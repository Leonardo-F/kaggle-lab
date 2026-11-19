"""Combine variable-angle strips and off-centre rotated cores with the existing portfolio."""
import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

from constructions import CLEARANCE_SCALE, Candidate, build_portfolio, finish_template, write_portfolio
from packing import Tile, extent
from strip_search import MIN_SIDE_GAIN, _add_borders, search_portfolio

EPS = 1e-10


@dataclass(frozen=True)
class StripWitness:
    k: int
    degrees: float
    phase: float
    first: int
    last: int


def critical_sides(w):
    """The n-th threshold is the smallest side for n tiles with this witness."""
    theta = math.radians(w.degrees)
    s, c = math.sin(theta), math.cos(theta)
    lower_margin = w.phase + w.first - .5
    end = w.phase + w.last + .5
    minimum_side = max(w.k, end / (s + c))
    sides = []
    for i in range(1, w.k + 1):
        for j in range(1, w.k + 1):
            distance = i*s + j*c
            if distance <= lower_margin + EPS:
                sides.append(minimum_side)
            sides.append(max(minimum_side, (end + distance)/(s + c)))
    for row in range(w.first, w.last + 1):
        t = w.phase + row
        count = min(math.floor((t - .5)/(s*c) + EPS),
                    math.floor((w.k + 1 - s)/c + EPS))
        for length in range(1, count + 1):
            sides.append(max(minimum_side, s + length*c,
                             (t + .5 + length*s*c)/(s + c)))
    return sorted(sides)


def make_layout(w, side):
    theta = math.radians(w.degrees)
    s, c = math.sin(theta), math.cos(theta)
    half = (s + c)/2
    upper_margin = side*(s + c) - w.phase - w.last - .5
    lower_margin = w.phase + w.first - .5
    tiles = []
    for i in range(1, w.k + 1):
        for j in range(1, w.k + 1):
            distance = i*s + j*c
            if distance <= lower_margin + EPS:
                tiles.append(Tile(side - i + .5, j - .5))
            if distance <= upper_margin + EPS:
                tiles.append(Tile(i - .5, side - j + .5))
    for row in range(w.first, w.last + 1):
        # u = cx + sy and v = -sx + cy; a whole row has the same v.
        t = w.phase + row
        v = t - side*s
        lo = max((half + s*v)/c, (half - c*v)/s)
        hi = min((side - half + s*v)/c, (side - half - c*v)/s)
        count = max(0, math.floor(min((side - s)/c, (t - .5)/(s*c),
                                      (side*(s + c) - t - .5)/(s*c)) + EPS))
        for i in range(count):
            u = (lo + hi)/2 + i - (count - 1)/2
            tiles.append(Tile(u*c - v*s, u*s + v*c, theta))
    return finish_template(tiles, side)


def improve(baseline, witness_file):
    choices = {}
    sides = {n: candidate.side for n, candidate in baseline.items()}
    max_n = max(baseline)
    seen = set()
    with witness_file.open() as handle:
        for line in handle:
            k, _, _, degrees, phase, first, last = line.split()
            w = StripWitness(int(k), float(degrees), float(phase), int(first), int(last))
            if w in seen or w.k*w.k >= max_n:
                continue
            seen.add(w)
            for n, ideal in enumerate(critical_sides(w), 1):
                if ideal >= w.k + 1 or n > max_n:
                    break
                if n <= w.k*w.k:
                    continue
                # Guard the active upper threshold from binary roundoff.
                side = ideal + 1e-9
                if side * CLEARANCE_SCALE < sides[n] - MIN_SIDE_GAIN:
                    sides[n] = side * CLEARANCE_SCALE
                    choices[n] = (w, side)
    combined = baseline.copy()
    for n, (w, side) in choices.items():
        layout = make_layout(w, side)
        if len(layout) < n:
            raise ValueError(f'Capacity/geometry mismatch for n={n} and {w}')
        tiles = layout[:n]
        combined[n] = Candidate(tiles, 'tilted-strip', len(layout), asdict(w), extent(tiles))
    return combined


def add_rectangular_cores(baseline):
    """Friedman's off-centre Göbel family (1997); construct all coordinates here."""
    result = baseline.copy()
    max_n = max(baseline)
    for a in range(1, math.isqrt(max_n) + 1):
        for b in range(1, math.isqrt(max_n) + 1):
            radius = b/math.sqrt(2)
            if abs(a - radius) > .5:
                continue
            width = a + .5 + radius
            side = width + 1
            capacity = 2*a*(a + 1) + b*b + math.floor(side)
            eligible = [n for n in range(math.floor(side)**2 + 1, min(max_n, capacity) + 1)
                        if side*CLEARANCE_SCALE < result[n].side - MIN_SIDE_GAIN]
            if not eligible:
                continue
            tiles = [Tile(width + .5, j + .5) for j in range(math.floor(side))]
            for i in range(a):
                for j in range(a - i):
                    for x in (i + .5, width - i - .5):
                        for y in (j + .5, side - j - .5):
                            tiles.append(Tile(x, y))
            for i in range(b):
                for j in range(b):
                    tiles.append(Tile(width/2 + (i - j)/math.sqrt(2),
                                      side/2 + (i + j - b + 1)/math.sqrt(2), math.pi/4))
            layout = finish_template(tiles, side)
            for n in eligible:
                subset = layout[:n]
                result[n] = Candidate(subset, 'off-centre-core', capacity,
                                      {'a': a, 'b': b}, extent(subset))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--witnesses', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    if len({p.resolve() for p in (args.witnesses, args.output, args.manifest)}) != 3:
        parser.error('Witness, output and manifest paths must be distinct')
    baseline = search_portfolio(build_portfolio())
    direct = improve(baseline, args.witnesses)
    strip_only = _add_borders(direct)
    merged = add_rectangular_cores(direct)
    final = _add_borders(merged)
    report = write_portfolio(args.output, final)
    report['direct_improvements'] = [n for n in direct if direct[n].side < baseline[n].side - MIN_SIDE_GAIN]
    report['score_strip_with_border'] = sum(c.side/math.sqrt(n) - 1 for n, c in strip_only.items())
    report['strip_with_border_improvements'] = [
        n for n in strip_only if strip_only[n].side < baseline[n].side - MIN_SIDE_GAIN]
    report['core_improvements_including_border'] = [
        n for n in final if final[n].side < strip_only[n].side - MIN_SIDE_GAIN]
    report['score_before_border'] = sum(c.side/math.sqrt(n) - 1 for n, c in direct.items())
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(report, indent=2) + '\n')
    print({k: v for k, v in report.items() if k != 'details'})


if __name__ == '__main__':
    main()
