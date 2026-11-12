"""Strict final-file gate around the unchanged official v20 interval metric.

Checks literal decimal geometry AND the default pandas numeric read/write used
at a Kaggle-style metric boundary. A fallback penalty never counts as accepted.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile

HEADER = ('id', 'n', 'square_id', 'x', 'y', 'angle')
METRIC_SHA256 = 'd269f24b02d5f33fbd2149f76b83414b3b446be4d02776560e04631af3365ccf'
_METRIC = None


def official_metric():
    global _METRIC
    if _METRIC is None:
        path = Path(__file__).resolve().parents[1] / 'vendor' / 'metric_v20.py'
        if hashlib.sha256(path.read_bytes()).hexdigest() != METRIC_SHA256:
            raise ValueError('Official metric snapshot hash mismatch')
        spec = importlib.util.spec_from_file_location('_packing_metric_v20', path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _METRIC = module
    return _METRIC


def read_rows(text: str, complete: bool = False) -> dict[int, list[dict]]:
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if tuple(reader.fieldnames or ()) != HEADER:
        raise ValueError('Expected exactly ' + ','.join(HEADER))
    groups = {}
    for index, row in enumerate(reader):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'Row {index + 2}: malformed CSV')
        if not all(row[k].strip().isascii() and row[k].strip().isdigit() for k in HEADER[:3]):
            raise ValueError(f'Row {index + 2}: ids must be nonnegative integers')
        rid, n, sid = (int(row[k]) for k in HEADER[:3])
        if rid != index or not 1 <= n <= 1000:
            raise ValueError(f'Row {index + 2}: nonsequential id or n outside 1..1000')
        group = groups.setdefault(n, [])
        if sid != len(group) or sid >= n:
            raise ValueError(f'n={n}: square_id must progress from 0 to n-1')
        group.append(row)
    if not groups or any(len(rows) != n for n, rows in groups.items()):
        raise ValueError('Empty file or incomplete puzzle')
    if complete and set(groups) != set(range(1, 1001)):
        raise ValueError('Complete submission requires all 1000 puzzles')
    return groups


def _evaluate(item):
    n, rows = item
    result = official_metric()._evaluate_puzzle_worker((n, rows))
    return {'n': n, 'score': result[1], 'L': result[2], 'reason': result[3]}


def certify_csv(path: Path, complete: bool = False, workers: int = 1) -> dict:
    import mpmath
    import pandas as pd

    if not 1 <= workers <= 32:
        raise ValueError('workers must be 1..32')
    if not hasattr(mpmath.mpf(0), 'man'):
        raise RuntimeError('Install squares-in-squares/requirements.txt (mpmath 1.4.1 required)')
    raw = path.read_bytes()
    literal = read_rows(raw.decode('utf-8-sig'), complete)
    # Deliberately NOT dtype=str: this second route exercises lossy numeric IO.
    transported = read_rows(pd.read_csv(io.BytesIO(raw)).to_csv(index=False), complete)
    work = sorted(literal.items()) + sorted(transported.items())
    if workers == 1:
        results = list(map(_evaluate, work))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_evaluate, work, chunksize=4))
    count = len(literal)
    a, b = results[:count], results[count:]
    accepted_a = sum(r['reason'] == 'ok' and r['L'] is not None for r in a)
    accepted_b = sum(r['reason'] == 'ok' and r['L'] is not None for r in b)
    return {
        'valid': accepted_a == accepted_b == count,
        'metric_version': 20, 'metric_sha256': METRIC_SHA256,
        'csv_sha256': hashlib.sha256(raw).hexdigest(),
        'pandas_version': pd.__version__, 'mpmath_version': mpmath.__version__,
        'rows': sum(map(len, literal.values())), 'puzzles': count,
        'accepted_literal': accepted_a, 'accepted_transport': accepted_b,
        'score_literal': sum(r['score'] for r in a),
        'score_transport': sum(r['score'] for r in b),
        'details': [{'n': x['n'], 'literal': x, 'transport': y} for x, y in zip(a, b)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--complete', action='store_true')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.report.resolve() == args.input.resolve():
        parser.error('--report must differ from --input')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    def write_report(report):
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=args.report.parent, delete=False) as out:
            out.write(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
            temporary = Path(out.name)
        temporary.replace(args.report)
    try:
        input_hash = hashlib.sha256(args.input.read_bytes()).hexdigest()
    except OSError:
        input_hash = None
    # Invalidate a previous receipt before starting a potentially long run.
    pending = {'valid': False, 'status': 'running', 'csv_sha256': input_hash}
    write_report(pending)
    try:
        report = certify_csv(args.input, args.complete, args.workers)
    except Exception as error:
        report = {**pending, 'status': 'failed', 'error': f'{type(error).__name__}: {error}'}
    write_report(report)
    print(json.dumps({k: v for k, v in report.items() if k != 'details'}, indent=2))
    raise SystemExit(0 if report['valid'] else 1)


if __name__ == '__main__':
    main()
