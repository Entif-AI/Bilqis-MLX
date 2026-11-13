"""Evidence projection behavior from the original School50 suite."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from bilqis_mlx.presentation.dashboard import build, ingest


class EvidenceTests(unittest.TestCase):
    def test_unavailable_longitudinal_history_names_the_actual_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "B",
                "generation": 22, "rubric": "b" * 64,
                "cohort_sha256": "c" * 64, "optimizer_step": 123,
                "cohort_file": f"cohorts/{'c' * 64}.json",
                "generator_version": "test-fixed-b-cohort/v1",
                "student_sha256": "a" * 64,
                "scores": {"B.OR": {"correct": 11, "total": 12}},
                "learning_diagnostics": {
                    "active_warnings": [], "history_usable": False,
                    "history_issue": "DIAGNOSTIC_NON_MONOTONIC_CHECKPOINT_HISTORY",
                    "findings": [{"status": "NOT_MEASURED", "signal": "LACK_OF_DURABLE_GAIN",
                                  "capability": "B.OR"}]}})
            system = board.rows["SYSTEM & QUALIFICATION"]
            diagnostic = next(row for row in system if row["kind"] == "DIAGNOSTIC")
            self.assertIn("S3 unavailable", diagnostic["detail"])
            self.assertIn("1 NOT MEASURED", diagnostic["detail"])
            self.assertNotIn("no active warnings", diagnostic["detail"])
            history_error = next(row for row in system if row["kind"] == "HISTORY ISSUE")
            self.assertEqual(history_error["detail"],
                             "DIAGNOSTIC_NON_MONOTONIC_CHECKPOINT_HISTORY")

    def test_paired_s3_recovery_does_not_keep_unavailable_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "B",
                "generation": 23, "rubric": "b" * 64,
                "cohort_sha256": "d" * 64, "optimizer_step": 139,
                "cohort_file": f"cohorts/{'d' * 64}.json",
                "generator_version": "fresh-b-cohort/v2",
                "student_sha256": "e" * 64,
                "scores": {"B.OR": {"correct": 10, "total": 12}},
                "learning_diagnostics": {
                    "active_warnings": [{"signal": "LACK_OF_DURABLE_GAIN",
                                         "capability": "B.OR", "target": "CAPABILITY"}],
                    "history_usable": False, "s3_usable": True,
                    "history_issue": "DIAGNOSTIC_NON_MONOTONIC_CHECKPOINT_HISTORY",
                    "findings": [{"status": "OBSERVED_LONGITUDINALLY",
                                  "signal": "LACK_OF_DURABLE_GAIN",
                                  "capability": "B.OR"}]}})
            system = board.rows["SYSTEM & QUALIFICATION"]
            diagnostic = next(row for row in system if row["kind"] == "DIAGNOSTIC")
            self.assertIn("S3:B.OR", diagnostic["detail"])
            self.assertNotIn("S3 unavailable", diagnostic["detail"])
            history_error = next(row for row in system if row["kind"] == "HISTORY ISSUE")
            self.assertIn("paired S3 recovered", history_error["detail"])

    def test_live_exam_projects_warning_and_teacher_outcome_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "grade": "B",
                "generation": 8, "rubric": "b" * 64,
                "cohort_sha256": "c" * 64,
                "generator_version": "grade-b-live/v1",
                "cohort_file": f"cohorts/{'c'*64}.json",
                "optimizer_step": 200, "student_sha256": "d" * 64,
                "scores": {"B.NOT": {"correct": 6, "total": 12}},
                "learning_diagnostics": {
                    "active_warnings": [{"signal":"CHANCE_LEVEL_OR_LAGGING",
                                         "target":"CAPABILITY","capability":"B.NOT"}],
                    "findings": [{"signal":"CHANCE_LEVEL_OR_LAGGING",
                                  "status":"OBSERVED_IN_COHORT","capability":"B.NOT"},
                                 {"signal":"LACK_OF_DURABLE_GAIN",
                                  "status":"NOT_MEASURED","capability":"B.NOT"}],
                },
                "teacher_outcomes": [{
                    "capability":"B.NOT",
                    "attribution":"MEASURED_FIXED_EXAM_UNIQUE_ACTION",
                    "delta_correct": 2,
                }],
            })
            system = board.rows["SYSTEM & QUALIFICATION"]
            diagnostic = next(row for row in system if row["kind"] == "DIAGNOSTIC")
            outcome = next(row for row in system if row["kind"] == "TEACH OUTCOME")
            self.assertIn("S2:B.NOT", diagnostic["detail"])
            self.assertIn("1 NOT MEASURED", diagnostic["detail"])
            self.assertIn("B.NOT +2", outcome["detail"])

    def test_future_sentinel_soup_and_qualification_emit_without_grade_renames(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_SENTINEL_COMMITTED", "grade": "C",
                           "generation": 50, "optimizer_step": 131000,
                           "partition": "independent_validation", "probe_delta_pp": 5.,
                           "dataset_sha256": "a" * 64, "student_sha256": "b" * 64,
                           "sentinel_delta_pp": 2.5, "worst_delta_pp": -6.25,
                           "cross_entropy_delta": -.3, "correct_probability_delta": .03,
                           "margin_delta": .12, "family_count": 8})
            ingest(board, {"event": "SCHOOL_SOUP_COMMITTED", "grade": "C",
                           "generation": 51, "optimizer_step": 131000,
                           "teacher_only": True, "teacher_digest": "c" * 64,
                           "soup_kl": .04, "parent_kl": .03,
                           "coverage": .85, "supervised_loss": .7,
                           "teacher_credit": .2, "bridge_ce": .4})
            ingest(board, {"event": "SCHOOL_QUALIFICATION_COMMITTED", "grade": "C",
                           "generation": 52, "status": "SOURCE_ATTESTED",
                           "details": "NI typed morphology checked"})
            self.assertEqual(board.rows["SENTINEL & RETENTION"][-1]["grade"], "C")
            self.assertEqual(board.rows["SENTINEL & RETENTION"][-1]["sent"], "+2.5pp")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["soup"], "0.040")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["cover"], "85.0%")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["sup"], "0.700")
            self.assertEqual(board.rows["SOUP & TEACHER"][-1]["bridge_ce"], "0.400")
            self.assertTrue(any("SOURCE_ATTESTED" in r["detail"]
                                for r in board.rows["SYSTEM & QUALIFICATION"]))

    def test_unverified_future_sentinel_and_student_soup_cannot_claim_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            with self.assertRaisesRegex(ValueError, "SOURCE_PROVENANCE_REQUIRED"):
                ingest(board, {"event": "SCHOOL_SENTINEL_COMMITTED", "grade": "B",
                               "partition": "independent_validation", "probe_delta_pp": 5})
            with self.assertRaisesRegex(ValueError, "TEACHER_ONLY_REQUIRED"):
                ingest(board, {"event": "SCHOOL_SOUP_COMMITTED", "grade": "B",
                               "teacher_only": False, "soup_kl": .01})
            self.assertFalse(board.rows["SENTINEL & RETENTION"])
            self.assertFalse(board.rows["SOUP & TEACHER"])

    def test_autonomy_events_are_visible_in_system_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_AUTONOMY_EVIDENCE_RECORDED",
                "grade": "B",
                "generation": 60,
                "capability": "B.IDBOOLOPS",
                "obligation": "B.IDBOOLOPS/prerequisite/B.XOR",
                "passed": False,
                "cohort_sha256": "a" * 64,
                "student_sha256": "b" * 64,
                "optimizer_step": 140000,
            })
            ingest(board, {
                "event": "SCHOOL_AUTONOMY_TEACHING_RECORDED",
                "grade": "B",
                "generation": 61,
                "capability": "B.IDBOOLOPS",
                "obligation": "B.IDBOOLOPS/prerequisite/B.XOR",
                "parent_student_sha256": "b" * 64,
                "student_sha256": "c" * 64,
                "optimizer_step": 140016,
            })
            ingest(board, {
                "event": "SCHOOL_AUTONOMY_SOURCE_COVERAGE_BLOCKED",
                "grade": "B",
                "generation": 62,
                "debt": ["B.IDBOOLOPS:TRANSFER:SOURCE_PROJECTION_UNSUPPORTED"],
                "model_and_optimizer_unchanged": True,
            })

            autonomy = [
                row for row in board.rows["SYSTEM & QUALIFICATION"]
                if row.get("kind") == "AUTONOMY"
            ]
            self.assertEqual(len(autonomy), 3)
            self.assertIn("FAIL B.IDBOOLOPS", autonomy[0]["detail"])
            self.assertIn("B.IDBOOLOPS/prerequisite/B.XOR", autonomy[0]["detail"])
            self.assertIn("TEACH B.IDBOOLOPS", autonomy[1]["detail"])
            self.assertIn("SOURCE COVERAGE BLOCKED", autonomy[2]["detail"])
            self.assertIn("SOURCE_PROJECTION_UNSUPPORTED", autonomy[2]["detail"])

    def test_disk_headroom_is_visible_and_grade_neutral_in_system_panel(self):
        free = int(100.28 * 1024 ** 3)
        with tempfile.TemporaryDirectory() as tmp, patch(
            "bilqis_mlx.runtime.disk.shutil.disk_usage",
            return_value=SimpleNamespace(total=1000 * 1024 ** 3,
                                         used=0, free=free)):
            board = build(Path(tmp), stream=io.StringIO())
            disk = next(x for x in board.rows["SYSTEM & QUALIFICATION"]
                        if x["kind"] == "DISK")
            self.assertIn("100.28 GiB", disk["detail"])
            self.assertIn("BLOCKED", disk["detail"])
            ingest(board, {"event": "SCHOOL_RESOURCE_OBSERVED", "grade": "B",
                           "free_bytes": free + 1024 ** 3,
                           "reserve_bytes": 100 * 1024 ** 3,
                           "estimated_write_bytes": 600_000_000})
            updated = [x for x in board.rows["SYSTEM & QUALIFICATION"]
                       if x["kind"] == "DISK"]
            self.assertEqual(len(updated), 1)
            self.assertIn("READY", updated[0]["detail"])
