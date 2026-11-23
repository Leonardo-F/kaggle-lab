"""Read a self-generated portfolio and preserve untouched decimal coordinates."""

import csv
import json
from math import sqrt

import numpy as np

from contact_polish import Candidate, COLUMNS, Tile, extent, _add_borders, enclosing_box

MIN_GAIN = 1e-6


def load_batch(path):
    rows = {n: [] for n in range(1, 1001)}
    with path.open(newline='', encoding='utf-8') as stream:
        reader = csv.reader(stream)
        if tuple(next(reader)) != COLUMNS:
            raise ValueError('Expected a packing CSV')
        for rid, n, sid, *pose in reader:
            rows[int(n)].append([rid, n, sid, *pose])
    if any(len(group) != n for n, group in rows.items()):
        raise ValueError('Expected a complete packing CSV')
    seeds = {n: np.array([row[3:] for row in group], dtype=float) for n, group in rows.items()}
    return rows, seeds


def write_updates(path, rows, seeds, updates):
    sides = {n: enclosing_box(seed)[1] for n, seed in seeds.items()}
    best = {}
    for n, seed in seeds.items():
        poses = updates.get(n, seed).copy()
        if n in updates:
            poses[:, :2] -= poses[:, :2].mean(axis=0)
        tiles = [Tile(*pose) for pose in poses.tolist()]
        best[n] = Candidate(tiles, 'search' if n in updates else 'baseline', n, {}, extent(tiles))

    for n in range(999, 0, -1):
        donor = best[n+1]
        if donor.side < best[n].side - MIN_GAIN:
            tiles = donor.tiles[:n]
            best[n] = Candidate(tiles, 'deletion', donor.source_n, {}, extent(tiles))
    best = _add_borders(best)

    gains = {n: (sides[n] - c.side) / sqrt(n) for n, c in best.items()
             if c.side < sides[n] - MIN_GAIN}
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(COLUMNS)
        for n, candidate in sorted(best.items()):
            if n in gains:
                for row, tile in zip(rows[n], candidate.tiles):
                    row[3:] = [repr(tile.x), repr(tile.y), repr(tile.angle)]
            writer.writerows(rows[n])
    print(json.dumps({'improved': len(gains), 'gain': sum(gains.values())}), flush=True)
