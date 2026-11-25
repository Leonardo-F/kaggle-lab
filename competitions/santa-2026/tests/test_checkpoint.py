import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import fcntl

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
import graph_solver


class CheckpointTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.puzzles = self.root / "puzzles.csv"
        self.puzzles.write_text(
            'id,starting_values,targets,value_limit,registers\n'
            'a,[3],"[9,27,81]",100,48\n'
            'b,"[12,5]",[7],30,48\n'
            'c,[2],"[64,81]",100,48\n'
        )
        self.output = self.root / "answer.csv"
        self.checkpoint = self.root / "run.sqlite"

    def run_solver(self, *extra, version="v7"):
        return subprocess.run(
            [sys.executable, str(SRC / "graph_solver.py"), str(self.puzzles),
             "--version", version, "--output", str(self.output),
             "--checkpoint", str(self.checkpoint), *extra],
            capture_output=True, text=True,
        )

    def test_stop_resume_exports_only_complete_run(self):
        first = self.run_solver("--jobs", "1", "--stop-after", "1")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("PARTIAL: 1/3", first.stdout)
        self.assertFalse(self.output.exists())
        with sqlite3.connect(self.checkpoint) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM results").fetchone()[0], 1)

        second = self.run_solver("--jobs", "2", "--resume")
        self.assertEqual(second.returncode, 0, second.stderr)
        report = json.loads((self.root / "answer.csv.validation.json").read_text())
        self.assertEqual(report["resumed_at_start"], 1)
        self.assertEqual(report["validated"], 3)
        self.assertEqual(report["score"], report["v7"])
        self.assertEqual(report["fingerprint"]["version"], "v7")
        self.assertEqual(report["fingerprint"]["parameters"]["path_rounds"], 400)

    def test_resume_rejects_changed_parameters(self):
        self.assertEqual(self.run_solver("--jobs", "1", "--stop-after", "1").returncode, 0)
        result = self.run_solver("--jobs", "1", "--resume", "--path-rounds", "401")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("provenance mismatch", result.stderr)

    def test_resume_requires_matching_checkpoint_state(self):
        self.assertNotEqual(self.run_solver("--jobs", "1", "--resume").returncode, 0)
        self.assertEqual(self.run_solver("--jobs", "1", "--stop-after", "0").returncode, 0)
        self.assertNotEqual(self.run_solver("--jobs", "1").returncode, 0)

    def test_checkpoint_rejects_other_versions(self):
        result = subprocess.run(
            [sys.executable, str(SRC / "graph_solver.py"), str(self.puzzles),
             "--version", "v6", "--output", str(self.output),
             "--checkpoint", str(self.checkpoint), "--jobs", "1"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("only available for v7 and v8", result.stderr)

    def test_concurrent_writer_is_rejected(self):
        lock_path = Path(str(self.checkpoint) + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_solver("--jobs", "1", "--stop-after", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("locked by another running experiment", result.stderr)


    def test_v8_checkpoint_reports_every_stage(self):
        result = self.run_solver("--jobs", "1", version="v8")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.root / "answer.csv.validation.json").read_text())
        stages = ["v7", "list_schedule", "v8", "v81", "v82",
                  "v8group_strict", "v8group_neutral", "v8final"]
        costs = [report[stage] for stage in stages]
        self.assertEqual(report["score"], report["v8final"])
        self.assertEqual(costs, sorted(costs, reverse=True))
        self.assertEqual(report["improved"] + report["unchanged"] + report["worse"], 3)
        self.assertEqual(report["fingerprint"]["version"], "v8")
        self.assertEqual(report["fingerprint"]["parameters"]["rewrite_sweeps"], 2)

if __name__ == "__main__":
    unittest.main()
