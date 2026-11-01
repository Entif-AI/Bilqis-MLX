"""Exams projection behavior from the original School50 suite."""
import io
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.dashboard import build, ingest
from bilqis_mlx.presentation.tests.school50.fixtures import exam


class ExamsTests(unittest.TestCase):
    def test_exam_without_logical_target_grade_remains_renderable(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "B",
                "generation": 13008, "rubric": "b" * 64,
                "assessment_scope_sha256": "s" * 64,
                "cohort_sha256": "c" * 64,
                "generator_version": "grade-live/v2",
                "cohort_file": f"cohorts/{'c' * 64}.json",
                "optimizer_step": 230344, "student_sha256": "d" * 64,
                "phase": "RECOVERY_1",
                "scores": {
                    "A.LINK": {"correct": 11, "total": 12},
                    "C.MUL": {"correct": 19, "total": 21},
                },
            })
            scope = next(
                row for row in board.rows["SYSTEM & QUALIFICATION"]
                if row["kind"] == "EXAM SCOPE")
            self.assertEqual(scope["grade"], "B")
            self.assertIn("B NOT EVALUATED", scope["detail"])
            self.assertIn("A+C", scope["detail"])
            self.assertIn("B NOT EVALUATED", board.operator_lines[0])

    def test_grade_a_live_exam_scope_separates_different_capability_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            common = {
                "event": "GRADE_A_LIVE_EXAM_COMMITTED",
                "grade": "A",
                "rubric": "a" * 64,
                "generator_version": "grade-a-live/v1",
                "optimizer_step": 200,
                "student_sha256": "d" * 64,
            }
            ingest(board, {
                **common,
                "generation": 1,
                "assessment_scope_sha256": "1" * 64,
                "cohort_sha256": "2" * 64,
                "cohort_file": f"cohorts/{'2' * 64}.json",
                "scores": {
                    "A.IDENTITY": {"correct": 12, "total": 12},
                    "A.LINK": {"correct": 11, "total": 12},
                },
            })
            ingest(board, {
                **common,
                "generation": 2,
                "assessment_scope_sha256": "3" * 64,
                "cohort_sha256": "4" * 64,
                "cohort_file": f"cohorts/{'4' * 64}.json",
                "scores": {
                    "A.IDENTITY": {"correct": 12, "total": 12},
                },
            })

            self.assertEqual(len(board.school_telemetry.latest), 2)

    def test_grade_a_live_exam_same_scope_rejects_capability_inventory_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            common = {
                "event": "GRADE_A_LIVE_EXAM_COMMITTED",
                "grade": "A",
                "rubric": "a" * 64,
                "assessment_scope_sha256": "1" * 64,
                "generator_version": "grade-a-live/v1",
                "optimizer_step": 200,
                "student_sha256": "d" * 64,
            }
            ingest(board, {
                **common,
                "generation": 1,
                "cohort_sha256": "2" * 64,
                "cohort_file": f"cohorts/{'2' * 64}.json",
                "scores": {
                    "A.IDENTITY": {"correct": 12, "total": 12},
                    "A.LINK": {"correct": 11, "total": 12},
                },
            })
            with self.assertRaisesRegex(ValueError, "RUBRIC_ITEMS_DRIFT"):
                ingest(board, {
                    **common,
                    "generation": 2,
                    "cohort_sha256": "3" * 64,
                    "cohort_file": f"cohorts/{'3' * 64}.json",
                    "scores": {
                        "A.IDENTITY": {"correct": 12, "total": 12},
                    },
                })

    def test_withheld_scope_receipt_bug_separates_partial_and_full_exams(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            common = {
                "event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                "grade": "B", "rubric": "b" * 64,
                "assessment_scope_sha256": "1" * 64,
                "generator_version": "grade-b-live/v1",
                "optimizer_step": 200, "student_sha256": "d" * 64,
                "withheld_capabilities": ["B.IFF"],
            }
            ingest(board, {
                **common, "generation": 1, "exam_plane": "ROUTINE",
                "cohort_sha256": "2" * 64,
                "cohort_file": f"cohorts/{'2' * 64}.json",
                "scores": {
                    "B.AND": {"correct": 5, "total": 12},
                    "B.NOT": {"correct": 7, "total": 12},
                },
            })
            ingest(board, {
                **common, "generation": 2, "exam_plane": "ROUTINE",
                "cohort_sha256": "3" * 64,
                "cohort_file": f"cohorts/{'3' * 64}.json",
                "scores": {
                    "B.AND": {"correct": 6, "total": 12},
                    "B.IFF": {"correct": 8, "total": 12},
                    "B.NOT": {"correct": 8, "total": 12},
                },
            })
            reports = [report for (grade, _, _), report in
                       board.school_telemetry.latest.items() if grade == "B"]
            self.assertEqual(len(reports), 2)
            self.assertEqual({report.total for report in reports}, {24, 36})

    def test_mismatched_checkpoint_in_one_exam_cannot_claim_mastery(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            corrupted = exam("A", 1, "rubric-a", {"A.IDENTITY": (12, 12)},
                             step=117000, sha="whole")
            corrupted["scores"]["A.IDENTITY"]["checkpoint_sha256"] = "different"
            with self.assertRaisesRegex(ValueError, "CHECKPOINT_MISMATCH"):
                ingest(board, corrupted)
            self.assertTrue(all(row.get("latest") == "-"
                                for row in board.rows["GRADES & MASTERY"]))
