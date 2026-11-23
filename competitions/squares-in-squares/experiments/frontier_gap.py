"""Compare a self-generated portfolio with the public per-puzzle best sides.

The reference file holds public leaderboard values only; it is used to rank
targets, never to change a layout. Every row of our CSV is re-measured here.
"""

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from packing_batch import load_batch
from rotated_windows import layout_side

RANGES = ((1, 100), (101, 324), (325, 576), (577, 1000))


def side_list(seeds):
    return {n: layout_side(seed) for n, seed in seeds.items()}


def score(side, n):
    return side / math.sqrt(n) - 1


def bucket(n):
    for low, high in RANGES:
        if low <= n <= high:
            return f'{low}-{high}'
    raise ValueError(n)


def family(n):
    k = math.isqrt(n)
    d = n - k * k
    if d <= 3:
        return f'k^2+{d}'
    if d <= 10:
        return 'k^2+4..10'
    if d <= 30:
        return 'k^2+11..30'
    return 'k^2+31..'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='our complete packing CSV')
    parser.add_argument('--reference', type=Path,
                        default=Path(__file__).resolve().parent.parent
                        / 'docs/results/per-puzzle-best-2026-11-23.json')
    parser.add_argument('--targets', type=Path,
                        help='write n,gap rows for puzzles we can still improve')
    parser.add_argument('--min-gap', type=float, default=1e-6,
                        help='score gap needed before a puzzle counts as a target')
    parser.add_argument('--top', type=int, default=0, help='print the N largest gaps')
    args = parser.parse_args()

    reference = json.loads(args.reference.read_text(encoding='utf-8'))
    best = {row['n']: float(row['L']) for row in reference['puzzles']}
    _, seeds = load_batch(args.input)
    sides = side_list(seeds)

    total = sum(score(sides[n], n) for n in range(1, 1001))
    gaps = []
    for n, target in best.items():
        gap = score(sides[n], n) - score(target, n)
        if gap > args.min_gap:
            gaps.append((gap, n, sides[n], target))
    gaps.sort(reverse=True)

    by_range = defaultdict(lambda: [0, 0.0])
    by_family = defaultdict(lambda: [0, 0.0])
    for gap, n, ours, target in gaps:
        by_range[bucket(n)][0] += 1
        by_range[bucket(n)][1] += gap
        by_family[family(n)][0] += 1
        by_family[family(n)][1] += gap

    report = {
        'csv': str(args.input),
        'ours_total': round(total, 9),
        'reference_puzzles': len(best),
        'reference_total_if_ours_fill_rest': round(
            total - sum(score(sides[n], n) - score(best[n], n) for n in best), 9),
        'targets': len(gaps),
        'gap': round(sum(g[0] for g in gaps), 9),
        'by_range': {k: [v[0], round(v[1], 6)] for k, v in sorted(by_range.items())},
        'by_family': {k: [v[0], round(v[1], 6)] for k, v in by_family.items()},
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.top:
        for gap, n, ours, target in gaps[:args.top]:
            print(f'{n:4d} ours={ours:.9f} target={target:.9f} gap={gap:.6f}')
    if args.targets:
        with args.targets.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow(('n', 'ours', 'target', 'gap'))
            for gap, n, ours, target in sorted(gaps, key=lambda g: g[1]):
                writer.writerow((n, f'{ours:.12f}', f'{target:.12f}', f'{gap:.9f}'))


if __name__ == '__main__':
    main()
