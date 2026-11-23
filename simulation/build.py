"""Build a single-file offline launcher from the competition-owned HTML files."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
SQUARE = ROOT / 'competitions/squares-in-squares/simulator/SquarePackingStudio-standalone.html'
SANTA = ROOT / 'competitions/santa-2026/simulator.html'
PYTHON_SOLVER = ROOT / 'competitions/santa-2026/solve.py'
REVIEW = HERE / 'santa-review.json'
OUTPUT = HERE / 'index.html'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    review = json.loads(REVIEW.read_text(encoding='utf-8'))
    if review['python_sha256'] != digest(PYTHON_SOLVER):
        raise ValueError('Santa Python solver changed: review browser solver compatibility and update simulation/santa-review.json before rebuilding.')
    payload = {name: base64.b64encode(path.read_bytes()).decode('ascii')
               for name, path in [('square', SQUARE), ('santa', SANTA)]}
    template = (HERE / 'template.html').read_text(encoding='utf-8')
    return template.replace('/* EMBEDDED_DOCUMENTS */', json.dumps(payload, ensure_ascii=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        content = build()
        if args.check:
            if not args.output.exists() or args.output.read_text(encoding='utf-8') != content:
                raise ValueError('The bundle is out of date. Run python simulation/build.py.')
        else:
            args.output.write_text(content, encoding='utf-8')
            print(args.output)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
