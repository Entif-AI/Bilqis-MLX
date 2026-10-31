"""Curriculum projection behavior from the original School50 suite."""
import io
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.dashboard import build, ingest


class CurriculumTests(unittest.TestCase):
    def test_cross_cohort_top_resets_when_next_grade_is_admitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for generation, score in ((1, 10), (2, 8)):
                ingest(board, {
                    "event": "SCHOOL_LIVE_EXAM_COMMITTED",
                    "grade": "A", "generation": generation,
                    "rubric": "a" * 64,
                    "cohort_sha256": str(generation) * 64,
                    "cohort_file": f"cohorts/{str(generation) * 64}.json",
                    "generator_version": "grade-a-live/v1",
                    "optimizer_step": 100 + generation,
                    "student_sha256": str(generation) * 64,
                    "scores": {"A.IDENTITY": {"correct": score, "total": 12}},
                })
            before = next(
                row for row in reversed(board._section_rows("GRADES & MASTERY"))
                if row.get("grade") == "A" and row.get("row_type") == "summary"
            )
            self.assertEqual(before["best"], "10/12")

            ingest(board, {
                "event": "SCHOOL_NEXT_GRADE_COURSE_ADMITTED",
                "grade": "B", "generation": 3, "optimizer_step": 102,
            })
            ingest(board, {
                "event": "SCHOOL_LIVE_EXAM_COMMITTED",
                "grade": "A", "generation": 4,
                "rubric": "a" * 64,
                "cohort_sha256": "4" * 64,
                "cohort_file": f"cohorts/{'4' * 64}.json",
                "generator_version": "grade-a-live/v1",
                "optimizer_step": 103,
                "student_sha256": "4" * 64,
                "scores": {"A.IDENTITY": {"correct": 7, "total": 12}},
            })
            after = next(
                row for row in reversed(board._section_rows("GRADES & MASTERY"))
                if row.get("grade") == "A" and row.get("row_type") == "summary"
            )
            self.assertEqual(after["best"], "7/12")
            self.assertTrue(any(
                row.get("kind") == "SCORE ERA" and
                "NEXT_GRADE_ADMITTED" in row.get("detail", "")
                for row in board.rows["SYSTEM & QUALIFICATION"]
            ))
