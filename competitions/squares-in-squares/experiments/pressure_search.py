"""Restart a pressure search from self-generated layouts using a fixed random seed."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import ctypes
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from contact_polish import enclosing_box, separate
from contact_repair import optimize
from rotated_windows import Windows, layout_side
from packing_batch import load_batch, write_updates

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


def starts_for(n, seeds):
    best, side = enclosing_box(seeds[n])
    variants = [best]
    for m in range(n + 1, min(n + 8, 1001)):
        seed, other_side = enclosing_box(seeds[m])
        if other_side > side + .32:
            continue
        crop = Windows(seed).crop(n, other_side + 1e-7)
        if crop is not None:
            variants.append(enclosing_box(crop)[0])
    return variants


def search(work):
    n, starts, attempts = work
    best, side = enclosing_box(starts[0])
    rng = np.random.default_rng(20261123 + n)
    for restart in range(attempts):
        pattern = restart % 5
        seed = (best if pattern < 3 else starts[restart % len(starts)]).copy()
        length = layout_side(seed)
        target = max(np.sqrt(n), min(side - .00008, length - .00008) - rng.choice(
            [0., .0005, .002, .006, .012, .025],
        ))
        seed[:, :2] -= (length - target) * .5
        if restart:
            scale = rng.choice([.005, .014, .035, .070, .13])
            seed += scale * rng.normal(size=seed.shape)
            if pattern == 2:
                # Coherently turn a cluster and give the optimizer new contacts.
                center = seed[rng.integers(n), :2]
                near = np.linalg.norm(seed[:, :2] - center, axis=1) < rng.uniform(1.5, 3.5)
                seed[near, 2] += rng.choice([-1, 1]) * rng.uniform(.10, .40)
        result = minimize(
            loss, seed.ravel(), args=(n, target), jac=True, method='L-BFGS-B',
            options={'maxiter': 550, 'ftol': 2e-15, 'gtol': 1e-9},
        )
        if result.fun > .001:
            continue
        poses, repaired_side = separate(result.x.reshape(n, 3).copy())
        if repaired_side < side - 2e-6:
            best, side = poses, repaired_side
    if side < layout_side(starts[0]) - 2e-6:
        _, best, side = optimize((n, best, 4))
    return n, best, side


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--lib', type=Path, required=True)
    parser.add_argument('--targets', type=int, nargs='+', required=True)
    parser.add_argument('--attempts', type=int, default=80)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.output.exists() or args.attempts < 1 or any(not 2 <= n <= 999 for n in args.targets):
        parser.error('Use a new output, positive attempts and targets in 2..999')
    rows, seeds = load_batch(args.input)
    targets = [(n, starts_for(n, seeds), args.attempts) for n in args.targets]
    updates = {}
    with ProcessPoolExecutor(max_workers=args.workers, initializer=init, initargs=(args.lib.resolve(),)) as pool:
        for n, poses, side in pool.map(search, targets):
            if side < layout_side(seeds[n]) - 2e-6:
                updates[n] = poses
                print(f'{n} {layout_side(seeds[n]):.9f} -> {side:.9f}', flush=True)
    write_updates(args.output, rows, seeds, updates)


if __name__ == '__main__':
    main()
