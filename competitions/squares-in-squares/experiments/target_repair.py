"""Random-seed search at a fixed published side, then LP repair."""

import argparse
import json
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from target_search import init, loss, min_gap
from contact_repair import repair
from packing_batch import load_batch
from rotated_windows import layout_side


def attempt(work):
    n, target, seed, attempts, baseline = work
    rng = np.random.default_rng(seed)
    best = (1e9, None)
    for k in range(attempts):
        m = int(np.ceil(np.sqrt(n)))
        idx = rng.choice(m * m, n, replace=False)
        pts = np.array([(i % m + .5, i // m + .5) for i in idx], float) * (target / m)
        x = np.zeros((n, 3))
        x[:, 0], x[:, 1] = pts[:, 0], pts[:, 1]
        x[:, :2] += rng.normal(scale=target / m * .25, size=(n, 2))
        x[:, 2] = rng.choice([0., np.pi / 4, rng.uniform(0, np.pi / 2)], n)
        x[:, :2] = np.clip(x[:, :2], .55, target - .55)
        result = minimize(loss, x.ravel(), args=(n, target), jac=True, method='L-BFGS-B',
                          options={'maxiter': 400, 'ftol': 2e-15, 'gtol': 1e-9})
        poses = result.x.reshape(n, 3)
        gap = min_gap(poses)
        if gap < best[0]:
            best = (gap, poses.copy())
        if gap <= 0:
            break
    if best[1] is None:
        return (n,)
    winner = None
    for trust in (.6, .4, .2, .1):
        repaired = repair(best[1].copy(), trust)
        if repaired is None:
            continue
        candidate, side = repaired
        if min_gap(candidate) > 0:
            continue
        if side < baseline - 1e-9 and (winner is None or side < winner[1]):
            winner = (candidate, side)
    if winner is None:
        return (n,)
    return n, winner[0].tolist(), winner[1], best[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('targets', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--lib', type=Path, required=True)
    parser.add_argument('--attempts', type=int, default=4000)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--seed', type=int, default=20261124)
    args = parser.parse_args()
    _, seeds = load_batch(args.input)
    targets = json.loads(args.targets.read_text())
    work = [(n, side, args.seed + i, args.attempts, layout_side(seeds[n]))
            for i, (n, side) in enumerate(targets)]
    found = []
    with Pool(args.workers, initializer=init, initargs=(args.lib.resolve(),)) as pool:
        for result in pool.imap_unordered(attempt, work):
            if len(result) == 4:
                n, poses, side, gap = result
                found.append([n, poses])
                print(f'WIN n={n} side={side:.9f} search_gap={gap:.6f}', flush=True)
            else:
                print(f'miss n={result[0]}', flush=True)
    args.output.write_text(json.dumps(found))


if __name__ == '__main__':
    main()
