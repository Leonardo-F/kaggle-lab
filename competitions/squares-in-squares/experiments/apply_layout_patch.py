"""Replace complete instances in a self-generated packing submission."""

import argparse
import csv
from pathlib import Path


HEADER = ('id', 'n', 'square_id', 'x', 'y', 'angle')


def read_rows(stream):
    reader = csv.reader(stream)
    if tuple(next(reader, ())) != HEADER:
        raise ValueError('Expected a packing CSV with columns ' + ','.join(HEADER))
    for row in reader:
        if len(row) != len(HEADER):
            raise ValueError(f'Invalid packing row on line {reader.line_num}')
        yield row


def load_patch(path):
    groups = {}
    with path.open(newline='', encoding='utf-8') as stream:
        for row in read_rows(stream):
            row_id, n, square_id = map(int, row[:3])
            group = groups.setdefault(n, {})
            if not 1 <= n <= 1000 or not 0 <= square_id < n:
                raise ValueError(f'Invalid patch instance or square: {n}, {square_id}')
            if row_id != n * (n - 1) // 2 + square_id or square_id in group:
                raise ValueError(f'Invalid or repeated patch row ID: {row_id}')
            group[square_id] = row
    if not groups or any(len(group) != n for n, group in groups.items()):
        raise ValueError('The patch must contain whole instances')
    return groups


def apply_patch(baseline, patch, output):
    groups = load_patch(patch)
    with baseline.open(newline='', encoding='utf-8') as source:
        # Opening exclusively prevents overwriting a solution or leaving a stale receipt.
        with output.open('x', newline='', encoding='utf-8') as destination:
            try:
                writer = csv.writer(destination, lineterminator='\n')
                writer.writerow(HEADER)
                rows = iter(read_rows(source))
                row_id = 0
                for n in range(1, 1001):
                    replacements = groups.get(n)
                    for square_id in range(n):
                        row = next(rows, ())
                        if list(map(int, row[:3])) != [row_id, n, square_id]:
                            raise ValueError(f'Expected baseline row {row_id} for instance {n}')
                        writer.writerow(row if replacements is None else replacements[square_id])
                        row_id += 1
                if next(rows, None) is not None:
                    raise ValueError('Unexpected extra rows in the baseline')
                destination.flush()
            except BaseException:
                destination.close()
                output.unlink()
                raise
    return sorted(groups)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('patch', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        instances = apply_patch(args.baseline, args.patch, args.output)
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(1, f'{error}\n')
    print(f'Replaced {len(instances)} instances: {", ".join(map(str, instances))}')


if __name__ == '__main__':
    main()
