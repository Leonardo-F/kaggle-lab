"""Perturb our own layout at a published side, quench, then repair at that side."""

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from target_search import init, loss, min_gap
from contact_repair import repair
from packing_batch import load_batch
from contact_polish import enclosing_box
from rotated_windows import layout_side


def search(work):
    n, target, seed, attempts, baseline, poses = work
    rng = np.random.default_rng(seed)
    base = poses.copy()
    side0 = max(np.ptp(base[:, 0]), np.ptp(base[:, 1]))
    best = (1e9, None)
    for k in range(attempts):
        x = base.copy()
        x[:, :2] *= target / side0
        x[:, :2] += rng.normal(scale=rng.choice([1e-4, 5e-4, 2e-3, 6e-3]), size=(n, 2))
        if k % 5 == 0:
            centre = x[rng.integers(n), :2]
            near = np.linalg.norm(x[:, :2] - centre, axis=1) < rng.uniform(1.5, 3.5)
            x[near, 2] += rng.choice([-1, 1]) * rng.uniform(.1, .5)
        result = minimize(loss, x.ravel(), args=(n, target), jac=True, method='L-BFGS-B',
                          options={'maxiter': 400, 'ftol': 2e-15, 'gtol': 1e-9})
        candidate = result.x.reshape(n, 3)
        gap = min_gap(candidate)
        if gap < best[0]:
            best = (gap, candidate.copy())
        if gap <= 0:
            break
    if best[1] is None:
        return (n,)
    winner = None
    for trust in (.6, .4, .2, .1):
        repaired = repair(best[1].copy(), trust)
        if repaired is None:
            continue
        poses_out, side = repaired
        if min_gap(poses_out) > 0:
            continue
        if side < baseline - 1e-9 and (winner is None or side < winner[1]):
            winner = (poses_out, side)
    if winner is None:
        return (n,)
    return n, winner[0].tolist(), winner[1], best[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('targets', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--lib', type=Path, required=True)
    parser.add_argument('--attempts', type=int, default=20000)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--seed-offset', type=int, default=0)
    args = parser.parse_args()
    _, seeds = load_batch(args.input)
    targets = json.loads(args.targets.read_text())
    work = []
    for i, (n, target) in enumerate(targets):
        base, _ = enclosing_box(seeds[n].copy())
        work.append((n, target, args.seed_offset + i, args.attempts, layout_side(seeds[n]), base))
    found = []
    with Pool(args.workers, initializer=init, initargs=(args.lib.resolve(),)) as pool:
        for result in pool.imap_unordered(search, work):
            if len(result) == 4:
                n, poses, side, gap = result
                found.append([n, poses])
                print(f'WIN n={n} side={side:.9f} search_gap={gap:.6f}', flush=True)
            else:
                print(f'miss n={result[0]}', flush=True)
    args.output.write_text(json.dumps(found))


if __name__ == '__main__':
    main()
