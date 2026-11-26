"""Regression tests for the native build cache and explicit compiler selection.

The logical branches that need two different compilers are exercised with
small wrapper scripts that forward compilation to the real local compiler but
report a different ``--version`` identity.  That keeps the test hermetic while
still exercising the real resolution, probe, rebuild and fingerprint paths.
Tests that need a genuinely different *family* (GCC vs Clang) run in the Linux
GCC acceptance session; here the wrappers only fake identity/version, which is
exactly what the cache comparison must detect.

All builds write into a temporary ``NATIVE_DIR``/``BUILD_DIR`` copy, so the
repository sources and the normal ``experiments/native-build`` cache are never
touched.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import sys

TESTS = Path(__file__).resolve().parent
SRC = TESTS.parent / "src"
sys.path.insert(0, str(SRC))
from algorithms import construct as native_construct
from algorithms.native import build as native_build

NATIVE_DIR = SRC / "algorithms" / "native"
REAL_COMPILER = None
try:  # pragma: no branch - environment-dependent setup
    REAL_COMPILER = native_build.choose_compiler()[0]["path"]
except RuntimeError:  # pragma: no cover - no compiler available
    REAL_COMPILER = None


def write_wrapper(path, real_compiler, version_line):
    """A compiler wrapper that forwards to the real compiler but fakes --version."""
    path.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "{version_line}"; exit 0; fi\n'
        f'exec "{real_compiler}" "$@"\n'
    )
    path.chmod(0o755)
    return path


class NativeBuildTestCase(unittest.TestCase):
    """Isolated native source tree + build dir + environment for each test."""

    def setUp(self):
        if REAL_COMPILER is None:
            self.skipTest("no working C++17 compiler in this environment")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.native_dir = self.root / "native"
        shutil.copytree(NATIVE_DIR, self.native_dir,
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.build_dir = self.root / "build"
        self._patches = mock.patch.multiple(
            native_build,
            NATIVE_DIR=self.native_dir,
            COMPAT_DIR=self.native_dir / "compat",
            BUILD_DIR=self.build_dir,
        )
        self._patches.start()
        self.addCleanup(self._patches.stop)
        self.addCleanup(native_construct.reset_binaries)
        self._saved_env = os.environ.pop(native_build.SANTA_CXX_ENV, None)
        self.addCleanup(self._restore_env)
        self.compiler_a = write_wrapper(
            self.root / "compiler-a", REAL_COMPILER,
            "gcc (fake toolchain A) 14.2.0")
        self.compiler_b = write_wrapper(
            self.root / "compiler-b", REAL_COMPILER,
            "clang (fake toolchain B) 21.0.0")

    def _restore_env(self):
        os.environ.pop(native_build.SANTA_CXX_ENV, None)
        if self._saved_env is not None:
            os.environ[native_build.SANTA_CXX_ENV] = self._saved_env

    def use_compiler(self, compiler):
        if compiler is None:
            os.environ.pop(native_build.SANTA_CXX_ENV, None)
        else:
            os.environ[native_build.SANTA_CXX_ENV] = str(compiler)

    def manifest(self):
        return json.loads((self.build_dir / "manifest.json").read_text())

    def built_at(self):
        return (self.build_dir / "manifest.json").stat().st_mtime_ns


class CompilerCacheTests(NativeBuildTestCase):
    def test_valid_cache_is_reused_without_explicit_compiler(self):
        first = native_build.ensure_built()
        second = native_build.ensure_built()
        self.assertEqual(first, second)
        self.assertEqual(first["compiler"]["source"], "auto")

    def test_explicit_compiler_change_forces_rebuild_both_directions(self):
        self.use_compiler(self.compiler_a)
        first = native_build.ensure_built()
        self.assertEqual(first["compiler"]["path"], str(self.compiler_a.resolve()))
        self.assertEqual(first["compiler"]["source"], "SANTA_CXX")

        time.sleep(0.01)
        self.use_compiler(self.compiler_b)
        second = native_build.ensure_built()
        self.assertEqual(second["compiler"]["path"], str(self.compiler_b.resolve()))
        self.assertEqual(second["compiler"]["version"], "clang (fake toolchain B) 21.0.0")
        self.assertEqual(second["compiler"]["family"], "clang")
        self.assertNotEqual(first["built_at"], second["built_at"])

        time.sleep(0.01)
        self.use_compiler(self.compiler_a)
        third = native_build.ensure_built()
        self.assertEqual(third["compiler"]["path"], str(self.compiler_a.resolve()))
        self.assertEqual(third["compiler"]["family"], "gcc")

    def test_cache_built_automatically_is_replaced_by_explicit_compiler(self):
        auto = native_build.ensure_built()
        self.assertEqual(auto["compiler"]["source"], "auto")
        self.use_compiler(self.compiler_a)
        explicit = native_build.ensure_built()
        self.assertEqual(explicit["compiler"]["path"], str(self.compiler_a.resolve()))
        self.assertNotEqual(auto["compiler"]["path"], explicit["compiler"]["path"])

    def test_missing_explicit_compiler_fails_loudly(self):
        self.use_compiler(self.root / "does-not-exist")
        with self.assertRaisesRegex(RuntimeError, "explicit compiler from SANTA_CXX"):
            native_build.ensure_built()
        self.assertFalse((self.build_dir / "manifest.json").exists())

    def test_unusable_explicit_compiler_fails_loudly(self):
        broken = self.root / "broken-compiler"
        broken.write_text("#!/bin/sh\nexit 3\n")
        broken.chmod(0o755)
        self.use_compiler(broken)
        with self.assertRaisesRegex(RuntimeError, "explicit compiler from SANTA_CXX"):
            native_build.ensure_built()

    def test_explicit_compiler_is_used_when_another_reason_invalidates_cache(self):
        self.use_compiler(self.compiler_a)
        native_build.ensure_built()
        # Invalidate through a source change while an explicit compiler is set.
        target = self.native_dir / "constructor_wide.cpp"
        target.write_text(target.read_text() + "\n// cache invalidation test\n")
        self.use_compiler(self.compiler_b)
        rebuilt = native_build.ensure_built()
        self.assertEqual(rebuilt["compiler"]["path"], str(self.compiler_b.resolve()))
        self.assertEqual(rebuilt["compiler"]["source"], "SANTA_CXX")

    def test_source_change_forces_rebuild(self):
        first = native_build.ensure_built()
        target = self.native_dir / "constructor_mitm.cpp"
        target.write_text(target.read_text() + "\n// source change test\n")
        time.sleep(0.01)
        second = native_build.ensure_built()
        self.assertNotEqual(first["sources"]["constructor_mitm.cpp"],
                            second["sources"]["constructor_mitm.cpp"])
        self.assertNotEqual(first["built_at"], second["built_at"])

    def test_binary_tampering_forces_rebuild(self):
        manifest = native_build.ensure_built()
        binary = Path(manifest["binaries"]["constructor_wide"]["path"])
        original_hash = manifest["binaries"]["constructor_wide"]["sha256"]
        binary.write_bytes(binary.read_bytes() + b"\x00tampered")
        time.sleep(0.01)
        rebuilt = native_build.ensure_built()
        self.assertEqual(rebuilt["binaries"]["constructor_wide"]["sha256"], original_hash)
        self.assertNotIn(b"tampered", binary.read_bytes()[-32:])

    def test_force_rebuilds_even_when_manifest_is_valid(self):
        native_build.ensure_built()
        before = self.built_at()
        time.sleep(0.01)
        native_build.ensure_built(force=True)
        self.assertNotEqual(before, self.built_at())

    def test_built_info_respects_explicit_compiler(self):
        self.use_compiler(self.compiler_a)
        native_build.ensure_built()
        self.assertEqual(native_build.built_info()["compiler"]["path"],
                         str(self.compiler_a.resolve()))
        self.use_compiler(self.compiler_b)
        with self.assertRaisesRegex(RuntimeError, "changed"):
            native_build.built_info()

    def test_manifest_validation_rejects_mutated_fields(self):
        manifest = native_build.ensure_built()
        self.assertTrue(native_build._manifest_matches(manifest))
        mutated_cases = {
            "schema": dict(manifest, schema=1),
            "flags": dict(manifest, flags=["-O2", "-std=c++17"]),
            "sources": dict(manifest, sources=dict(manifest["sources"],
                                                   **{"constructor_wide.cpp": "0" * 64})),
            "compat": dict(manifest, compat_include="yes"),
            "compiler_path": dict(manifest, compiler=dict(manifest["compiler"], path="/bin/false")),
            "compiler_version": dict(manifest, compiler=dict(manifest["compiler"], version="other")),
            "binary_path": dict(manifest, binaries=dict(manifest["binaries"],
                                                        constructor_wide={"path": "/tmp/not-there",
                                                                          "sha256": "0" * 64})),
            "binary_hash": dict(manifest, binaries=dict(manifest["binaries"],
                                                        constructor_wide={"path": manifest["binaries"]["constructor_wide"]["path"],
                                                                          "sha256": "0" * 64})),
        }
        for name, mutated in mutated_cases.items():
            with self.subTest(case=name):
                self.assertFalse(native_build._manifest_matches(mutated), name)

    def test_explicit_compiler_mismatch_invalidates_manifest(self):
        self.use_compiler(self.compiler_a)
        manifest = native_build.ensure_built()
        info_b = native_build._explicit_compiler_info(str(self.compiler_b))
        self.assertFalse(native_build._manifest_matches(manifest, info_b))
        info_a = native_build._explicit_compiler_info(str(self.compiler_a))
        self.assertTrue(native_build._manifest_matches(manifest, info_a))


class ConstructBinaryCacheTests(NativeBuildTestCase):
    def test_metadata_junk_is_not_a_build_source(self):
        junk_dir = self.native_dir / "compat" / "bits"
        (junk_dir / "._stdc++.h").write_bytes(b"\x00\x05\x16\x07junk")
        (self.native_dir / "compat" / "._bits").write_bytes(b"\x00\x05\x16\x07junk")
        (self.native_dir / ".DS_Store").write_bytes(b"junk")
        sources = native_build.source_files()
        self.assertEqual(sorted(sources), [
            "build.py", "compat/bits/stdc++.h", "constructor_cf.cpp",
            "constructor_joint.cpp", "constructor_mitm.cpp", "constructor_order_cf.cpp",
            "constructor_order_fast.cpp", "constructor_pressure.cpp", "constructor_wide.cpp",
        ])
        native_build.ensure_built()
        manifest = self.manifest()
        self.assertEqual(sorted(manifest["sources"]), [
            "build.py", "compat/bits/stdc++.h", "constructor_cf.cpp",
            "constructor_joint.cpp", "constructor_mitm.cpp", "constructor_order_cf.cpp",
            "constructor_order_fast.cpp", "constructor_pressure.cpp", "constructor_wide.cpp",
        ])

    def test_binary_path_cache_invalidates_after_rebuild(self):
        native_build.ensure_built()
        calls = []
        real_binaries = native_build.binaries

        def counting_binaries():
            calls.append(1)
            return real_binaries()

        with mock.patch.object(native_build, "binaries", counting_binaries):
            first = native_construct.binary_paths()
            second = native_construct.binary_paths()
            self.assertEqual(len(calls), 1)
            self.assertEqual(first, second)
            time.sleep(0.01)
            native_build.ensure_built(force=True)
            third = native_construct.binary_paths()
            self.assertEqual(len(calls), 2)
            manifest = json.loads((self.build_dir / "manifest.json").read_text())
            self.assertEqual({name: str(path) for name, path in third.items()},
                             {name: info["path"] for name, info in manifest["binaries"].items()})


class CheckpointCompilerFingerprintTests(NativeBuildTestCase):
    def test_compiler_change_blocks_checkpoint_resume(self):
        import csv
        import checkpoint as checkpoint_engine

        puzzles = self.root / "puzzles.csv"
        with puzzles.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("id", "starting_values", "targets", "value_limit", "registers"))
            writer.writerow(("a", "[3]", "[9,27,81]", "100", "48"))
        checkpoint = self.root / "run.sqlite"
        output = self.root / "answer.csv"

        self.use_compiler(self.compiler_a)
        checkpoint_engine.run_checkpoint(puzzles, output, checkpoint, "v9",
                                         jobs=1, stop_after=0)
        self.assertFalse(output.exists())

        self.use_compiler(self.compiler_b)
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            checkpoint_engine.run_checkpoint(puzzles, output, checkpoint, "v9",
                                             jobs=1, resume=True)


if __name__ == "__main__":
    unittest.main()
