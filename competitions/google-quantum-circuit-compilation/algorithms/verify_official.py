"""Entry point for the three UNMODIFIED verifiers in downloaded Kaggle data.

The call interfaces follow the public official metric v10. No reduced-shot
mode is offered. Integration is pending access to the competition data; a
passing unit test of this wrapper is NOT a passing competition submission.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys

TASKS = ('invsqrt', 'dqi', 'dfthcsos')


def circuit_path(root: Path, stem: str) -> Path:
    paths = [p for suffix in ('.kmb', '.kmx') if (p := root/(stem+suffix)).is_file()]
    if len(paths) != 1:
        raise ValueError(f'{stem}: expected exactly one .kmb or .kmx circuit')
    return paths[0]


def angle_paths(root: Path) -> list[Path]:
    files = [p for p in root.glob('angle_k_*') if p.suffix in ('.kmb', '.kmx')]
    expected = [f'angle_k_{i}' for i in range(len(files))]
    if not files or sorted(p.stem for p in files) != sorted(expected):
        raise ValueError('ANGLE indices must be continuous from 0, with exactly one format per slot')
    by_stem = {p.stem: p for p in files}
    return [by_stem[key] for key in expected]


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(data_root: Path, submission: Path, task: str = 'all', salt: str = '') -> dict:
    verifiers = (data_root/'verifiers').resolve()
    requested = TASKS if task == 'all' else (task,)
    if any(t not in TASKS for t in requested):
        raise ValueError('Unknown task')
    required = [verifiers/t/('verify.py' if t == 'dfthcsos' else f'verify_submission_{t}.py') for t in requested]
    if not all(p.is_file() for p in required):
        raise FileNotFoundError('Official verifiers are missing. Download the competition data after signing in and accepting its rules; point --data-root at the extracted directory.')
    if not submission.is_dir():
        raise FileNotFoundError('Submission directory is missing')

    import kickmix as km
    import numpy as np
    sys.path.insert(0, str(verifiers))
    reports, files = {}, []
    for t in requested:
        name = 'dfthcsos.verify' if t == 'dfthcsos' else f'{t}.verify_submission_{t}'
        module = importlib.import_module(name)
        if not Path(module.__file__).resolve().is_relative_to(verifiers):
            raise ValueError(f'{t}: loaded verifier from a different data root')
        if t == 'dfthcsos':
            paths = angle_paths(submission/t)
            npz = submission/t/'submission.npz'
            with np.load(npz, allow_pickle=False) as archive:
                keys = {'U','W','H2_I','H1_I','Hsym_lower','tree_edges'}
                if set(archive.files) != keys:
                    raise ValueError('submission.npz must contain exactly the six official factorization/tree keys')
                arrays = {k: archive[k].copy() for k in keys}
            tree = arrays.pop('tree_edges')
            circuits = [km.Circuit.from_file(str(p), format=p.suffix[1:]) for p in paths]
            reports[t] = module.verify(circuits, arrays, tree, salt=salt)
            files.extend([*paths, npz])
        else:
            path = circuit_path(submission, t)
            circuit = km.Circuit.from_file(str(path), format=path.suffix[1:])
            spec = module.ProblemSpecInvSqrt.for_n_p(10) if t == 'invsqrt' else module.ProblemSpecDQI.benchmark_instance()
            reports[t] = module.verify(circuit, spec, salt=salt)
            files.append(path)
        cost = float(reports[t]['score'])
        if not math.isfinite(cost) or cost <= 0:
            raise ValueError(f'{t}: no finite positive official cost')
        print(f'{t}: complete local task verification returned cost {cost}',flush=True)
    return {
        'status': 'local-task-verifiers-passed', 'official_circuit_verified': True,
        'scope': list(requested), 'kaggle_scored': False,
        'note': 'Not a replacement for Kaggle metric archive/preflight checks or private-salt scoring.',
        'python': platform.python_version(), 'numpy': np.__version__,
        'kickmix_distribution': importlib.metadata.version('kickmix'),
        'kickmix_module_sha256': fingerprint(Path(km.__file__)),
        'salt': salt,
        'verifiers': {str(p.relative_to(verifiers)): fingerprint(p) for p in sorted(verifiers.rglob('*.py'))},
        'files': {str(p.relative_to(submission)): fingerprint(p) for p in files},
        'results': reports,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--submission', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--task', choices=['all', *TASKS], default='all')
    parser.add_argument('--salt', default='', help='Local reproducibility salt; not the private Kaggle salt')
    args = parser.parse_args()
    report = {'status': 'blocked-or-failed', 'official_circuit_verified': False, 'kaggle_scored': False}
    code = 2
    try:
        report = verify(args.data_root, args.submission, args.task, args.salt)
        code = 0
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, default=str)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('results','files','verifiers')}, indent=2))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
