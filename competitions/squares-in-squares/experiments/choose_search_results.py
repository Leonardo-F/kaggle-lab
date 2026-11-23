"""Select per-puzzle improvements from independent runs of our own generators."""

import argparse
from pathlib import Path

from packing_batch import MIN_GAIN, load_batch, write_updates
from rotated_windows import layout_side


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('candidates', type=Path, nargs='+')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output CSV')

    rows, seeds = load_batch(args.baseline)
    sides = {n: layout_side(seed) for n, seed in seeds.items()}
    updates = {}
    for path in args.candidates:
        _, proposals = load_batch(path)
        for n, proposal in proposals.items():
            side = layout_side(proposal)
            if side < sides[n] - MIN_GAIN:
                sides[n], updates[n] = side, proposal
    write_updates(args.output, rows, seeds, updates)


if __name__ == '__main__':
    main()
