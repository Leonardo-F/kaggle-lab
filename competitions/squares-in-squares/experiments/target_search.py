"""Search our own layouts at published best-known sides for small puzzles."""

import argparse
import json
import math
from multiprocessing import Pool
from pathlib import Path

import ctypes
import numpy as np
from scipy.optimize import minimize

from packing_batch import load_batch
from contact_polish import enclosing_box

LOSS = None


def init(lib):
    global LOSS
    native = ctypes.CDLL(str(lib))
    LOSS = native.pressure_loss
    array = np.ctypeslib.ndpointer(dtype=np.float64, flags='C_CONTIGUOUS')
    LOSS.argtypes = (ctypes.c_int, ctypes.c_double, array, array)
    LOSS.restype = ctypes.c_double


def loss(x, n, side):
    gradient = np.empty_like(x)
    return LOSS(n, side, x, gradient), gradient


def min_gap(poses):
    """Largest SAT penetration over all pairs; <=0 means valid."""
    n = len(poses)
    cosine, sine = np.cos(poses[:, 2]), np.sin(poses[:, 2])
    worst = -1e9
    for i in range(n - 1):
        dx = poses[i + 1:, 0] - poses[i, 0]
        dy = poses[i + 1:, 1] - poses[i, 1]
        cj, sj = cosine[i + 1:], sine[i + 1:]
        best = np.full(len(dx), 1e9)
        for ax, ay in ((cosine[i], sine[i]), (-sine[i], cosine[i]),
                       (cj, sj), (-sj, cj)):
            r_i = .5 * (abs(cosine[i] * ax + sine[i] * ay)
                        + abs(-sine[i] * ax + cosine[i] * ay))
            r_j = .5 * (np.abs(cj * ax + sj * ay) + np.abs(-sj * ax + cj * ay))
            best = np.minimum(best, r_i + r_j - np.abs(dx * ax + dy * ay))
        worst = max(worst, float(best.max()))
    return worst


def search(work):
    n, target, seed, attempts, base = work
    rng = np.random.default_rng(seed)
    side0 = max(np.ptp(base[:, 0]), np.ptp(base[:, 1]))
    p = base.copy()
    p[:, :2] *= target / side0
    best = (1e9, None)
    for k in range(attempts):
        x = p.copy()
        if k:
            x[:, :2] += rng.normal(scale=rng.choice([2e-4, 1e-3, 4e-3, 1.2e-2]), size=(n, 2))
            if k % 4 == 0:
                centre = x[rng.integers(n), :2]
                near = np.linalg.norm(x[:, :2] - centre, axis=1) < rng.uniform(1.5, 3.5)
                x[near, 2] += rng.choice([-1, 1]) * rng.uniform(.1, .5)
        result = minimize(loss, x.ravel(), args=(n, target), jac=True, method='L-BFGS-B',
                          options={'maxiter': 400, 'ftol': 2e-15, 'gtol': 1e-9})
        poses = result.x.reshape(n, 3)
        gap = min_gap(poses)
        if gap < best[0]:
            best = (gap, poses.copy())
        if gap <= 0:
            return n, target, poses, k + 1
    return n, target, None, attempts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('targets', type=Path, help='JSON: [[n, side], ...]')
    parser.add_argument('output', type=Path, help='JSON: [[n, [[x,y,angle],...]], ...]')
    parser.add_argument('--lib', type=Path, required=True)
    parser.add_argument('--attempts', type=int, default=4000)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--seed', type=int, default=20261124)
    args = parser.parse_args()

    _, seeds = load_batch(args.input)
    targets = json.loads(args.targets.read_text())
    work = [(n, side, args.seed + i, args.attempts, seeds[n]) for i, (n, side) in enumerate(targets)]
    found = []
    with Pool(args.workers, initializer=init, initargs=(args.lib.resolve(),)) as pool:
        for n, side, poses, tries in pool.imap_unordered(search, work):
            if poses is not None:
                found.append([n, poses.tolist()])
                print(f'FOUND n={n} side={side:.9f} tries={tries}', flush=True)
            else:
                print(f'miss n={n} side={side:.9f} tries={tries}', flush=True)
    args.output.write_text(json.dumps(found))


if __name__ == '__main__':
    main()
