"""Compress self-generated packings with alternating angle steps and exact face constraints."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import json
from math import sqrt
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from contact_polish import Candidate, COLUMNS, Tile, enclosing_box, extent, linear_step, nearby_contacts
from packing_batch import MIN_GAIN, _add_borders, load_batch

CLEARANCE = 2e-8


def repair(poses, trust):
    """At fixed angles, choose a separating face per pair and solve for centers."""
    poses, side = enclosing_box(poses)
    n = len(poses)
    left, right, axes, projections, radius, offsets = nearby_contacts(
        poses, np.sqrt(2) + 2 * np.sqrt(2) * trust + CLEARANCE,
    )
    gaps = abs(projections) - radius
    active = np.flatnonzero(gaps.max(axis=1) <= 2 * np.sqrt(2) * trust + CLEARANCE)
    faces = gaps[active].argmax(axis=1)
    normals = axes[active, faces] * np.sign(projections[active, faces])[:, None]
    indices = np.column_stack((
        2 * left[active, None] + np.arange(2),
        2 * right[active, None] + np.arange(2),
    )).ravel()
    rows = np.repeat(np.arange(len(active)), 4).tolist()
    cols = indices.tolist()
    data = np.column_stack((normals, -normals)).ravel().tolist()
    limits = (gaps[active, faces] - CLEARANCE).tolist()

    half = offsets.max(axis=1)
    bounds = []
    for i, center in enumerate(poses[:, :2]):
        for axis in range(2):
            index = 2 * i + axis
            bounds.append((max(-trust, half[i, axis] - center[axis]), trust))
            rows.extend((len(limits), len(limits)))
            cols.extend((index, 2 * n))
            data.extend((1., -1.))
            limits.append(side - center[axis] - half[i, axis])

    bounds.append((-trust, 3 * trust))
    objective = np.zeros(2 * n + 1)
    objective[-1] = 1
    matrix = coo_matrix((data, (rows, cols)), shape=(len(limits), 2 * n + 1)).tocsr()
    result = linprog(
        objective, A_ub=matrix, b_ub=limits, bounds=bounds, method='highs',
        options={'primal_feasibility_tolerance': 1e-9, 'dual_feasibility_tolerance': 1e-9},
    )
    if not result.success:
        return None
    poses[:, :2] += result.x[:-1].reshape(n, 2)
    return enclosing_box(poses)


def optimize(work):
    n, seed, steps = work
    best, side = enclosing_box(seed)
    for trust in (.025, .010, .003, .0005):
        for _ in range(steps):
            delta = linear_step(best, side, trust, 0)
            start = best if delta is None else best + delta
            candidate = repair(start, 2 * trust)
            if candidate is None or candidate[1] >= side - 3e-8:
                if delta is None:
                    break
                candidate = repair(best, 2 * trust)
                if candidate is None or candidate[1] >= side - 3e-8:
                    break
            best, side = candidate
    return n, best, side


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--min-n', type=int, default=1)
    parser.add_argument('--max-n', type=int, default=1000)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--steps', type=int, default=4)
    args = parser.parse_args()
    if args.output.exists() or not 1 <= args.min_n <= args.max_n <= 1000 or args.steps < 1:
        parser.error('Use a new output, positive steps and a valid puzzle range')

    rows, seeds = load_batch(args.input)
    sides = {n: enclosing_box(seed)[1] for n, seed in seeds.items()}
    targets = [(n, seed, args.steps) for n, seed in seeds.items()
               if args.min_n <= n <= args.max_n and np.any(abs(np.sin(2 * seed[:, 2])) > 1e-5)]
    best = {n: Candidate([Tile(*pose) for pose in seed], 'baseline', n, {}, sides[n])
            for n, seed in seeds.items()}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for n, poses, side in pool.map(optimize, targets, chunksize=1):
            if side < sides[n] - MIN_GAIN:
                # Recenter before exporting to retain precision in decimal coordinates.
                poses[:, :2] -= poses[:, :2].mean(axis=0)
                tiles = [Tile(*pose) for pose in poses.tolist()]
                best[n] = Candidate(tiles, 'contact-repair', n, {}, extent(tiles))
                print(f'{n} {sides[n]:.9f} -> {side:.9f}', flush=True)

    best = _add_borders(best)
    with args.output.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(COLUMNS)
        improved = 0
        gain = 0.
        for n, candidate in sorted(best.items()):
            if candidate.side < sides[n] - MIN_GAIN:
                improved += 1
                gain += (sides[n] - candidate.side) / sqrt(n)
                for row, tile in zip(rows[n], candidate.tiles):
                    row[3:] = [repr(tile.x), repr(tile.y), repr(tile.angle)]
            writer.writerows(rows[n])
    print(json.dumps({'improved': improved, 'gain': gain}), flush=True)


if __name__ == '__main__':
    main()
