"""Summary projection behavior from the original School50 suite."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.presentation.dashboard import build, ingest
from bilqis_mlx.presentation.tests.school50.fixtures import exam


class SummaryTests(unittest.TestCase):
    def test_independent_perfect_grade_bests_do_not_claim_cumulative_graduation(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for generation, a, b in ((1, 12, 10), (2, 8, 12), (3, 11, 11)):
                ingest(board, {
                    "event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "grade": "B",
                    "generation": generation, "rubric": "b" * 64,
                    "cohort_sha256": str(generation) * 64,
                    "generator_version": "grade-b-live/v1",
                    "cohort_file": f"cohorts/{str(generation)*64}.json",
                    "optimizer_step": 200 + generation,
                    "student_sha256": str(generation) * 64,
                    "phase": "RECOVERY_1",
                    "scores": {"A.IDENTITY": {"correct": a, "total": 12},
                               "B.NOT": {"correct": b, "total": 12}},
                })
            grades = {row["grade"]: row for row in
                      board._section_rows("GRADES & MASTERY")
                      if row.get("row_type") == "summary"}
            self.assertEqual(grades["A"]["best"], "12/12")
            self.assertEqual(grades["B"]["best"], "12/12")
            rows = [row for row in board.rows["SYSTEM & QUALIFICATION"]
                    if row["kind"] == "CUMULATIVE"]
            self.assertEqual(len(rows), 1)
            self.assertIn("latest 22/24", rows[0]["detail"])
            self.assertIn("best same student 22/24", rows[0]["detail"])
            self.assertIn("24/24 REQUIRED", rows[0]["detail"])
            self.assertIn("CUMULATIVE", " ".join(board.operator_lines))
            self.assertNotIn("QUALIFIED", " ".join(board.operator_lines))

            ingest(board, {"event": "SCHOOL_SESSION_STOPPED", "grade": "B",
                           "stop_reason": "TIME_LIMIT_REACHED",
                           "visits_this_command": 3, "elapsed_seconds": 5401.,
                           "optimizer_step": 203})
            self.assertIn("TIME_LIMIT_REACHED", board.mode)
            self.assertIn("24/24 REQUIRED", " ".join(board.operator_lines))

    def test_cumulative_perfect_requires_one_complete_scored_student(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                "grade": "B", "generation": 1, "rubric": "b" * 64,
                "cohort_sha256": "c" * 64, "cohort_file": f"cohorts/{'c'*64}.json",
                "generator_version": "grade-b-live/v1", "optimizer_step": 300,
                "student_sha256": "d" * 64, "phase": "AWAITING_NEXT_GRADE",
                "scores": {"A.IDENTITY": {"correct": 12, "total": 12},
                           "B.NOT": {"correct": 12, "total": 12}}})
            rows = [row for row in board.rows["SYSTEM & QUALIFICATION"]
                    if row["kind"] == "CUMULATIVE"]
            self.assertEqual(len(rows), 1)
            self.assertIn("24/24", rows[0]["detail"])
            self.assertIn("GATE MET", rows[0]["detail"])

    def test_cumulative_backward_a_replay_shows_a_as_exam_target_not_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp),stream=io.StringIO())
            ingest(board,{"event":"SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                "grade":"A","phase":"MAIN","generation":27,
                "rubric":"b"*64,"cohort_sha256":"8"*64,
                "generator_version":"bilqis.mlx.grade-b-connectives-constructor/v1",
                "cohort_file":f"cohorts/{'8'*64}.json",
                "optimizer_step":154008,"student_sha256":"8"*64,
                "scores":{"A.IDENTITY":{"correct":12,"total":12},
                           "B.NOT":{"correct":9,"total":12}}})
            self.assertEqual(board.school_telemetry.last_exam_grade,"A")
            self.assertIn("LATEST A 12/12",board.operator_lines[0])
            self.assertEqual(board.state["prefix"],"A")

    def test_saved_b_grade_dashboard_shows_current_cumulative_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            state = {"curriculum_mode":"bilqis.mlx.grade-a-b-live/20261015-v1",
                "result":"GRADE_B_REVALIDATING_A", "teacher":{"events":4000},
                "school":{"stage":"MAIN", "active_grades":["A","B"],
                    "grade_index":0,"visits":1000,
                    "current_student":{"optimizer_step":154000},
                    "champions":{}},"last_exam":None}
            (run/"state.json").write_text(json.dumps(state))
            board = build(run,stream=io.StringIO())
            source = next(row["detail"] for row in
                          board.rows["SYSTEM & QUALIFICATION"]
                          if row["kind"]=="RUBRIC")
            self.assertIn("generated 144",source)
            self.assertIn("same-checkpoint",source)

    def test_capability_best_below_perfect_is_displayed_without_grade_mastery(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "SCHOOL_CAPABILITY_BEST_COMMITTED",
                           "grade": "A", "optimizer_step": 116776,
                           "student_sha256": "e" * 64,
                           "rubric": "a" * 64,
                           "scores": {"A.IDENTITY": {"correct": 5, "total": 12},
                                      "A.LINK": {"correct": 7, "total": 12}},
                           "capabilities": ["A.IDENTITY", "A.LINK"]})
            message = board.rows["SYSTEM & QUALIFICATION"][-1]["detail"]
            self.assertIn("A.IDENTITY", message)
            self.assertIn("A.LINK", message)
            self.assertIn("CAPABILITY BEST SAVED", message)
            self.assertIn("eeeeeeeeee", message)
            self.assertIn("TITLE SEPARATE", message)
            self.assertIn("NOT grade mastery", message)
            self.assertFalse(board.rows["SENTINEL & RETENTION"])

    def test_first_latest_best_and_regression_use_same_sealed_rubric(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            for index, numbers in enumerate(((7, 5), (10, 8), (6, 4)), 1):
                ingest(board, exam("A", index * 5, "rubric-a",
                    {"A.IDENTITY": (numbers[0], 12), "A.PARENT": (numbers[1], 12)},
                    step=116760 + 16 * index))
            rows = board._section_rows("BRIDGE FAMILIES")
            self.assertEqual(len(rows), 2)
            identity = next(r for r in rows if r["family"] == "A.IDENTITY")
            self.assertEqual(identity["start"], "7/12")
            self.assertEqual(identity["before"], "10/12")
            self.assertEqual(identity["after"], "6/12")
            self.assertEqual(identity["gain"], "-4")
            mastery = [row for row in board._section_rows("GRADES & MASTERY")
                       if row.get("row_type") == "summary"]
            self.assertEqual(len(mastery), 1)
            self.assertEqual(mastery[0]["latest"], "10/24")
            self.assertEqual(mastery[0]["best"], "18/24")
            self.assertEqual(mastery[0]["to100"], "14")
            operator = " ".join(board.operator_lines)
            self.assertIn("START SEALED A 12/24", operator)
            self.assertIn("LATEST A 10/24", operator)
            self.assertIn("BEST A 18/24", operator)
            self.assertIn("TO100 14/24", operator)
            text = board.render(width=180, height=42)
            self.assertNotIn("START SEALED A 12/24", text)
            self.assertNotIn("LATEST A 10/24", text)
            self.assertNotIn("BEST A 18/24", text)
            self.assertNotIn("TO100 14/24", text)

    def test_future_b_cumulative_exam_preserves_per_grade_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, exam("A", 8, "rubric-a", {"A.IDENTITY": (9, 12)},
                               step=117000, sha="old-a"))
            ingest(board, exam("B", 12, "rubric-a+b", {
                "A.IDENTITY": (8, 12), "B.DIRECTION": (11, 12)},
                step=117500, sha="whole-a+b"))
            mastery = {r["grade"]: r for r in board._section_rows("GRADES & MASTERY")}
            self.assertEqual(set(mastery), {"A", "B"})
            self.assertEqual(mastery["A"]["latest"], "8/12")
            self.assertEqual(mastery["B"]["latest"], "11/12")
            self.assertEqual(mastery["A"]["step"], 117500)
            identity = next(r for r in board._section_rows("BRIDGE FAMILIES")
                            if r["family"] == "A.IDENTITY")
            self.assertEqual(identity["gain"], "-")
            self.assertEqual(identity["before"], "-")
            self.assertTrue(all(not r.get("mastered", False) for r in mastery.values()))

    def test_historical_champion_does_not_hide_latest_grade_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "state.json").write_text(json.dumps({
                "school": {"active_grades": ["A", "B"],
                           "current_student": {"optimizer_step": 123400},
                           "champions": {"A": {"optimizer_step": 123000}},
                           "stage": "MAIN", "visits": 4},
                "teacher": {"events": 10}, "result": "ACTIVE_SCHOOL"}))
            board = build(run, stream=io.StringIO())
            ingest(board, exam("B", 5, "rubric-a+b", {
                "A.IDENTITY": (7, 12), "B.FOCUS": (8, 12)},
                step=123400, sha="student-B-step"))
            latest_a = next(x for x in board._section_rows("GRADES & MASTERY")
                            if x["grade"] == "A")
            self.assertTrue(latest_a["mastered"])
            self.assertIn("CURRENT REGRESSION", latest_a["outcome"])
            self.assertEqual(latest_a["latest"], "7/12")
            self.assertEqual(board.state["prefix"], "B")
            self.assertEqual(board.grade_program, ("A", "B"))
