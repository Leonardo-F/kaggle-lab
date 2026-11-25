import base64
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / 'web' / 'build' / 'build.py'
REVIEW = ROOT / 'web' / 'build' / 'santa-review.json'
BUNDLE = ROOT / 'web' / 'simulators.html'

spec = importlib.util.spec_from_file_location('santa_bundle_build', BUILDER)
build_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_mod)

HISTORICAL = ['v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7', 'v8']


def make_santa(root, version='v8', versions=HISTORICAL, algorithms=('__init__.py', 'common.py', 'solver.py')):
    """A minimal Santa tree: only two real algorithm files plus the CLI files."""
    santa = Path(root) / 'santa'
    src = santa / 'src'
    (src / 'algorithms').mkdir(parents=True)
    (src / 'graph_solver.py').write_text(f'DEFAULT_VERSION = {version!r}\n', encoding='utf-8')
    (src / 'checkpoint.py').write_text('"""checkpoint"""\n', encoding='utf-8')
    (src / 'verify.py').write_text('"""verify"""\n', encoding='utf-8')
    for name in algorithms:
        source = (f'SOLVER_VERSION = {version!r}\n' if name == 'solver.py' else f'# {name}\n')
        (src / 'algorithms' / name).write_text(source, encoding='utf-8')
    simulator = src / 'simulator.html'
    simulator.write_text(
        '<div id="replay-files" data-versions="%s"><label>V1</label></div>' % ','.join(versions),
        encoding='utf-8',
    )
    square = santa / 'square.html'
    square.write_text('<html><body>square</body></html>', encoding='utf-8')
    return src, simulator, square


def reviewed(src, simulator, version=None, versions=None):
    hashes, detected, replay = build_mod.review_state(src, simulator)
    return {
        'schema_version': 2,
        'solver': {'current_version': version or detected,
                   'source_sha256': dict(hashes)},
        'independent_replay': {'versions': list(versions or replay)},
    }


class ReviewDecouplingTests(unittest.TestCase):
    def test_layout_with_only_common_and_solver_keeps_v1_to_v8(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, simulator, _ = make_santa(tmp)
            hashes, version, replay = build_mod.review_state(src, simulator)
            self.assertEqual(version, 'v8')
            self.assertEqual(sorted(hashes), [
                'algorithms/__init__.py', 'algorithms/common.py', 'algorithms/solver.py',
                'checkpoint.py', 'graph_solver.py', 'verify.py',
            ])
            self.assertEqual(replay, HISTORICAL)
            build_mod.validate_review(reviewed(src, simulator), hashes, version, replay, simulator)

    def test_changed_added_and_deleted_sources_invalidate_the_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, simulator, _ = make_santa(tmp)
            review = reviewed(src, simulator)
            hashes, version, replay = build_mod.review_state(src, simulator)

            (src / 'algorithms' / 'common.py').write_text('# changed\n', encoding='utf-8')
            changed, _, _ = build_mod.review_state(src, simulator)
            with self.assertRaisesRegex(build_mod.BuildError, 'changed files: algorithms/common.py'):
                build_mod.validate_review(review, changed, version, replay, simulator)

            (src / 'algorithms' / 'extra.py').write_text('# new\n', encoding='utf-8')
            added, _, _ = build_mod.review_state(src, simulator)
            with self.assertRaisesRegex(build_mod.BuildError, 'new files not reviewed: algorithms/extra.py'):
                build_mod.validate_review(review, added, version, replay, simulator)

            review = reviewed(src, simulator)
            (src / 'algorithms' / 'extra.py').unlink()
            deleted, _, _ = build_mod.review_state(src, simulator)
            with self.assertRaisesRegex(build_mod.BuildError, 'missing from review: algorithms/extra.py'):
                build_mod.validate_review(review, deleted, version, replay, simulator)

    def test_release_identifier_must_match_the_reviewed_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, simulator, _ = make_santa(tmp)
            hashes, version, replay = build_mod.review_state(src, simulator)
            review = reviewed(src, simulator, version='v7')
            with self.assertRaisesRegex(build_mod.BuildError, "release is 'v8'"):
                build_mod.validate_review(review, hashes, version, replay, simulator)

    def test_disagreeing_release_constants_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, simulator, _ = make_santa(tmp)
            (src / 'algorithms' / 'solver.py').write_text('SOLVER_VERSION = "v9"\n', encoding='utf-8')
            with self.assertRaisesRegex(build_mod.BuildError, 'release identifiers disagree'):
                build_mod.solver_version(src)

    def test_replay_slots_are_not_derived_from_python_file_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, simulator, _ = make_santa(tmp)
            (src / 'algorithms' / 'v1.py').write_text('# legacy name\n', encoding='utf-8')
            hashes, version, replay = build_mod.review_state(src, simulator)
            # A file named v1.py is just another reviewed source file; the slot
            # list still comes from the simulator/review pair.
            self.assertIn('algorithms/v1.py', hashes)
            self.assertEqual(replay, HISTORICAL)

    def test_simulator_slots_must_match_the_reviewed_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, simulator, _ = make_santa(tmp)
            review = reviewed(src, simulator)
            hashes, version, replay = build_mod.review_state(src, simulator)
            simulator.write_text(
                '<div id="replay-files" data-versions="v1,v2,v3,v4,v5,v6,v7"></div>',
                encoding='utf-8',
            )
            shorter = build_mod.parse_replay_versions(simulator.read_text(encoding='utf-8'))
            with self.assertRaisesRegex(build_mod.BuildError, 'do not match the simulator slots'):
                build_mod.validate_review(review, hashes, version, shorter, simulator)

    def test_duplicate_or_invalid_slots_are_rejected(self):
        with self.assertRaisesRegex(build_mod.BuildError, 'duplicates'):
            build_mod.validate_slots(['v1', 'v1'], 'review')
        with self.assertRaisesRegex(build_mod.BuildError, 'invalid replay version'):
            build_mod.validate_slots(['v1', 'has space'], 'review')
        with self.assertRaisesRegex(build_mod.BuildError, 'non-empty list'):
            build_mod.validate_slots([], 'review')

    def test_refresh_keeps_historical_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, simulator, _ = make_santa(tmp)
            review = reviewed(src, simulator)
            original = review['solver']['source_sha256']['algorithms/common.py']
            (src / 'algorithms' / 'common.py').write_text('# touched\n', encoding='utf-8')
            hashes, version, replay = build_mod.review_state(src, simulator)
            updated = build_mod.refreshed_review(review, hashes, version)
            self.assertEqual(updated['independent_replay']['versions'], HISTORICAL)
            self.assertEqual(updated['solver']['source_sha256'], hashes)
            self.assertNotEqual(updated['solver']['source_sha256']['algorithms/common.py'], original)
            self.assertEqual(review['solver']['source_sha256']['algorithms/common.py'], original)

    def test_explicit_refresh_migrates_legacy_review_and_keeps_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, simulator, _ = make_santa(tmp)
            review_path = Path(tmp) / 'review.json'
            review_path.write_text(json.dumps({
                'independent_replay': {'versions': HISTORICAL, 'source_sha256': {'stale.py': '0' * 64}},
            }), encoding='utf-8')
            build_mod.refresh(review_path=review_path, santa_src=src, simulator_path=simulator)
            refreshed = json.loads(review_path.read_text(encoding='utf-8'))
            self.assertEqual(refreshed['schema_version'], 2)
            self.assertEqual(refreshed['independent_replay']['versions'], HISTORICAL)
            self.assertEqual(refreshed['solver']['current_version'], 'v8')
            self.assertNotIn('stale.py', refreshed['solver']['source_sha256'])
            build_mod.validate_review(refreshed, *build_mod.review_state(src, simulator)[:3], simulator)

    def test_normal_build_does_not_rewrite_the_review_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, simulator, square = make_santa(tmp)
            review_path = Path(tmp) / 'review.json'
            review_path.write_text(json.dumps(reviewed(src, simulator), indent=2) + '\n', encoding='utf-8')
            before = review_path.read_bytes()
            output = Path(tmp) / 'bundle.html'
            build_mod.build(review_path=review_path, santa_src=src, simulator_path=simulator,
                            square_path=square, output_path=output)
            output.write_text(build_mod.build(review_path=review_path, santa_src=src,
                                              simulator_path=simulator, square_path=square), encoding='utf-8')
            self.assertEqual(review_path.read_bytes(), before)


class BundleTests(unittest.TestCase):
    def test_generated_bundle_contains_original_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'bundle.html'
            result = subprocess.run([sys.executable, str(BUILDER), '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            content = output.read_text(encoding='utf-8')
            self.assertIn('正方形装箱', content)
            self.assertIn('Santa 2026', content)
            self.assertIn('srcdoc', content)
            embedded = json.loads(re.search(r'const documents = (.*);', content).group(1))
            for key, name in [('square', 'competitions/squares-in-squares/simulator/SquarePackingStudio-standalone.html'),
                              ('santa', 'competitions/santa-2026/src/simulator.html')]:
                self.assertEqual(base64.b64decode(embedded[key]), (ROOT / name).read_bytes())

    def test_checked_in_bundle_is_up_to_date(self):
        result = subprocess.run([sys.executable, str(BUILDER), '--check'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_checked_in_review_matches_repository_sources(self):
        review = build_mod.load_review(REVIEW)
        hashes, version, replay = build_mod.review_state(ROOT / 'competitions/santa-2026/src')
        build_mod.validate_review(review, hashes, version, replay)
        self.assertEqual(review['solver']['current_version'], version)
        self.assertNotIn('score', review)
        self.assertNotIn('best', review)

    def test_stale_review_fails_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, simulator, square = make_santa(tmp)
            review_path = Path(tmp) / 'review.json'
            review_path.write_text(json.dumps(reviewed(src, simulator), indent=2), encoding='utf-8')
            (src / 'verify.py').write_text('# changed\n', encoding='utf-8')
            with self.assertRaisesRegex(build_mod.BuildError, 'changed files: verify.py'):
                build_mod.build(review_path=review_path, santa_src=src, simulator_path=simulator,
                                square_path=square)


if __name__ == '__main__':
    unittest.main()
