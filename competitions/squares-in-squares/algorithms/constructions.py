"""Original constructive portfolio: grids, rotated cores, and deletion transfer.

Geometric families are inspired by the classical Göbel rotated-core idea cited
in the strategy notes. No third-party coordinates or implementation are used.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from packing import COLUMNS, Tile, extent, grid_layout

CLEARANCE_SCALE = 1.00000004


@dataclass
class Candidate:
    tiles: list[Tile]
    method: str
    source_n: int
    parameters: dict
    side: float


def _finish(tiles: list[Tile], side: float) -> list[Tile]:
    # Move centres, never resize the unit squares. A strict gap makes these
    # bounded, float-generated families robust to CSV decimal transport.
    return sorted((Tile((t.x-side/2)*CLEARANCE_SCALE,
                        (t.y-side/2)*CLEARANCE_SCALE, t.angle) for t in tiles),
                  key=lambda t: (t.x*t.x+t.y*t.y, t.x, t.y, t.angle))


def _corners(x: float, y: float, side: float) -> list[Tile]:
    return [Tile(x, y), Tile(side-x, y), Tile(x, side-y), Tile(side-x, side-y)]


def four_corners(k: int) -> list[Tile]:
    """4*k² axis-aligned corner cells and one central 45-degree cell."""
    if not isinstance(k, int) or k < 1:
        raise ValueError('k must be a positive integer')
    side = 2*k + math.sqrt(2)/2
    tiles = [Tile(side/2, side/2, math.pi/4)]
    for i in range(k):
        for j in range(k):
            tiles.extend(_corners(i+.5, j+.5, side))
    return _finish(tiles, side)


def diamond_staircase(m: int, b: int) -> list[Tile]:
    """A b*b rotated core plus four m*(m-1)/2-cell corner staircases.

    L=m+b/sqrt(2). Corner top-right vertices satisfy x+y<=m, outside
    the core diamond. b²>=2(m-2)² keeps each staircase in its quadrant;
    b²<=2m² keeps the central diamond inside the container.
    """
    if (not isinstance(m, int) or not isinstance(b, int) or m < 2 or b < 1
            or b*b < 2*(m-2)**2 or b*b > 2*m*m):
        raise ValueError('Incompatible staircase/core parameters')
    side = m+b/math.sqrt(2)
    tiles = []
    for i in range(b):
        for j in range(b):
            u, v = i-(b-1)/2, j-(b-1)/2
            tiles.append(Tile(side/2+(u-v)/math.sqrt(2),
                              side/2+(u+v)/math.sqrt(2), math.pi/4))
    for i in range(m-1):
        for j in range(m-1-i):
            tiles.extend(_corners(i+.5, j+.5, side))
    return _finish(tiles, side)


def build_portfolio(max_n: int = 1000) -> dict[int, Candidate]:
    if not isinstance(max_n, int) or not 1 <= max_n <= 1000:
        raise ValueError('max_n must be 1..1000')
    portfolio = {}
    for n in range(1, max_n+1):
        tiles = grid_layout(n)
        portfolio[n] = Candidate(tiles, 'grid', n, {}, extent(tiles))
    # Include a small larger-instance horizon: removing cells preserves
    # feasibility and can improve counts just below a constructed capacity.
    limit = (math.ceil(math.sqrt(max_n))+1)**2
    templates = []
    for k in range(1, math.isqrt(limit//4)+1):
        tiles = four_corners(k)
        if len(tiles) <= limit:
            templates.append((tiles, 'four-corners', {'k': k}))
    for m in range(2, math.isqrt(limit)+2):
        for b in range(1, math.isqrt(2*m*m)+1):
            capacity = 2*m*(m-1)+b*b
            if b*b >= 2*(m-2)**2 and capacity <= limit:
                templates.append((diamond_staircase(m, b), 'diamond-staircase', {'m': m, 'b': b}))
    for tiles, method, parameters in templates:
        min_x = min_y = math.inf
        max_x = max_y = -math.inf
        for index, tile in enumerate(tiles[:max_n], start=1):
            h = .5*(abs(math.cos(tile.angle))+abs(math.sin(tile.angle)))
            min_x, max_x = min(min_x, tile.x-h), max(max_x, tile.x+h)
            min_y, max_y = min(min_y, tile.y-h), max(max_y, tile.y+h)
            side = max(max_x-min_x, max_y-min_y)
            if side < portfolio[index].side-1e-12:
                portfolio[index] = Candidate(tiles[:index], method if index == len(tiles) else method+'/drop',
                                             len(tiles), parameters, side)
    return portfolio


def write_portfolio(path: Path, portfolio: dict[int, Candidate]) -> dict:
    if not portfolio or set(portfolio) != set(range(1, max(portfolio)+1)):
        raise ValueError('Portfolio must cover consecutive n starting at 1')
    path.parent.mkdir(parents=True, exist_ok=True)
    rows, details = 0, []
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for n, c in sorted(portfolio.items()):
            if len(c.tiles) != n:
                raise ValueError(f'n={n}: wrong tile count')
            for sid, tile in enumerate(c.tiles):
                writer.writerow((rows, n, sid, repr(tile.x), repr(tile.y), repr(tile.angle)))
                rows += 1
            details.append({'n': n, 'method': c.method, 'source_n': c.source_n,
                            'parameters': c.parameters, 'side_local': c.side,
                            'gain_local': (math.ceil(math.sqrt(n))-c.side)/math.sqrt(n)})
    return {'rows': rows, 'csv_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'clearance_scale': CLEARANCE_SCALE,
            'score_local': sum(max(0, c.side/math.sqrt(n)-1) for n, c in portfolio.items()),
            'improved_puzzles': sum(c.method != 'grid' for c in portfolio.values()),
            'certification': 'not-yet-run', 'details': details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--max-n', type=int, default=1000)
    args = parser.parse_args()
    report = write_portfolio(args.output, build_portfolio(args.max_n))
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'details'}, indent=2))


if __name__ == '__main__':
    main()
