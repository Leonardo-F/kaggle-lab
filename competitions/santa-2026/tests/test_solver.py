import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
import graph_solver
from algorithms.solver import DEFAULT_CONFIG, STAGES, solve


class SolverTest(unittest.TestCase):
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
        self.assertIn('"version": "v8"', result.stdout)
        self.assertIn('"validated": 1', result.stdout)
        self.assertEqual(len(self.read_program()), 3)

    def test_explicit_v8_alias_matches_default(self):
        self.assertEqual(self.run_cli().returncode, 0)
        default = self.output.read_bytes()
        self.output.unlink()
        result = self.run_cli("--version", "v8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), default)

    def test_legacy_version_points_to_git_worktree(self):
        result = self.run_cli("--version", "v7")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(graph_solver.LEGACY_REVISION, result.stderr)
        self.assertIn("worktree", result.stderr)
        self.assertIn("--version v7", result.stderr)

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

    def test_solve_returns_stage_metrics(self):
        row = {"id": "test", "starting_values": "[3]", "targets": "[9,27,81]",
               "value_limit": "100", "registers": "48"}
        pid, program, metrics = solve(row)
        self.assertEqual(pid, "test")
        self.assertEqual(len(program), 3)
        self.assertEqual(metrics["v8final"], len(program))
        for stage in STAGES:
            self.assertIn(stage, metrics)
            self.assertIs(type(metrics[stage]), int)
        costs = [metrics[stage] for stage in STAGES]
        self.assertEqual(costs, sorted(costs, reverse=True))
        self.assertEqual(set(DEFAULT_CONFIG), {"v6_rounds", "v6_extra", "v7_portfolio",
                                               "v7_path_rounds", "v7_schedule",
                                               "v7_retain_v6_graphs", "rewrite_sweeps",
                                               "three_sweeps", "three_budget",
                                               "group_strict_rounds", "group_neutral_rounds",
                                               "group_beam", "schedule_tries"})

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

    def test_only_functional_modules_remain(self):
        algorithms = SRC / "algorithms"
        names = sorted(path.stem for path in algorithms.glob("*.py"))
        self.assertEqual(names, ["__init__", "common", "construct", "graph",
                                 "rewrite", "schedule", "solver"])
        self.assertFalse(list(algorithms.glob("v[0-9]*.py")))

    def test_rejects_duplicate_ids(self):
        self.puzzles.write_text(
            'id,starting_values,targets,value_limit,registers\n'
            'a,[3],"[9]",100,48\n'
            'a,[3],"[9]",100,48\n'
        )
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unique puzzle IDs", result.stderr)


if __name__ == "__main__":
    unittest.main()
