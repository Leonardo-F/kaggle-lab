"""Tests for the archive-time V8/V9 merge CLI (synthetic data only, no official puzzles)."""

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import merge_submissions
from merge_submissions import merge
from verify import verify

SCRIPT = Path(__file__).resolve().parents[1] / "src" / "merge_submissions.py"
PUZZLE_HEADER = ("id", "starting_values", "targets", "value_limit", "registers")
PUZZLES = (
    ("p1", "[12,5]", "[7]", 30, 4),
    ("p2", "[3,4]", "[1]", 30, 4),
    ("p3", "[2,3]", "[6]", 30, 4),
)

# One instruction per puzzle: 12-5=7, 4-3=1, 2*3=6.
SHORT = {
    "p1": [["-", 0, 1, 2]],
    "p2": [["-", 1, 0, 2]],
    "p3": [["*", 0, 1, 2]],
}
# Two instructions per puzzle; the extra step is legal but never needed.
LONG = {
    "p1": [["-", 0, 1, 2], ["+", 2, 1, 2]],
    "p2": [["-", 1, 0, 2], ["+", 2, 0, 2]],
    "p3": [["*", 0, 1, 2], ["*", 2, 1, 2]],
}
# Same lengths as LONG but different instructions, to test the tie-break.
ALT_LONG = {
    "p1": [["-", 0, 1, 2], ["+", 2, 0, 2]],
    "p2": [["-", 1, 0, 2], ["+", 2, 1, 2]],
    "p3": [["*", 0, 1, 2], ["*", 2, 0, 2]],
}


def encode(program):
    return json.dumps(program, separators=(",", ":"))


class MergeTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.puzzles = self.root / "puzzles.csv"
        self.first = self.root / "first.csv"
        self.second = self.root / "second.csv"
        self.output = self.root / "merged.csv"
        self.write_puzzles()

    def write_puzzles(self, rows=PUZZLES):
        with self.puzzles.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(PUZZLE_HEADER)
            writer.writerows(rows)

    def write_submission(self, path, programs, ids=("p1", "p2", "p3"), header=("id", "program")):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            for pid in ids:
                row = programs[pid]
                writer.writerow((pid, row if isinstance(row, str) else encode(row)))

    def write_pair(self, first=SHORT, second=LONG, first_ids=("p1", "p2", "p3"),
                   second_ids=("p1", "p2", "p3")):
        self.write_submission(self.first, first, first_ids)
        self.write_submission(self.second, second, second_ids)

    def output_rows(self):
        with self.output.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, ["id", "program"])
            return [(row["id"], json.loads(row["program"])) for row in reader]

    def temp_files(self):
        return sorted(path.name for path in self.root.iterdir() if path.name.endswith(".tmp"))

    def assert_clean_failure(self):
        self.assertFalse(self.output.exists())
        self.assertEqual(self.temp_files(), [])

    def sha256(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_merges_shorter_program_and_counts_sources(self):
        self.write_pair(first={"p1": LONG["p1"], "p2": SHORT["p2"], "p3": LONG["p3"]},
                        second={"p1": SHORT["p1"], "p2": LONG["p2"], "p3": SHORT["p3"]})
        summary = merge(self.puzzles, self.first, self.second, self.output)

        self.assertEqual(summary["puzzles"], 3)
        self.assertEqual(summary["validated"], 3)
        self.assertEqual(summary["score"], 3)
        self.assertEqual(summary["max_steps"], 1)
        self.assertEqual((summary["from_first"], summary["from_second"], summary["tie"]),
                         (1, 2, 0))
        self.assertEqual(summary["inputs"]["first"]["score"], 5)
        self.assertEqual(summary["inputs"]["second"]["score"], 4)
        self.assertEqual(summary["inputs"]["first"]["sha256"], self.sha256(self.first))
        self.assertEqual(summary["inputs"]["second"]["sha256"], self.sha256(self.second))
        self.assertEqual(summary["inputs"]["puzzles"]["sha256"], self.sha256(self.puzzles))
        self.assertEqual(summary["output"]["sha256"], self.sha256(self.output))
        self.assertIsNone(summary["expect_score"])
        self.assertEqual(self.output_rows(), [
            ("p1", SHORT["p1"]), ("p2", SHORT["p2"]), ("p3", SHORT["p3"]),
        ])
        report = verify(self.puzzles, self.output)
        self.assertEqual((report["validated"], report["score"], report["max_steps"]),
                         (3, 3, 1))

    def test_tie_is_won_by_second_input(self):
        self.write_pair(first=LONG, second=ALT_LONG)
        summary = merge(self.puzzles, self.first, self.second, self.output)

        self.assertEqual((summary["from_first"], summary["from_second"], summary["tie"]),
                         (0, 3, 3))
        self.assertEqual(summary["score"], 6)
        self.assertEqual(self.output_rows(), [
            ("p1", ALT_LONG["p1"]), ("p2", ALT_LONG["p2"]), ("p3", ALT_LONG["p3"]),
        ])
        self.assertNotEqual(self.output_rows()[0][1], LONG["p1"])

    def test_scrambled_input_rows_follow_puzzle_order(self):
        self.write_pair(first=LONG, second=SHORT,
                        first_ids=("p3", "p1", "p2"), second_ids=("p2", "p3", "p1"))
        summary = merge(self.puzzles, self.first, self.second, self.output)

        self.assertEqual(summary["score"], 3)
        self.assertEqual([pid for pid, _ in self.output_rows()], ["p1", "p2", "p3"])
        self.assertEqual(self.output_rows(), [
            ("p1", SHORT["p1"]), ("p2", SHORT["p2"]), ("p3", SHORT["p3"]),
        ])

    def test_rejects_wrong_input_header(self):
        for broken in (self.first, self.second):
            with self.subTest(broken=broken.name):
                self.write_pair()
                self.write_submission(broken, LONG, header=("id", "programs"))
                with self.assertRaisesRegex(ValueError, "wrong submission header"):
                    merge(self.puzzles, self.first, self.second, self.output)
                self.assert_clean_failure()

    def test_rejects_duplicate_missing_or_extra_ids(self):
        for label, programs, ids in [
            ("duplicate", LONG, ("p1", "p1", "p2", "p3")),
            ("missing", LONG, ("p1", "p2")),
            ("extra", dict(LONG, p4=[]), ("p1", "p2", "p3", "p4")),
        ]:
            with self.subTest(label=label):
                self.write_pair()
                self.write_submission(self.first, programs, ids)
                with self.assertRaisesRegex(ValueError, "puzzle IDs"):
                    merge(self.puzzles, self.first, self.second, self.output)
                self.assert_clean_failure()

    def test_rejects_invalid_programs(self):
        for label, raw in [
            ("invalid-json", "{"),
            ("invalid-operator", '[["%",0,1,2]]'),
            ("invalid-instruction", '[["-",0,1]]'),
            ("missing-targets", '[["+",0,1,2]]'),
        ]:
            with self.subTest(label=label):
                self.write_pair()
                self.write_submission(self.first, dict(SHORT, p1=raw))
                with self.assertRaises(ValueError):
                    merge(self.puzzles, self.first, self.second, self.output)
                self.assert_clean_failure()

    def test_refuses_existing_output(self):
        self.write_pair()
        self.output.write_text("sentinel", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            merge(self.puzzles, self.first, self.second, self.output)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "sentinel")
        self.assertEqual(self.temp_files(), [])

    def test_expect_score_mismatch_leaves_no_output(self):
        self.write_pair(first=LONG, second=SHORT)
        with self.assertRaisesRegex(ValueError, "expected score 999, got 3"):
            merge(self.puzzles, self.first, self.second, self.output, expect_score=999)
        self.assert_clean_failure()

    def test_failure_after_temp_write_cleans_up(self):
        self.write_pair(first=LONG, second=SHORT)
        real_verify = merge_submissions.verify

        def verify_or_fail(puzzles, submission):
            if Path(submission).name.endswith(".tmp"):
                raise ValueError("simulated output verification failure")
            return real_verify(puzzles, submission)

        with mock.patch.object(merge_submissions, "verify", side_effect=verify_or_fail):
            with self.assertRaisesRegex(ValueError, "simulated output verification failure"):
                merge(self.puzzles, self.first, self.second, self.output)
        self.assert_clean_failure()

    def test_cli_end_to_end(self):
        self.write_pair(first={"p1": LONG["p1"], "p2": SHORT["p2"], "p3": LONG["p3"]},
                        second={"p1": SHORT["p1"], "p2": LONG["p2"], "p3": SHORT["p3"]})
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.puzzles), str(self.first),
             str(self.second), "-o", str(self.output), "--expect-score", "3"],
            capture_output=True, text=True, cwd=self.root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["puzzles"], 3)
        self.assertEqual(summary["validated"], 3)
        self.assertEqual(summary["score"], 3)
        self.assertEqual(summary["max_steps"], 1)
        self.assertEqual((summary["from_first"], summary["from_second"], summary["tie"]),
                         (1, 2, 0))
        self.assertEqual(summary["expect_score"], {"expected": 3, "actual": 3, "ok": True})
        self.assertEqual(summary["output"]["path"], str(self.output))
        self.assertEqual(summary["output"]["sha256"], self.sha256(self.output))
        report = verify(self.puzzles, self.output)
        self.assertEqual((report["validated"], report["score"]), (3, 3))

    def test_cli_exit_code_and_no_output_on_failure(self):
        self.write_pair(first=LONG, second=SHORT)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.puzzles), str(self.first),
             str(self.second), "-o", str(self.output), "--expect-score", "999"],
            capture_output=True, text=True, cwd=self.root,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected score 999, got 3", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assert_clean_failure()


if __name__ == "__main__":
    unittest.main()
