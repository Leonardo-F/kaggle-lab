"""Current checkpoint lifecycle, provenance, and corruption checks."""
import csv
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from verify import verify
from algorithms.native import build


class CheckpointTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build.ensure_built()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        d = Path(self.directory.name)
        self.p, self.db, self.out = d/"p.csv", d/"run.sqlite", d/"result.csv"
        with self.p.open("w", newline="") as f:
            w = csv.writer(f); w.writerow(["id", "starting_values", "targets", "value_limit", "registers"])
            w.writerow(["a", "[3]", "[9,27,81]", 100, 48])
        self.cmd = [sys.executable, str(ROOT / "src/graph_solver.py"), str(self.p), "--output", str(self.out), "--jobs", "1", "--checkpoint", str(self.db)]

    def invoke(self, *args, ok=True):
        result = subprocess.run(self.cmd + list(args), text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_resume_and_verify(self):
        self.invoke("--stop-after", "1")
        self.assertFalse(self.out.exists())
        self.invoke("--resume")
        self.assertEqual(verify(self.p, self.out)["score"], 3)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("select count(*) from groups").fetchone()[0], 2)

    def test_corruption_blocks_resume(self):
        self.invoke("--stop-after", "1")
        with sqlite3.connect(self.db) as db:
            db.execute("update groups set digest = 'bad'")
        self.invoke("--resume", ok=False)
        self.assertFalse(self.out.exists())

    def test_changed_input_blocks_resume(self):
        self.invoke("--stop-after", "0")
        self.p.write_text(self.p.read_text().replace("100,48", "101,48"))
        self.invoke("--resume", ok=False)
        self.assertFalse(self.out.exists())

    def test_legacy_checkpoint_rejected(self):
        with sqlite3.connect(self.db) as db:
            db.execute("create table meta(v text)")
        self.invoke("--resume", ok=False)
