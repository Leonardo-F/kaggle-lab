"""Consistency tests for the V9 integration acceptance report.

The report is engineering evidence, not a formal algorithm version: it must not
join the vN.json score curve, and its archive/full-scale claims must match the
tracked submission files and the current integrated sources.
"""

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SANTA = TESTS.parent
SRC = SANTA / "src"
sys.path.insert(0, str(SRC))
import checkpoint as checkpoint_engine

_SPEC = importlib.util.spec_from_file_location(
    "santa_acceptance_build_report", SANTA / "docs" / "build_report.py")
build_report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_report)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class AcceptanceReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = SANTA / "docs" / "reports" / "v9-integration.json"
        cls.report = json.loads(cls.path.read_text(encoding="utf-8"))

    def test_required_shape_and_status(self):
        required = {
            "schema_version", "kind", "status", "baseline_commit", "integration_commit",
            "reviewed_commit", "acceptance_branch", "reference_environment",
            "actual_environment", "reference_source_hashes", "integrated_source_hashes",
            "native_build", "full_scale_reproduction", "same_toolchain_comparison",
            "archive_verification", "checkpoint_validation", "toolchain_cache_fix",
            "test_results", "ci_validation", "limitations", "acceptance_status",
        }
        self.assertEqual(required - set(self.report), set())
        self.assertEqual(self.report["kind"], "santa-v9-integration-acceptance")
        self.assertIn(self.report["acceptance_status"], {"passed", "conditional_pass", "failed"})

    def test_full_scale_reproduction_matches_archive_and_frozen_record(self):
        reproduction = self.report["full_scale_reproduction"]
        self.assertEqual(reproduction["puzzles"], 1000)
        self.assertEqual(reproduction["validated"], 1000)
        self.assertEqual(reproduction["score"], 175604)
        self.assertEqual(reproduction["stage1_total"], 182205)
        self.assertEqual(reproduction["max_steps"], 415)
        self.assertEqual(reproduction["saved_vs_stage1"], 6601)
        self.assertEqual(reproduction["submission_sha256"],
                         reproduction["frozen_submission_sha256"])
        self.assertEqual(reproduction["frozen_submission_sha256"],
                         "5ab0b72c170272591f4d9485730b9805c82d9b2b857827bc017ab53ca3f3ce63")
        self.assertTrue(reproduction["csv_bytes_equal_to_frozen"])
        self.assertEqual(reproduction["checkpoint_integrity_check"], "ok")
        self.assertEqual(reproduction["checkpoint_results"], 1000)

    def test_same_toolchain_comparison_is_complete_and_clean(self):
        comparison = self.report["same_toolchain_comparison"]
        self.assertEqual(comparison["puzzles_compared"], 1000)
        self.assertEqual(comparison["program_differences"], 0)
        self.assertEqual(comparison["program_difference_ids"], [])
        for key in ("v9_stage1", "v9final", "nodes", "schedule_attempts"):
            self.assertEqual(comparison["metric_differences"][key]["differ"], 0, key)
        self.assertEqual(comparison["route_metric_differences"]["differ"], 0)
        self.assertEqual(comparison["route_failures"], {"reference": 0, "port": 0})
        self.assertTrue(comparison["all_three_csvs_byte_identical"])
        self.assertEqual(comparison["reference_submission_sha256"],
                         comparison["integrated_submission_sha256"])

    def test_scored_0775_is_identical_under_the_reference_toolchain(self):
        entry = self.report["scored_0775"]
        self.assertTrue(entry["port_equals_reference"])
        self.assertTrue(entry["port_equals_frozen"])
        self.assertTrue(entry["reference_equals_frozen"])
        self.assertEqual(entry["port_len"], 181)

    def test_archive_hashes_match_tracked_files(self):
        archives = self.report["archive_verification"]
        for key, relative in (
            ("v8", "submissions/elf-calculator-independent-v8-score-194444.csv"),
            ("v9", "submissions/elf-calculator-independent-v9-score-175604.csv"),
            ("merged", "submissions/elf-calculator-merged-v8-v9-score-174884.csv"),
        ):
            entry = archives[key]
            self.assertEqual(sha(SANTA / relative), entry["sha256"], key)
            self.assertEqual(entry["sha256"], entry["report_sha256"], key)
            self.assertTrue(entry["consistent"], key)
        regeneration = archives["mixed_regeneration"]
        self.assertEqual(regeneration["from_v8_strictly_shorter"], 137)
        self.assertEqual(regeneration["from_v9"], 863)
        self.assertEqual(regeneration["ties_to_v9"], 30)
        self.assertEqual(regeneration["formula_errors"], 0)

    def test_integrated_source_hashes_are_historical_and_well_formed(self):
        # This report records the V9 integration sources at its own commit.
        # V10 moved the V9 pipeline into algorithms/v9.py and added five native
        # kernels, so the historical hashes must not be expected to equal the
        # current worktree.  Only shape and declared population are checked.
        hashes = self.report["integrated_source_hashes"]
        self.assertEqual(len(hashes), 14)
        for name, digest in hashes.items():
            self.assertRegex(name, r"^(algorithms/|checkpoint|graph_solver|verify)")
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        for name in ("graph_solver.py", "checkpoint.py", "verify.py",
                     "algorithms/solver.py", "algorithms/native/constructor_wide.cpp"):
            self.assertIn(name, hashes)
        self.assertEqual(self.report["native_build"]["compat_include"], False)

    def test_acceptance_report_is_not_a_formal_score_curve_node(self):
        # The loader only treats vN.json as formal releases; the acceptance
        # report must never leak into the V1-V9 curve.
        self.assertFalse(build_report.FORMAL_REPORT_RE.fullmatch(self.path.name))
        data = build_report.load_report_data()
        self.assertEqual([row["version"] for row in data["historical"]],
                         [f"v{number}" for number in range(1, 12)])
        self.assertEqual(data["statuses"]["v11"], "report-only")
        self.assertNotIn("v9-integration", {row["version"] for row in data["historical"]})


if __name__ == "__main__":
    unittest.main()
