"""Curriculum projection behavior from the original School50 suite."""
import io
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.dashboard import build, ingest
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.presentation.tests.school50.fixtures import exam


class CurriculumTests(unittest.TestCase):
    def test_profile_adoption_refreshes_integer_root_scope_without_release_replacement_shape(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                          tables=LETTER_TABLES, compact_header=True)
        board.school_telemetry = SchoolTelemetry(
            board, active_grades=("C",), champions={})

        ingest(board, {
            "event": "SCHOOL_EXECUTION_PROFILE_ADOPTED",
            "grade": "C", "generation": 1, "optimizer_step": 200,
            "profile_id": "school/u7c-full-b/numeric-0-10",
            "numeric_maximum": 10,
            "transition_kind": "REVISE_PROFILE",
        })

        self.assertEqual(board.state["numeric_maximum"], 10)
        rendered = board.render(width=320, height=30)
        self.assertIn("INTROOT", rendered)
        self.assertIn("0...10", rendered)

    def test_grade_release_replacement_removes_obsolete_curriculum_from_live_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {
                "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "grade": "B",
                "generation": 10,
                "capability": "B.OR",
                "optimizer_step": 100,
                "retained_optimizer_updates": 0,
            })
            ingest(board, exam(
                "B", 11, "old-rubric",
                {cap: (6, 12) for cap in (
                    "B.NOT", "B.AND", "B.OR", "B.XOR",
                    "B.IMPLIES", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS")},
                step=100))
            ingest(board, {
                "event": "SCHOOL_GRADE_RELEASE_REPLACED",
                "grade": "B",
                "generation": 12,
                "old_capabilities": [
                    "B.NOT", "B.AND", "B.OR", "B.XOR",
                    "B.IMPLIES", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"],
                "new_capabilities": [
                    "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"],
                "withheld_capabilities": [
                    "B.NOT", "B.OR", "B.XOR", "B.IMPLIES"],
            })
            self.assertNotIn(
                "B.OR",
                {row.get("capability") for row in board.rows["CANDIDATES"]})
            self.assertFalse(any(
                row.get("grade") == "B"
                for row in board._section_rows("GRADES & MASTERY")
                if row.get("row_type") == "summary"))
            self.assertTrue(any(
                row.get("kind") == "CURRICULUM" and
                "B.AND, B.IFF, B.COMPOSITE, B.IDBOOLOPS" in row.get("detail", "")
                for row in board.rows["SYSTEM & QUALIFICATION"]))
            self.assertEqual(board.school_telemetry.score_era, 1)
            self.assertFalse(board.school_telemetry.best)

    def test_session_start_reanchors_start_score_without_erasing_historical_best(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, exam("A", 10, "rubric-a", {"A.IDENTITY": (7, 12)},
                               step=100))
            ingest(board, exam("A", 20, "rubric-a", {"A.IDENTITY": (10, 12)},
                               step=120))
            # The live CLI prepares the board before the session-start event.
            # Receiving that same start boundary must not move START a second
            # time and zero the entire GREW column again.
            board.school_telemetry.begin_execution(grade="A", step=120)
            ingest(board, {"event": "SCHOOL_SESSION_STARTED", "grade": "A",
                           "generation": 20, "optimizer_step": 120,
                           "checkpoint_sha256": "a" * 64})
            ingest(board, exam("A", 30, "rubric-a", {"A.IDENTITY": (8, 12)},
                               step=136))

            mastery = next(
                row for row in board._section_rows("GRADES & MASTERY")
                if row.get("row_type") == "summary"
            )
            self.assertEqual(mastery["start"], "10/12")
            self.assertEqual(mastery["latest"], "8/12")
            self.assertEqual(mastery["best"], "10/12")
            self.assertIn("START", " ".join(board.operator_lines))
            display = board.render(width=180, height=42)
            self.assertNotIn("START", display)
            self.assertNotIn("FIRST", display)

    def test_begin_execution_resets_command_local_visit_and_rate_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for generation in (10, 11):
                ingest(board, {
                    "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                    "grade": "B", "generation": generation,
                    "capability": "B.AND", "optimizer_step": 100,
                    "attempted_optimizer_updates": 16,
                    "retained_optimizer_updates": 0,
                })
            self.assertEqual(board.school_telemetry.visits, 2)
            self.assertEqual(board.state["visits"], 2)

            board.school_telemetry.begin_execution(grade="B", step=100)

            self.assertEqual(board.school_telemetry.visits, 0)
            self.assertEqual(board.state["visits"], 0)
            self.assertEqual(board.state["attempted_steps"], 0)
            self.assertEqual(board.state["retained_steps"], 0)
            self.assertEqual(board.state["retained_visits"], 0)

    def test_curriculum_header_reports_visibility_and_trained_score(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                          tables=LETTER_TABLES)
        board.state.update(_all_grade_correct=100, _all_grade_total=144)
        board.rows["GRADES & MASTERY"].extend([
            {"grade": "A", "step": 126056, "attempt": 5789,
             "start": "70/72", "latest": "63/72", "best": "72/72",
             "outcome": "NO TITLE CHANGE"},
            {"grade": "B", "step": 126056, "attempt": 5789,
             "start": "33/72", "latest": "37/72", "best": "47/72",
             "outcome": "NO TITLE CHANGE"},
        ])
        for grade in ("A", "B"):
            for index in range(6):
                board.rows["BRIDGE FAMILIES"].append({
                    "grade": grade,
                    "family": f"{grade}.C{index}",
                    "step": 126056,
                    "attempt": 5789,
                    "start": "6/12",
                    "before": "-",
                    "after": "6/12",
                    "gain": "-",
                })

        available = board._section_rows("GRADES & MASTERY")
        self.assertEqual(
            board._section_label(
                "GRADES & MASTERY", len(available), available, available),
            "CURRICULUM [14/14 visible]: 100/144 (69.4%) TRAINED",
        )
        rendered = board.render(width=210, height=60)
        self.assertIn(
            "CURRICULUM [14/14 visible]: 100/144 (69.4%) TRAINED",
            rendered,
        )
        self.assertNotIn("TRAIN: S 126056", rendered)
