"""Reinsert selected tiles and minimize wall penetration and SAT overlap."""

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from constructions import finish_template
from packing import Tile, extent


class Relaxation:
    def __init__(self, count):
        self.first, self.second = np.triu_indices(count, 1)
        self.pairs = np.arange(len(self.first))

    def loss(self, vector, side):
        tiles = vector.reshape(-1, 3)
        xy, theta = tiles[:, :2], tiles[:, 2]
        c, s = np.cos(theta), np.sin(theta)
        axes = np.stack((np.column_stack((c,s)), np.column_stack((-s,c))), axis=1)
        first, second = self.first, self.second
        pair_axes = np.concatenate((axes[first], axes[second]), axis=1)
        delta = xy[second] - xy[first]
        signed = np.einsum('pd,pad->pa', delta, pair_axes)
        chosen = np.argmax(np.abs(signed), axis=1)
        projection = signed[self.pairs, chosen]
        normal = pair_axes[self.pairs, chosen]
        owner = np.where(chosen < 2, first, second)
        angle_gap = theta[first] - theta[second]
        c_gap, s_gap = np.cos(angle_gap), np.sin(angle_gap)
        support = (1 + abs(c_gap) + abs(s_gap))/2
        overlap = np.maximum(0, support - abs(projection))
        walls = np.maximum(0, abs(xy) + (abs(c) + abs(s))[:, None]/2 - side/2)

        gradient = np.empty_like(tiles)
        gradient[:, :2] = walls * np.sign(xy)
        gradient[:, 2] = walls.sum(axis=1) * (-s*np.sign(c) + c*np.sign(s))/2
        force = (overlap * np.sign(projection))[:, None] * normal
        rotation = overlap * (-s_gap*np.sign(c_gap) + c_gap*np.sign(s_gap))/2
        np.add.at(gradient[:, :2], first, force)
        np.add.at(gradient[:, :2], second, -force)
        np.add.at(gradient[:, 2], first, rotation)
        np.add.at(gradient[:, 2], second, -rotation)
        np.add.at(gradient[:, 2], owner, overlap * np.sign(projection)
                  * (delta[:, 0]*normal[:, 1] - delta[:, 1]*normal[:, 0]))
        return (np.dot(overlap, overlap) + np.sum(walls**2))/2, gradient.ravel()

    def fit(self, initial, side):
        return minimize(self.loss, initial.ravel(), args=(side,), jac=True, method='L-BFGS-B',
                        options={'maxiter': 1100, 'gtol': 1e-11, 'ftol': 1e-16})


def read_seeds(path, n):
    seeds = {n-1: [], n: []}
    with path.open(newline='') as handle:
        for row in csv.DictReader(handle):
            size = int(row['n'])
            if size > n:
                break
            if size in seeds:
                seeds[size].append([float(row[key]) for key in ('x','y','angle')])
    arrays = []
    for size, rows in seeds.items():
        if len(rows) != size:
            raise ValueError(f'Expected {size} tiles in the n={size} seed')
        array = np.array(rows)
        half = (abs(np.cos(array[:, 2])) + abs(np.sin(array[:, 2])))[:, None]/2
        array[:, :2] -= ((array[:, :2] + half).max(axis=0) +
                         (array[:, :2] - half).min(axis=0))/2
        arrays.append(array)
    return arrays


def reinsert(seed, n, side, rng):
    initial = seed.copy()
    if len(initial) < n:
        initial = np.vstack((initial, np.zeros((n - len(initial), 3))))
    count = int(rng.integers(1, 5))
    # Reinsert a small neighborhood, including a new tile for n-1 seeds.
    focal = rng.uniform(-side/2, side/2, 2)
    nearby = np.argsort(np.linalg.norm(initial[:len(seed), :2] - focal, axis=1))
    indices = np.concatenate((nearby[:count], np.arange(len(seed), n)))
    initial[indices, :2] = np.clip(focal + rng.normal(0, .6, (len(indices), 2)),
                                  -side/2+.5, side/2-.5)
    initial[indices, 2] = rng.uniform(-math.pi/4, math.pi/4, len(indices))
    initial += rng.normal(0, (.09, .09, .10), initial.shape)
    return initial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--attempts', type=int, default=200)
    parser.add_argument('--seed', type=int, default=29)
    parser.add_argument('--n', type=int, default=29)
    parser.add_argument('--target', type=float, default=5.9899)
    args = parser.parse_args()
    if not 2 <= args.n <= 1000 or args.attempts <= 0 or not math.isfinite(args.target) or args.target <= 0:
        parser.error('Requires 2 <= n <= 1000, positive attempts, and a finite positive target')
    if args.input.resolve() == args.output.resolve():
        parser.error('Output must differ from the input CSV')
    rng = np.random.default_rng(args.seed)
    relax = Relaxation(args.n)
    seeds = read_seeds(args.input, args.n)
    best, best_result = math.inf, None
    side = args.target
    for attempt in range(1, args.attempts + 1):
        result = relax.fit(reinsert(seeds[attempt % len(seeds)], args.n, side, rng), side)
        if result.fun < best:
            best, best_result = float(result.fun), result.x.reshape(-1, 3)
        if result.fun > 1e-17:
            continue
        layout = finish_template([Tile(*map(float, row)) for row in best_result], 0)
        side = extent(layout)
        if not side < args.target + 1e-5:
            break
        args.output.write_text(json.dumps({'n': args.n, 'side': side, 'attempt': attempt,
                                           'tiles': [[t.x,t.y,t.angle] for t in layout]}) + '\n')
        print(f'Found side {side:.10f} on attempt {attempt}')
        return
    print(f'{args.attempts} attempts; smallest residual sum of half squares {best:.4g}')


if __name__ == '__main__':
    main()
