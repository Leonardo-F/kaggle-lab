"""Rebuild the certified portfolio and add the best 45-degree core witnesses."""

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

from constructions import CLEARANCE_SCALE, Candidate, build_portfolio, finish_template, write_portfolio
from packing import Tile, extent
from strip_search import MIN_SIDE_GAIN, _add_borders, search_portfolio
from tilt_search import add_rectangular_cores, improve

ROOT_TWO = math.sqrt(2)


@dataclass(frozen=True)
class Core:
    side: float
    capacity: int
    p: int
    q: int
    right: int
    top: int
    bl: int
    br: int
    tl: int
    tr: int

    def layout(self) -> list[Tile]:
        side = self.side + 2e-9
        width, height = side - self.right, side - self.top
        p_half, q_half = self.p / ROOT_TWO, self.q / ROOT_TWO
        radius = (p_half + q_half)/2

        sum_min = self.bl + 1 + p_half if self.bl else 2*radius
        sum_max = width + height - (self.tr + 1 + p_half if self.tr else 2*radius)
        diff_min = -width + (self.br + 1 + q_half if self.br else 2*radius)
        diff_max = height - (self.tl + 1 + q_half if self.tl else 2*radius)

        u_min = max(sum_min, 2*radius, diff_min + 2*radius, 2*radius - diff_max)
        u_max = min(sum_max, width + height - 2*radius,
                    2*(height - radius) - diff_min, diff_max + 2*(width - radius))
        u = (u_min + u_max)/2
        v_min = max(diff_min, 2*radius - u, u - 2*(width - radius))
        v_max = min(diff_max, u - 2*radius, 2*(height - radius) - u)
        if u_min > u_max or v_min > v_max:
            raise ValueError(f'Inconsistent core witness: {self}')
        # Mark the midpoint of the feasible interval before transforming to x,y.
        x, y = (u - v_min/2 - v_max/2)/2, (u + v_min/2 + v_max/2)/2

        tiles = []
        for i in range(self.p):
            for j in range(self.q):
                du = (i - (self.p-1)/2)/ROOT_TWO
                dv = (j - (self.q-1)/2)/ROOT_TWO
                tiles.append(Tile(x + du - dv, y + du + dv, math.pi/4))
        for depth, right, top in ((self.bl, False, False), (self.br, True, False),
                                  (self.tl, False, True), (self.tr, True, True)):
            for i in range(depth):
                for j in range(depth - i):
                    dx, dy = i + .5, j + .5
                    tiles.append(Tile(width - dx if right else dx, height - dy if top else dy))
        k = math.floor(side)
        for i in range(self.right):
            for j in range(k):
                tiles.append(Tile(width + i + .5, j + .5))
        for j in range(self.top):
            for i in range(k - self.right):
                tiles.append(Tile(i + .5, height + j + .5))
        if len(tiles) != self.capacity:
            raise ValueError(f'Tile count does not match core witness: {self}')
        return finish_template(tiles, side)


def baseline_portfolio(tilt_witnesses):
    strip = search_portfolio(build_portfolio())
    return _add_borders(add_rectangular_cores(improve(strip, tilt_witnesses)))


def add_cores(baseline, witnesses, *, rectangles):
    portfolio = baseline.copy()
    layouts = {}
    for n, core in witnesses:
        if core.p != core.q and not rectangles:
            continue
        if core.side * CLEARANCE_SCALE >= portfolio[n].side - MIN_SIDE_GAIN:
            continue
        if core not in layouts:
            layouts[core] = core.layout()
        tiles = layouts[core][:n]
        method = 'square-core' if core.p == core.q else 'rectangular-core'
        portfolio[n] = Candidate(tiles, method, core.capacity, asdict(core), extent(tiles))
    return _add_borders(portfolio)


def read_witnesses(path):
    with path.open() as handle:
        for line in handle:
            n, side, *parameters = line.split()
            yield int(n), Core(float(side), *map(int, parameters))


def main():
    directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tilt-witnesses', type=Path, default=directory / 'tilt_witnesses.tsv')
    parser.add_argument('--core-witnesses', type=Path, default=directory / 'core_witnesses.tsv')
    parser.add_argument('--mode', choices=('baseline', 'square', 'rectangular'), default='rectangular')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.manifest.resolve():
        parser.error('CSV and manifest paths must be distinct')
    baseline = baseline_portfolio(args.tilt_witnesses)
    portfolio = baseline
    if args.mode != 'baseline':
        portfolio = add_cores(baseline, read_witnesses(args.core_witnesses),
                              rectangles=args.mode == 'rectangular')
    report = write_portfolio(args.output, portfolio)
    report['mode'] = args.mode
    report['improved_over_baseline'] = [n for n in portfolio
                                       if portfolio[n].side < baseline[n].side - MIN_SIDE_GAIN]
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print({key: value for key, value in report.items() if key != 'details'})


if __name__ == '__main__':
    main()
