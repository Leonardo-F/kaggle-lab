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


class SolverTest(unittest.TestCase):
    def test_every_version_from_puzzle_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            puzzles = root / "puzzles.csv"
            puzzles.write_text(
                'id,starting_values,targets,value_limit,registers\n'
                'test,[3],"[9,27,81]",100,48\n'
            )
            output = root / "answer.csv"
            versions = [f"v{i}" for i in range(1, int(graph_solver.DEFAULT_VERSION[1:]) + 1)]
            for version in [*versions, None]:
                with self.subTest(version=version):
                    args = ["--version", version] if version else []
                    result = subprocess.run(
                        [sys.executable, str(SRC / "graph_solver.py"), str(puzzles),
                         "--jobs", "1", "--output", str(output), *args],
                        cwd=root, capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('"version": "' + (version or graph_solver.DEFAULT_VERSION) + '"', result.stdout)
                    with output.open(newline="") as stream:
                        program = json.loads(next(csv.DictReader(stream))["program"])
                    self.assertEqual(len(program), 3)
                    output.unlink()


    def test_v6_trace_interface_matches_plain_optimizer(self):
        from algorithms import v6
        row = {"id": "test", "starting_values": "[3]", "targets": "[9,27,81]",
               "value_limit": "100", "registers": "48"}
        plain = v6.optimize_v6((row, 0, False))
        traced = v6.optimize_v6((row, 0, False), trace=True)
        self.assertEqual((traced[0], traced[1], traced[2]), plain)
        self.assertEqual(traced[3][-1], plain[1])

    def test_rejects_reference_option(self):
        result = subprocess.run(
            [sys.executable, str(SRC / "graph_solver.py"), "puzzles.csv",
             "--output", "answer.csv", "--reference", "history.csv"],
            capture_output=True, text=True,
        )
        self.assertIn("unrecognized arguments: --reference", result.stderr)
