import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "src"


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
            versions = sorted(p.stem for p in (SRC / "algorithms").glob("v[1-5].py"))
            for version in [*versions, None]:
                with self.subTest(version=version):
                    args = ["--version", version] if version else []
                    result = subprocess.run(
                        [sys.executable, str(SRC / "graph_solver.py"), str(puzzles),
                         "--jobs", "1", "--output", str(output), *args],
                        cwd=root, capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    with output.open(newline="") as stream:
                        program = json.loads(next(csv.DictReader(stream))["program"])
                    self.assertEqual(len(program), 3)
                    output.unlink()

    def test_rejects_reference_option(self):
        result = subprocess.run(
            [sys.executable, str(SRC / "graph_solver.py"), "puzzles.csv",
             "--output", "answer.csv", "--reference", "history.csv"],
            capture_output=True, text=True,
        )
        self.assertIn("unrecognized arguments: --reference", result.stderr)
