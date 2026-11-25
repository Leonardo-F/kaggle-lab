import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
import graph_solver
from algorithms import construct as native_construct
from algorithms.construct import parse_graph, puzzle_numbers
from algorithms.native import build as native_build
from algorithms.solver import DEFAULT_CONFIG, STAGES, SOLVER_VERSION, solve

FROZEN_CPP = {
    "constructor_wide.cpp": "99a05ebca2afb190ad90662351392a7784c70b1b67259dfa6ade26645f459ee3",
    "constructor_mitm.cpp": "14b3885b1fec5d7224c99bf5417c101fd6b00cf28174ba0d8cf66f6638dbb3cd",
}


class SolverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_build.ensure_built()
        native_construct.reset_binaries()

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.puzzles = self.root / "puzzles.csv"
        self.puzzles.write_text(
            'id,starting_values,targets,value_limit,registers\n'
            'test,[3],"[9,27,81]",100,48\n'
        )
        self.output = self.root / "answer.csv"

    def row(self, puzzle_id="test", starting="[3]", targets="[9,27,81]", limit=100, registers=48):
        return {"id": puzzle_id, "starting_values": starting, "targets": targets,
                "value_limit": str(limit), "registers": str(registers)}

    def run_cli(self, *extra):
        return subprocess.run(
            [sys.executable, str(SRC / "graph_solver.py"), str(self.puzzles),
             "--jobs", "1", "--output", str(self.output), *extra],
            cwd=self.root, capture_output=True, text=True,
        )

    def read_program(self):
        with self.output.open(newline="") as stream:
            return json.loads(next(csv.DictReader(stream))["program"])

    def test_default_entry_solves_three_steps(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"version": "v9"', result.stdout)
        self.assertIn('"validated": 1', result.stdout)
        self.assertEqual(len(self.read_program()), 3)

    def test_explicit_v9_alias_matches_default(self):
        self.assertEqual(self.run_cli().returncode, 0)
        default = self.output.read_bytes()
        self.output.unlink()
        result = self.run_cli("--version", "v9")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), default)

    def test_historical_versions_point_to_their_worktree_commits(self):
        for version, revision in (("v7", graph_solver.LEGACY_REVISION),
                                  ("v8", graph_solver.HISTORICAL_REVISIONS["v8"])):
            with self.subTest(version=version):
                result = self.run_cli("--version", version)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(revision, result.stderr)
                self.assertIn("worktree", result.stderr)
                self.assertIn(f"--version {version}", result.stderr)

    def test_unknown_version_has_no_misleading_worktree_command(self):
        result = self.run_cli("--version", "v10")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown solver version", result.stderr)
        self.assertNotIn("git worktree add", result.stderr)
        self.assertNotIn("worktree add --detach", result.stderr)

    def test_read_only_puzzle_csv(self):
        self.puzzles.chmod(0o444)
        self.addCleanup(self.puzzles.chmod, 0o644)
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.read_program()), 3)

    def test_removed_legacy_options_are_rejected(self):
        for option in (["--rounds", "180"], ["--portfolio", "3"], ["--path-rounds", "400"],
                       ["--retain-v6-graphs"], ["--no-schedule"], ["--no-extra"]):
            with self.subTest(option=option):
                result = self.run_cli(*option)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unrecognized arguments", result.stderr)

    def test_rejects_reference_option(self):
        result = self.run_cli("--reference", "history.csv")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized arguments: --reference", result.stderr)

    def test_solve_returns_frozen_stage_and_route_metrics(self):
        pid, program, metrics = solve(self.row())
        self.assertEqual(pid, "test")
        self.assertEqual(len(program), 3)
        self.assertEqual(metrics["v9final"], len(program))
        self.assertGreaterEqual(metrics["v9_stage1"], metrics["v9final"])
        for stage in STAGES:
            self.assertIn(stage, metrics)
            self.assertIs(type(metrics[stage]), int)
        self.assertIs(type(metrics["nodes"]), int)
        self.assertIs(type(metrics["schedule_attempts"]), int)
        self.assertEqual([entry["config"] for entry in metrics["routes"]],
                         [list(route) for route in DEFAULT_CONFIG["stage1_routes"]])
        for entry in metrics["routes"]:
            self.assertIsNone(entry["error"])
            self.assertIs(type(entry["score"]), int)
            self.assertIs(type(entry["nodes"]), int)
        self.assertEqual(set(DEFAULT_CONFIG), {
            "stage1_routes", "compile_tries", "compile_seed", "polish_rounds",
            "schedule_seed", "schedule_tries", "schedule_top", "schedule_modes",
        })
        self.assertEqual(DEFAULT_CONFIG["stage1_routes"],
                         (("constructor_wide_polish", 6, 3),
                          ("constructor_wide_polish", 6, 4),
                          ("constructor_mitm_polish", 6, 3),
                          ("constructor_mitm_polish", 6, 4)))
        self.assertEqual((DEFAULT_CONFIG["compile_seed"], DEFAULT_CONFIG["compile_tries"],
                          DEFAULT_CONFIG["polish_rounds"], DEFAULT_CONFIG["schedule_seed"],
                          DEFAULT_CONFIG["schedule_tries"], DEFAULT_CONFIG["schedule_top"],
                          DEFAULT_CONFIG["schedule_modes"]), (919, 8, 2, 202609, 32, 12, 6))

    def test_solve_is_deterministic(self):
        first = solve(self.row())
        second = solve(self.row())
        self.assertEqual(first[1], second[1])
        self.assertEqual(first[2], second[2])

    def test_zero_step_when_targets_are_starting_values(self):
        row = self.row(targets="[9,27,81]", starting="[9,27,81]")
        pid, program, metrics = solve(row)
        self.assertEqual(program, [])
        self.assertEqual((metrics["v9_stage1"], metrics["v9final"]), (0, 0))

    def test_jobs_one_and_two_are_identical(self):
        self.assertEqual(self.run_cli("--jobs", "1").returncode, 0)
        single = self.output.read_bytes()
        self.output.unlink()
        result = subprocess.run(
            [sys.executable, str(SRC / "graph_solver.py"), str(self.puzzles),
             "--jobs", "2", "--output", str(self.output)],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), single)

    def test_only_functional_modules_and_native_kernels_remain(self):
        algorithms = SRC / "algorithms"
        names = sorted(path.stem for path in algorithms.glob("*.py"))
        self.assertEqual(names, ["__init__", "common", "construct", "graph",
                                 "rewrite", "schedule", "solver"])
        self.assertFalse(list(algorithms.glob("v[0-9]*.py")))
        native = algorithms / "native"
        self.assertEqual(sorted(path.name for path in native.glob("*.cpp")),
                         sorted(FROZEN_CPP))
        self.assertTrue((native / "build.py").is_file())
        self.assertTrue((native / "compat" / "bits" / "stdc++.h").is_file())

    def test_frozen_native_sources_are_byte_identical(self):
        import hashlib
        native = SRC / "algorithms" / "native"
        for name, expected in FROZEN_CPP.items():
            digest = hashlib.sha256((native / name).read_bytes()).hexdigest()
            self.assertEqual(digest, expected, name)

    def test_native_build_manifest_is_reproducible_and_bound(self):
        first = native_build.ensure_built()
        rebuilt = native_build.ensure_built(force=True)
        for kernel in native_build.KERNELS:
            self.assertEqual(first["binaries"][kernel]["sha256"],
                             rebuilt["binaries"][kernel]["sha256"])
        self.assertIn("build.py", rebuilt["sources"])
        self.assertIn("constructor_wide.cpp", rebuilt["sources"])
        self.assertIn("compat/bits/stdc++.h", rebuilt["sources"])
        self.assertEqual(rebuilt["flags"], ["-O3", "-std=c++17"])
        self.assertTrue(Path(rebuilt["binaries"]["constructor_wide"]["path"]).is_file())

    def test_rejects_duplicate_ids(self):
        self.puzzles.write_text(
            'id,starting_values,targets,value_limit,registers\n'
            'a,[3],"[9]",100,48\n'
            'a,[3],"[9]",100,48\n'
        )
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unique puzzle IDs", result.stderr)

    def test_stage1_failure_is_reported_not_faked(self):
        with mock.patch("algorithms.solver.construct",
                        side_effect=ValueError("native constructor failed")):
            with self.assertRaisesRegex(RuntimeError, "no legal candidate"):
                solve(self.row())

    def test_invalid_metrics_are_rejected_by_checkpoint_validator(self):
        import checkpoint as checkpoint_engine
        row = self.row()
        _, program, metrics = solve(row)
        broken = dict(metrics, v9final=len(program) + 1)
        with self.assertRaisesRegex(ValueError, "invalid stage metrics"):
            checkpoint_engine.validate_record("v9", row, program, broken)
        broken = dict(metrics, nodes=True)
        with self.assertRaisesRegex(ValueError, "invalid nodes"):
            checkpoint_engine.validate_record("v9", row, program, broken)
        broken = dict(metrics, routes=[{"config": ["constructor_wide_polish", 6, 3],
                                        "nodes": None, "score": None, "error": "boom"}])
        with self.assertRaisesRegex(ValueError, "invalid route metrics"):
            checkpoint_engine.validate_record("v9", row, program, broken)
        self.assertEqual(SOLVER_VERSION, "v9")

    def test_solver_version_is_single_sourced(self):
        self.assertEqual(graph_solver.DEFAULT_VERSION, SOLVER_VERSION)
        self.assertEqual(graph_solver.DEFAULT_VERSION, "v9")


class NativeProtocolTest(unittest.TestCase):
    def row(self, **overrides):
        data = {"id": "p", "starting_values": "[3,5]", "targets": "[9,15]",
                "value_limit": "100", "registers": "48"}
        data.update(overrides)
        return data

    def test_parses_valid_graph(self):
        graph = parse_graph("2\n9 * 3 3\n15 * 3 5\n", self.row())
        self.assertEqual(graph, {9: ("*", 3, 3), 15: ("*", 3, 5)})

    def test_rejects_malformed_protocol(self):
        cases = [
            ("", "no protocol header"),
            ("x\n", "no protocol header"),
            ("3\n9 * 3 3\n15 * 3 5\n", "declared 3 nodes"),
            ("1\n9 ? 3 3\n", "unknown native operator"),
            ("1\n9 * 3\n", "malformed native node"),
            ("1\n9 * 3 five\n", "non-integer native node"),
            ("2\n9 * 3 3\n9 + 3 5\n", "duplicate native producer"),
            ("1\n20 * 4 5\n", "depends on undefined value"),
            ("2\n9 * 3 3\n15 * 3 4\n", "depends on undefined value"),
            ("1\n10 * 3 3\n", "does not satisfy"),
            ("1\n9 / 3 5\n", "does not satisfy"),
            ("1\n500 * 3 3\n", "outside 1..100"),
            ("1\n9 * 3 3\n", "missing"),
            ("2\n0 * 1 1\n9 * 3 3\n", "outside 1..100"),
        ]
        for text, error in cases:
            with self.subTest(error=error):
                with self.assertRaisesRegex(ValueError, error):
                    parse_graph(text, self.row())

    def test_rejects_values_outside_signed_64_bit_protocol(self):
        too_big = str(2 ** 63)
        with self.assertRaisesRegex(ValueError, "signed 64-bit"):
            puzzle_numbers(self.row(targets=f"[{too_big}]"))
        with self.assertRaisesRegex(ValueError, "signed 64-bit"):
            puzzle_numbers(self.row(value_limit=too_big))
        with self.assertRaisesRegex(ValueError, "value_limit"):
            puzzle_numbers(self.row(targets="[900]", value_limit=100))
        with self.assertRaisesRegex(ValueError, "duplicate starting values"):
            puzzle_numbers(self.row(starting_values="[3,3]"))
        with self.assertRaisesRegex(ValueError, "more starting values than registers"):
            puzzle_numbers(self.row(starting_values="[3,5]", registers=1))

    def _stub(self, body):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        script = Path(directory.name) / "stub"
        script.write_text("#!/bin/sh\n" + body + "\n")
        script.chmod(0o755)
        return script

    def test_native_timeout_is_an_error(self):
        stub = self._stub("sleep 5")
        with self.assertRaisesRegex(ValueError, "timed out after 0.2s"):
            native_construct.construct(self.row(), 6, 3, "constructor_wide",
                                       binary=stub, timeout=0.2)

    def test_native_nonzero_exit_is_an_error(self):
        stub = self._stub("echo 'target missing' >&2; exit 2")
        with self.assertRaisesRegex(ValueError, "exited 2: target missing"):
            native_construct.construct(self.row(), 6, 3, "constructor_wide", binary=stub)

    def test_unknown_kernel_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown native constructor kernel"):
            native_construct.construct(self.row(), 6, 3, "constructor_unknown")

    def test_native_build_failure_is_explicit(self):
        with mock.patch.dict("os.environ", {"SANTA_CXX": "/bin/false"}):
            with self.assertRaisesRegex(RuntimeError, "no working C\\+\\+17 compiler"):
                native_build.choose_compiler()


class SourceInventoryTest(unittest.TestCase):
    def test_web_review_and_checkpoint_bind_the_same_sources(self):
        import importlib.util
        builder = Path(__file__).resolve().parents[3] / "web" / "build" / "build.py"
        spec = importlib.util.spec_from_file_location("santa_bundle_inventory", builder)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        import checkpoint as checkpoint_engine
        santa_src = Path(__file__).resolve().parents[1] / "src"
        web_sources = {path.relative_to(santa_src).as_posix()
                       for path in module.solver_sources(santa_src)}
        self.assertEqual(web_sources, set(checkpoint_engine.BOUND_SOURCES))

    def test_checkpoint_binds_native_sources_but_not_the_archive_merge_tool(self):
        import checkpoint as checkpoint_engine
        sources = set(checkpoint_engine.BOUND_SOURCES)
        for name in ("algorithms/native/build.py",
                     "algorithms/native/constructor_wide.cpp",
                     "algorithms/native/constructor_mitm.cpp",
                     "algorithms/native/compat/bits/stdc++.h",
                     "algorithms/solver.py", "checkpoint.py", "graph_solver.py", "verify.py"):
            self.assertIn(name, sources)
        self.assertNotIn("merge_submissions.py", sources)
        self.assertEqual(checkpoint_engine.SCHEMA, 3)
        self.assertEqual(checkpoint_engine.LAYOUT, "v9-functional")


if __name__ == "__main__":
    unittest.main()
