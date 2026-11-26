import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
import fcntl

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
import checkpoint as checkpoint_engine


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

    def run_solver(self, *extra):
        return subprocess.run(
            [sys.executable, str(SRC / "graph_solver.py"), str(self.puzzles),
             "--output", str(self.output), "--checkpoint", str(self.checkpoint), *extra],
            capture_output=True, text=True,
        )

    def read_report(self):
        return json.loads((self.root / "answer.csv.validation.json").read_text())

    def test_stop_resume_exports_only_complete_run(self):
        first = self.run_solver("--jobs", "1", "--stop-after", "1")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("PARTIAL: 1/3", first.stdout)
        self.assertFalse(self.output.exists())
        with closing(sqlite3.connect(self.checkpoint)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM results").fetchone()[0], 1)

        second = self.run_solver("--jobs", "2", "--resume")
        self.assertEqual(second.returncode, 0, second.stderr)
        report = self.read_report()
        self.assertEqual(report["resumed_at_start"], 1)
        self.assertEqual(report["validated"], 3)
        self.assertEqual(report["score"], report["v10final"])
        self.assertEqual(report["improved"] + report["unchanged"] + report["worse"], 3)
        fingerprint = report["fingerprint"]
        self.assertEqual(fingerprint["version"], "v10")
        self.assertEqual(fingerprint["schema"], 4)
        self.assertEqual(fingerprint["layout"], "v10-functional")
        self.assertEqual(fingerprint["parameters"]["compile_tries"], 8)
        self.assertEqual(fingerprint["parameters"]["policy"], "full")
        self.assertEqual(fingerprint["parameters"]["stage1_routes"],
                         [[name, width, mode] for name, width, mode in
                          checkpoint_engine.DEFAULTS["v10"]["stage1_routes"]])
        for name in ("algorithms/solver.py", "algorithms/construct.py",
                     "algorithms/schedule.py", "algorithms/rewrite.py",
                     "algorithms/native/build.py",
                     "algorithms/native/constructor_wide.cpp",
                     "algorithms/native/constructor_mitm.cpp",
                     "algorithms/native/compat/bits/stdc++.h"):
            self.assertIn(name, fingerprint["sources"])
        self.assertEqual(sorted(fingerprint["native"]["binaries"]),
                         ["constructor_cf", "constructor_joint", "constructor_mitm",
                          "constructor_order_cf", "constructor_order_fast",
                          "constructor_pressure", "constructor_wide"])
        self.assertTrue(fingerprint["native"]["compiler"]["path"])
        self.assertEqual(fingerprint["native"]["flags"], ["-O3", "-std=c++17"])

    def test_metrics_records_frozen_stage_and_route_keys(self):
        result = self.run_solver("--jobs", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.read_report()
        stages = ["v10_stage1", "v10_stage3", "v10final"]
        costs = [report[stage] for stage in stages]
        self.assertEqual(report["score"], report["v10final"])
        self.assertEqual(costs, sorted(costs, reverse=True))
        metrics = json.loads(Path(str(self.output) + ".metrics.json").read_text())
        self.assertEqual(set(metrics), {"a", "b", "c"})
        for record in metrics.values():
            for key in ("v10_stage1", "v9", "v10_stage3", "v10final", "routes",
                        "nodes", "schedule_attempts", "policies"):
                self.assertIn(key, record)
            self.assertEqual(record["policy"], "full")
            self.assertEqual(len(record["routes"]), 4)
            self.assertEqual([entry["label"] for entry in record["routes"]],
                             ["constructor_wide_polish:6:3",
                              "constructor_wide_polish:6:4",
                              "constructor_mitm_polish:6:3",
                              "constructor_mitm_polish:6:4"])
            for entry in record["routes"]:
                self.assertIs(type(entry["raw"]), int)
                self.assertIs(type(entry["polish"]), int)
            self.assertIs(type(record["nodes"]), int)
            self.assertIs(type(record["schedule_attempts"]), int)
        self.assertEqual(set(metrics["a"]), set(metrics["b"]))

    def test_resume_rejects_changed_parameters(self):
        self.assertEqual(self.run_solver("--jobs", "1", "--stop-after", "1").returncode, 0)
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            checkpoint_engine.run_checkpoint(
                self.puzzles, self.output, self.checkpoint, "v10",
                jobs=1, resume=True, parameters={"schedule_tries": 33},
            )

    def test_resume_requires_matching_checkpoint_state(self):
        self.assertNotEqual(self.run_solver("--jobs", "1", "--resume").returncode, 0)
        self.assertEqual(self.run_solver("--jobs", "1", "--stop-after", "0").returncode, 0)
        self.assertNotEqual(self.run_solver("--jobs", "1").returncode, 0)

    def test_checkpoint_rejects_other_versions(self):
        with self.assertRaisesRegex(ValueError, "supports v9 and v10"):
            checkpoint_engine.run_checkpoint(
                self.puzzles, self.output, self.checkpoint, "v6", jobs=1,
            )
        with self.assertRaisesRegex(ValueError, "V8 baseline commit"):
            checkpoint_engine.run_checkpoint(
                self.puzzles, self.output, self.checkpoint, "v8", jobs=1,
            )

    def test_concurrent_writer_is_rejected(self):
        lock_path = Path(str(self.checkpoint) + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_solver("--jobs", "1", "--stop-after", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("locked by another running experiment", result.stderr)

    def test_record_tampering_is_rejected(self):
        self.assertEqual(self.run_solver("--jobs", "1", "--stop-after", "1").returncode, 0)
        with closing(sqlite3.connect(self.checkpoint)) as db:
            db.execute("UPDATE results SET program='[]' WHERE pid=(SELECT pid FROM results LIMIT 1)")
            db.commit()
        result = self.run_solver("--jobs", "1", "--resume")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checkpoint integrity error", result.stderr)

    def test_legacy_layouts_are_rejected_with_resume_hint(self):
        self.assertEqual(self.run_solver("--jobs", "1", "--stop-after", "0").returncode, 0)
        with closing(sqlite3.connect(self.checkpoint)) as db:
            db.execute("UPDATE meta SET payload=? WHERE id=1",
                       (json.dumps({"schema": 1, "layout": "versioned", "version": "v8"}),))
            db.commit()
        result = self.run_solver("--jobs", "1", "--resume")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("legacy versioned layout", result.stderr)
        self.assertIn(checkpoint_engine.LEGACY_REVISIONS["versioned"], result.stderr)

        with closing(sqlite3.connect(self.checkpoint)) as db:
            db.execute("UPDATE meta SET payload=? WHERE id=1",
                       (json.dumps({"schema": 2, "layout": "functional", "version": "v8"}),))
            db.commit()
        result = self.run_solver("--jobs", "1", "--resume")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("V8 functional layout", result.stderr)
        self.assertIn(checkpoint_engine.LEGACY_REVISIONS["functional"], result.stderr)

    def test_changed_source_fingerprint_is_rejected(self):
        self.assertEqual(self.run_solver("--jobs", "1", "--stop-after", "0").returncode, 0)
        with closing(sqlite3.connect(self.checkpoint)) as db:
            payload = json.loads(db.execute("SELECT payload FROM meta WHERE id=1").fetchone()[0])
            payload["sources"]["algorithms/solver.py"] = "0" * 64
            db.execute("UPDATE meta SET payload=? WHERE id=1",
                       (json.dumps(payload, sort_keys=True, separators=(",", ":")),))
            db.commit()
        result = self.run_solver("--jobs", "1", "--resume")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("provenance mismatch", result.stderr)

    def test_changed_native_binary_fingerprint_is_rejected(self):
        self.assertEqual(self.run_solver("--jobs", "1", "--stop-after", "0").returncode, 0)
        with closing(sqlite3.connect(self.checkpoint)) as db:
            payload = json.loads(db.execute("SELECT payload FROM meta WHERE id=1").fetchone()[0])
            payload["native"]["binaries"]["constructor_wide"] = "0" * 64
            db.execute("UPDATE meta SET payload=? WHERE id=1",
                       (json.dumps(payload, sort_keys=True, separators=(",", ":")),))
            db.commit()
        result = self.run_solver("--jobs", "1", "--resume")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("provenance mismatch", result.stderr)

    def test_changed_input_is_rejected(self):
        self.assertEqual(self.run_solver("--jobs", "1", "--stop-after", "0").returncode, 0)
        self.puzzles.write_text(
            'id,starting_values,targets,value_limit,registers\n'
            'a,[3],"[9,27,81]",100,48\n'
        )
        result = self.run_solver("--jobs", "1", "--resume")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("provenance mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
