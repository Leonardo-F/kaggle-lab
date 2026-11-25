"""Build a single-file offline launcher from the competition-owned HTML files."""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
SQUARE = ROOT / 'competitions/squares-in-squares/simulator/SquarePackingStudio-standalone.html'
SANTA = ROOT / 'competitions/santa-2026/src/simulator.html'
REVIEW = HERE / 'santa-review.json'
OUTPUT = HERE / 'index.html'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    review = json.loads(REVIEW.read_text(encoding='utf-8'))
    review_independent_replay(review["independent_replay"])
    payload = {name: base64.b64encode(path.read_bytes()).decode('ascii')
               for name, path in [('square', SQUARE), ('santa', SANTA)]}
    template = (HERE / 'template.html').read_text(encoding='utf-8')
    return template.replace('/* EMBEDDED_DOCUMENTS */', json.dumps(payload, ensure_ascii=True))


def review_independent_replay(review):
    santa = SANTA.parent
    algorithms = sorted((santa / "algorithms").glob("*.py"))
    files = [santa / "graph_solver.py", santa / "verify.py", *algorithms]
    hashes = {path.relative_to(santa).as_posix(): digest(path) for path in files}
    versions = [path.stem for path in algorithms if re.fullmatch(r"v[1-5]", path.stem)]
    simulator = SANTA.read_text(encoding="utf-8")
    mapping = re.search(r'id="replay-files" data-versions="([^"]+)"', simulator)
    if hashes != review["source_sha256"] or versions != review["versions"]:
        raise ValueError("Santa independent solver changed: review CSV replay and update santa-review.json.")
    if not mapping or mapping[1].split(",") != versions:
        raise ValueError("Santa replay version choices do not match the Python files.")


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
