"""Regression coverage for the single current production solver."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from algorithms import SOLVER_VERSION, solve
from algorithms import construct
from algorithms.solver import ROUTES, choose
from algorithms.native import build
from verify import verify

ROW = dict(id="tiny", starting_values="[3]", targets="[9,27,81]", value_limit="100", registers="48")


class SolverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = build.ensure_built()

    def test_current_solver(self):
        pid, program, metrics = solve(ROW)
        self.assertEqual(pid, ROW["id"])
        self.assertEqual(len(program), 3)
        self.assertEqual(min(metrics["scores"].values()), 3)
        self.assertEqual(set(ROUTES), {"r8", "basis"})

    def test_zero_step(self):
        self.assertEqual(solve(dict(ROW, targets="[3]"))[1], [])

    def test_tie_order(self):
        p = [["*", 0, 0, 1], ["*", 1, 0, 2], ["*", 2, 0, 3]]
        q = [["*", 0, 0, 2], ["*", 2, 0, 1], ["*", 1, 0, 3]]
        result = {"r8": {"programs": {"first": p, "second": q}}, "basis": {"programs": {"other": q}}}
        self.assertEqual(choose(ROW, result)[2]["winner"], "r8/first")
        self.assertEqual(choose(ROW, result)[1], p)

    def test_no_legacy_modules(self):
        directory = ROOT / "src" / "algorithms"
        for name in ("v9.py", "v10.py", "v11.py", "v11_frozen_fulltest"):
            self.assertFalse((directory / name).exists())
        self.assertEqual(SOLVER_VERSION, "v11")
        self.assertEqual(set(self.manifest["binaries"]), set(build.KERNELS))
        self.assertEqual(len(build.KERNELS), 8)

    def test_malformed_native_protocol(self):
        with mock.patch.object(construct.subprocess, "run", return_value=mock.Mock(stdout="2\n9 * 3 3\n", stderr="")):
            with self.assertRaises(ValueError):
                construct.native("order", [6, 3], "100 1 1 3 9")

    def test_cli_independent_validation(self):
        with tempfile.TemporaryDirectory() as d:
            p, out = Path(d)/"puzzles.csv", Path(d)/"answer.csv"
            with p.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(ROW)); w.writeheader(); w.writerow(ROW)
            cmd = [sys.executable, str(ROOT / "src/graph_solver.py"), str(p), "--output", str(out), "--jobs", "2"]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.assertEqual(verify(p, out)["score"], 3)
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            out.unlink()
            self.assertNotEqual(subprocess.run(cmd + ["--version", "v10"], capture_output=True).returncode, 0)
            self.assertFalse(out.exists())

    def test_split_requires_the_exact_official_input(self):
        with tempfile.TemporaryDirectory() as d:
            p, out, db = Path(d)/"p.csv", Path(d)/"out.csv", Path(d)/"db.sqlite"
            with p.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(ROW)); w.writeheader(); w.writerow(ROW)
            cmd = [sys.executable, str(ROOT/"src/graph_solver.py"), str(p),
                   "--output", str(out), "--checkpoint", str(db), "--split", "dev"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exact official puzzle CSV", result.stderr)
            self.assertFalse(out.exists())

    def test_stop_after_and_resume_require_a_checkpoint(self):
        cmd = [sys.executable, str(ROOT/"src/graph_solver.py"), "unused.csv", "--output", "unused-out.csv"]
        for extra in (["--stop-after", "2"], ["--resume"]):
            with self.subTest(extra=extra):
                result = subprocess.run(cmd + extra, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("require --checkpoint", result.stderr)

    def test_group_validation_rejects_a_tampered_score(self):
        from algorithms.solver import solve_group
        from algorithms import solver as solver_module
        real = solver_module.ROUTES["r8"]
        def fake(row):
            return {"id": row["id"], "programs": {"x": []}, "scores": {"x": 1}}
        solver_module.ROUTES["r8"] = fake
        try:
            with self.assertRaisesRegex(ValueError, "invalid candidate group"):
                solve_group("r8", dict(ROW, targets="[3]"))
        finally:
            solver_module.ROUTES["r8"] = real

    def test_internal_replay_rejects_illegal_operations(self):
        from algorithms.common import replay
        for program in ([["-", 0, 0, 1]], [["/", 0, 0, 1]], [["?", 0, 0, 1]],
                        [["+", 0, 1, 1]], [["+", 0, 0, 99]]):
            with self.subTest(program=program):
                with self.assertRaises(ValueError):
                    replay(ROW, program)

    def test_compile_and_schedule_a_small_graph(self):
        from algorithms.common import replay
        from algorithms.schedule import compile_candidate
        graph = {9: ("*", 3, 3), 27: ("*", 9, 3), 81: ("*", 9, 9)}
        program, nodes = compile_candidate(ROW, graph)
        self.assertEqual(nodes, 3)
        self.assertGreaterEqual(len(program), 3)
        self.assertEqual(replay(ROW, program), len(program))
        self.assertLessEqual(len(program), 5)

    def test_compile_rejects_an_inconsistent_graph(self):
        from algorithms.schedule import compile_candidate
        cases = (({9: ("+", 3, 3)}, "[9]"),
                 ({9: ("?", 3, 3)}, "[9]"),
                 ({9: ("*", 3, 3), 10: ("+", 9, 3)}, "[9,10]"))
        for graph, targets in cases:
            with self.subTest(graph=graph):
                with self.assertRaises(ValueError):
                    compile_candidate(dict(ROW, targets=targets), graph)

    def test_native_protocol_rejects_malformed_lines(self):
        from algorithms import construct
        cases = ("2\n9 * 3 3\n", "1\n9 * 3\n", "1\n9 * 3 3\n10 + 3 3\n")
        for stdout in cases:
            with self.subTest(stdout=stdout):
                with mock.patch.object(construct.subprocess, "run",
                                       return_value=mock.Mock(stdout=stdout, stderr="")):
                    with self.assertRaises(ValueError):
                        construct.native("order", [6, 3], "100 1 1 3 9")
