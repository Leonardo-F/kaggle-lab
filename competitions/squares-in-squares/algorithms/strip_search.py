"""Improve the constructive portfolio with offset 45-degree strips and L borders."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import combinations_with_replacement
import json
import math
from pathlib import Path
from typing import Iterator

from constructions import CLEARANCE_SCALE, Candidate, build_portfolio, finish_template, write_portfolio
from packing import Tile, extent, layout_bounds

ROOT_TWO = math.sqrt(2)
MIN_SIDE_GAIN = 1e-6  # Skip changes on the scale of the decimal-transport clearance.
METHODS = ('combined', 'diagonal', 'border')


@dataclass(frozen=True)
class Margin:
    distance: float
    corner_depth: int  # floor(sqrt(2) * distance)
    end_row_span: int  # floor(2 * distance)


@dataclass(frozen=True)
class Strip:
    lower: Margin
    upper: Margin
    rows: int
    side: float
    capacity: int


def _corner_count(k: int, depth: int) -> int:
    """Count i+j <= depth with 1 <= i,j <= k."""
    if depth <= k + 1:
        return depth * (depth - 1) // 2
    omitted_depth = max(0, 2*k + 1 - depth)
    return k*k - omitted_depth * (omitted_depth - 1) // 2


def _strip_specs(max_side: int) -> Iterator[Strip]:
    # Row lengths change at half-units and corners at multiples of 1/sqrt(2).
    # Calculate those floors in integer arithmetic, including exact contacts.
    margins = {Margin(h/2, math.isqrt(h*h // 2), h)
               for h in range(math.ceil(2 * ROOT_TWO * max_side))}
    margins.update(Margin(d/ROOT_TWO, d, math.isqrt(2*d*d))
                   for d in range(1, 2*max_side))
    width_limit = ROOT_TWO * max_side
    for lower, upper in combinations_with_replacement(sorted(margins, key=lambda m: m.distance), 2):
        free_width = width_limit - lower.distance - upper.distance
        for rows in range(1, math.floor(free_width) + 1):
            side = (lower.distance + upper.distance + rows) / ROOT_TWO
            if side >= max_side:
                continue
            k = math.floor(side)
            a, b = lower.end_row_span, upper.end_row_span
            # min(a+2*j, b+2*(rows-1-j)) switches at most once.
            from_lower = min(rows, max(0, (b - a + 2*(rows - 1)) // 4 + 1))
            from_upper = rows - from_lower
            angled = from_lower*(a + from_lower - 1) + from_upper*(b + from_upper - 1)
            capacity = angled + _corner_count(k, lower.corner_depth) + _corner_count(k, upper.corner_depth)
            if capacity > k*k:
                yield Strip(lower, upper, rows, side, capacity)


def _strip_layout(strip: Strip) -> list[Tile]:
    tiles = []
    side = strip.side
    half_diagonal = side / ROOT_TWO
    for j in range(strip.rows):
        span = min(strip.lower.end_row_span + 2*j,
                   strip.upper.end_row_span + 2*(strip.rows - 1 - j))
        v = strip.lower.distance - half_diagonal + j + .5
        for i in range(span):
            u = half_diagonal + i - (span - 1)/2
            tiles.append(Tile((u - v)/ROOT_TWO, (u + v)/ROOT_TWO, math.pi/4))
    k = math.floor(side)
    for i in range(k):
        for j in range(min(k, strip.lower.corner_depth - i - 1)):
            tiles.append(Tile(side - i - .5, j + .5))
        for j in range(min(k, strip.upper.corner_depth - i - 1)):
            tiles.append(Tile(i + .5, side - j - .5))
    return finish_template(tiles, side)


def _add_diagonals(portfolio: dict[int, Candidate]) -> dict[int, Candidate]:
    max_n = max(portfolio)
    sides = {n: candidate.side for n, candidate in portfolio.items()}
    choices: dict[int, Strip] = {}
    for strip in _strip_specs(math.isqrt(max_n - 1) + 1):
        # The centre dilation is bounded by the same dilation of the container.
        upper_side = strip.side * CLEARANCE_SCALE
        for n in range(math.floor(strip.side)**2 + 1, min(max_n, strip.capacity) + 1):
            if upper_side < sides[n] - MIN_SIDE_GAIN:
                sides[n], choices[n] = upper_side, strip

    layouts: dict[Strip, list[Tile]] = {}
    improved = portfolio.copy()
    for n, strip in choices.items():
        if strip not in layouts:
            layouts[strip] = _strip_layout(strip)
        tiles = layouts[strip][:n]
        improved[n] = Candidate(
            tiles, 'diagonal-strip', strip.capacity,
            {'rows': strip.rows, 'lower': asdict(strip.lower), 'upper': asdict(strip.upper)},
            extent(tiles),
        )
    return improved


def _border_inner_side(side: float) -> float:
    return max(side, math.floor(side) * CLEARANCE_SCALE)


def _border_layout(seed: Candidate, width: int) -> list[Tile]:
    # Keep the seed fixed. Separate the two new grids and the seed along the
    # edges of an enclosing square, with a gap that survives numeric CSV IO.
    left, bottom, _, _ = layout_bounds(seed.tiles)
    k = math.floor(seed.side)
    start = _border_inner_side(seed.side) + (CLEARANCE_SCALE - 1)
    tiles = seed.tiles.copy()
    for i in range(width):
        for j in range(k + width):
            tiles.append(Tile(left + start + i*CLEARANCE_SCALE + .5,
                              bottom + j*CLEARANCE_SCALE + .5))
        for j in range(k):
            tiles.append(Tile(left + j*CLEARANCE_SCALE + .5,
                              bottom + start + i*CLEARANCE_SCALE + .5))
    return tiles


def _add_borders(seeds: dict[int, Candidate]) -> dict[int, Candidate]:
    max_n = max(seeds)
    max_side = math.isqrt(max_n - 1) + 1
    sides = {n: candidate.side for n, candidate in seeds.items()}
    choices: dict[int, tuple[int, int]] = {}
    for seed_n, seed in sorted(seeds.items()):
        k = math.floor(seed.side)
        excess = seed_n - k*k
        if excess <= 0:
            continue
        for width in range(1, max_side - k):
            new_grid_count = (k + width)**2
            upper_side = _border_inner_side(seed.side) + width * CLEARANCE_SCALE
            # Adding the border keeps the number beyond the old k*k grid.
            for n in range(new_grid_count + 1, min(max_n, new_grid_count + excess) + 1):
                if upper_side < sides[n] - MIN_SIDE_GAIN:
                    sides[n], choices[n] = upper_side, (seed_n, width)

    layouts: dict[tuple[int, int], list[Tile]] = {}
    improved = seeds.copy()
    for n, (seed_n, width) in choices.items():
        seed = seeds[seed_n]
        key = (seed_n, width)
        if key not in layouts:
            layouts[key] = _border_layout(seed, width)
        full = layouts[key]
        tiles = full[:n]
        improved[n] = Candidate(
            tiles, 'l-border', len(full),
            {'width': width, 'seed_n': seed_n, 'seed_method': seed.method,
             'seed_source_n': seed.source_n, 'seed_parameters': seed.parameters},
            extent(tiles),
        )
    return improved


def search_portfolio(baseline: dict[int, Candidate], *, method: str = 'combined') -> dict[int, Candidate]:
    """Take the consecutive portfolio from build_portfolio and improve it per n."""
    if method not in METHODS:
        raise ValueError(f'Unknown method: {method}')
    candidates = _add_diagonals(baseline) if method != 'border' else baseline
    return _add_borders(candidates) if method != 'diagonal' else candidates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--max-n', type=int, default=1000)
    parser.add_argument('--method', choices=METHODS, default='combined')
    args = parser.parse_args()
    if args.output.resolve() == args.manifest.resolve():
        parser.error('--manifest must differ from --output')
    if not 1 <= args.max_n <= 1000:
        parser.error('--max-n must be 1..1000')

    baseline = build_portfolio(args.max_n)
    portfolio = search_portfolio(baseline, method=args.method)
    report = write_portfolio(args.output, portfolio)
    report.update(
        method=args.method,
        baseline_score_local=sum(c.side/math.sqrt(n) - 1 for n, c in sorted(baseline.items())),
        improved_vs_constructed=sum(c.side < baseline[n].side - MIN_SIDE_GAIN for n, c in portfolio.items()),
        method_counts=dict(sorted(Counter(c.method for c in portfolio.values()).items())),
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'details'}, indent=2))


if __name__ == '__main__':
    main()
