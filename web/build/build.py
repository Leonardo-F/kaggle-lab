"""Build a single-file offline launcher from the competition-owned HTML files.

The Santa review file (``santa-review.json``) keeps three independent things:

* ``solver`` – the current CLI release identifier and the SHA-256 of every
  source file that takes part in solving, native construction or verification;
* ``independent_replay`` – the historical CSV replay slots shown by the
  simulator, which are a property of the recorded results, not of the Python
  files that happen to exist today;
* the best verified score, which lives only in
  ``competitions/santa-2026/submissions/latest.json``.

``--refresh-santa-review`` is the only way to accept new source hashes.  It
never changes the replay slot list and it never runs automatically.
"""
import argparse
import ast
import base64
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SQUARE = ROOT / 'competitions/squares-in-squares/simulator/SquarePackingStudio-standalone.html'
SANTA = ROOT / 'competitions/santa-2026/src/simulator.html'
REVIEW = HERE / 'santa-review.json'
OUTPUT = HERE.parent / 'simulators.html'
SCHEMA_VERSION = 2
SOLVER_FILES = ('graph_solver.py', 'checkpoint.py', 'verify.py')
SOLVER_SUFFIXES = ('.py', '.cpp', '.h', '.hpp')
# The release identifier is single-sourced in the solver module; the CLI
# imports it at runtime and must not declare a second literal.
VERSION_SOURCES = (('algorithms/solver.py', 'SOLVER_VERSION'),)
VERSION_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$')
SLOT_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$')


class BuildError(RuntimeError):
    """An input is missing, inconsistent or has an unreviewed change."""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def solver_sources(santa_src):
    """Every file that is part of the current Santa solver, in stable order."""
    algorithms = santa_src / 'algorithms'
    if not algorithms.is_dir():
        raise BuildError(f'Santa algorithm directory is missing: {algorithms}')
    files = [santa_src / name for name in SOLVER_FILES]
    files.extend(sorted(path for path in algorithms.rglob('*')
                        if path.is_file() and path.suffix in SOLVER_SUFFIXES
                        and '__pycache__' not in path.parts))
    missing = [path for path in files if not path.is_file()]
    if missing:
        raise BuildError('Santa solver files are missing: ' + ', '.join(
            path.relative_to(santa_src).as_posix() for path in missing))
    return files


def module_constant(path, name):
    """Read a module-level string constant without importing or running the module."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except SyntaxError as exc:
        raise BuildError(f'cannot parse {path}: {exc}') from exc
    for node in tree.body:
        value = None
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            value = node.value
        if value is not None:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
            raise BuildError(f'{path.name} {name} must be a string literal')
    return None


def solver_version(santa_src):
    """The single public release identifier declared by the solver entry points."""
    found = {}
    for relative, constant in VERSION_SOURCES:
        path = santa_src / relative
        if not path.is_file():
            continue
        value = module_constant(path, constant)
        if value is not None:
            found[relative] = value
    if not found:
        names = ' or '.join(f'{rel}:{const}' for rel, const in VERSION_SOURCES)
        raise BuildError(f'cannot find a solver release identifier ({names})')
    version = next(iter(found.values()))
    if not VERSION_PATTERN.fullmatch(version):
        raise BuildError(f'invalid solver release identifier: {version!r}')
    return version


def parse_replay_versions(simulator_text):
    tag = re.search(r'<div[^>]*id="replay-files"[^>]*>', simulator_text)
    match = tag and re.search(r'data-versions="([^"]*)"', tag.group(0))
    if not match:
        raise BuildError('Santa simulator has no #replay-files[data-versions] list')
    return [item.strip() for item in match.group(1).split(',')]


def validate_slots(versions, source):
    if not isinstance(versions, list) or not versions:
        raise BuildError(f'{source} replay versions must be a non-empty list')
    if len(set(versions)) != len(versions):
        raise BuildError(f'{source} replay versions contain duplicates')
    for version in versions:
        if not isinstance(version, str) or not SLOT_PATTERN.fullmatch(version):
            raise BuildError(f'{source} has an invalid replay version label: {version!r}')


def load_review(path):
    try:
        review = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise BuildError(f'Santa review file is missing: {path}') from exc
    except json.JSONDecodeError as exc:
        raise BuildError(f'Santa review file is not valid JSON: {path}: {exc}') from exc
    if not isinstance(review, dict) or review.get('schema_version') != SCHEMA_VERSION:
        raise BuildError(
            f'{path.name} must use schema_version {SCHEMA_VERSION}; regenerate it with '
            'python web/build/build.py --refresh-santa-review after reviewing the replay.'
        )
    solver = review.get('solver')
    if not isinstance(solver, dict) or not isinstance(solver.get('source_sha256'), dict):
        raise BuildError(f'{path.name} is missing solver.source_sha256')
    replay = review.get('independent_replay')
    if not isinstance(replay, dict):
        raise BuildError(f'{path.name} is missing independent_replay')
    validate_slots(replay.get('versions'), path.name)
    return review


def validate_review(review, hashes, version, replay_versions, simulator_path=SANTA):
    """Fail unless the review file describes exactly the current inputs."""
    solver = review['solver']
    if solver.get('current_version') != version:
        raise BuildError(
            f'Santa solver release is {version!r} but {REVIEW.name} reviewed '
            f'{solver.get("current_version")!r}; review the release and run '
            'python web/build/build.py --refresh-santa-review'
        )
    expected = solver['source_sha256']
    missing = sorted(set(expected) - set(hashes))
    extra = sorted(set(hashes) - set(expected))
    changed = sorted(name for name in set(expected) & set(hashes) if expected[name] != hashes[name])
    if missing or extra or changed:
        details = []
        if missing:
            details.append('missing from review: ' + ', '.join(missing))
        if extra:
            details.append('new files not reviewed: ' + ', '.join(extra))
        if changed:
            details.append('changed files: ' + ', '.join(changed))
        raise BuildError(
            'Santa solver sources changed since the last review (' + '; '.join(details) + '). '
            'Replay the affected versions, run the Santa tests, then run '
            'python web/build/build.py --refresh-santa-review.'
        )
    if review['independent_replay']['versions'] != replay_versions:
        raise BuildError(
            f'{REVIEW.name} independent_replay.versions={review["independent_replay"]["versions"]} '
            f'do not match the simulator slots {replay_versions} in {simulator_path.name}.'
        )


def review_state(santa_src, simulator_path=SANTA):
    """Hash current sources and read the reviewed slot list from the simulator."""
    hashes = {path.relative_to(santa_src).as_posix(): digest(path)
              for path in solver_sources(santa_src)}
    version = solver_version(santa_src)
    replay = parse_replay_versions(simulator_path.read_text(encoding='utf-8'))
    validate_slots(replay, simulator_path.name)
    return hashes, version, replay


def refreshed_review(review, hashes, version):
    """Return a reviewed copy with new hashes; historical slots are untouched."""
    updated = copy.deepcopy(review)
    updated['schema_version'] = SCHEMA_VERSION
    updated['solver'] = {
        'current_version': version,
        'source_sha256': {name: hashes[name] for name in sorted(hashes)},
    }
    return updated


def build(review_path=REVIEW, santa_src=SANTA.parent, simulator_path=SANTA,
          square_path=SQUARE, output_path=OUTPUT):
    review = load_review(review_path)
    hashes, version, replay = review_state(santa_src, simulator_path)
    validate_review(review, hashes, version, replay, simulator_path)
    payload = {name: base64.b64encode(path.read_bytes()).decode('ascii')
               for name, path in [('square', square_path), ('santa', simulator_path)]}
    template = (HERE / 'template.html').read_text(encoding='utf-8')
    return template.replace('/* EMBEDDED_DOCUMENTS */', json.dumps(payload, ensure_ascii=True))


def refresh(review_path=REVIEW, santa_src=SANTA.parent, simulator_path=SANTA):
    """Accept current hashes after manual review; never touch the replay slots."""
    try:
        raw = json.loads(review_path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise BuildError(f'Santa review file is missing: {review_path}') from exc
    except json.JSONDecodeError as exc:
        raise BuildError(f'Santa review file is not valid JSON: {review_path}: {exc}') from exc
    replay_block = raw.get('independent_replay') if isinstance(raw, dict) else None
    versions = replay_block.get('versions') if isinstance(replay_block, dict) else None
    validate_slots(versions, str(review_path))
    if raw.get('schema_version') != SCHEMA_VERSION:
        print(f'migrating {review_path.name} to schema_version {SCHEMA_VERSION}')
    review = {
        'schema_version': SCHEMA_VERSION,
        'solver': {},
        'independent_replay': {'versions': versions},
    }
    hashes, version, replay = review_state(santa_src, simulator_path)
    updated = refreshed_review(review, hashes, version)
    validate_review(updated, hashes, version, replay, simulator_path)
    review_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'refreshed {review_path} for solver {version} and {len(hashes)} source files')
    print('replay slots kept: ' + ', '.join(updated['independent_replay']['versions']))
    print('now run the Santa tests, then python web/build/build.py')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='fail if the bundle is stale')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--refresh-santa-review', action='store_true',
                        help='accept the current solver hashes after manual review')
    args = parser.parse_args(argv)
    try:
        if args.refresh_santa_review:
            refresh()
            return 0
        content = build(output_path=args.output)
        if args.check:
            if not args.output.exists() or args.output.read_text(encoding='utf-8') != content:
                raise BuildError('the bundle is out of date; run python web/build/build.py')
        else:
            args.output.write_text(content, encoding='utf-8')
            print(args.output)
        return 0
    except (OSError, BuildError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
