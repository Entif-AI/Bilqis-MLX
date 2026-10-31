"""Events operator contracts preserve the human-run boundary."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.cli import main
from bilqis_mlx.presentation.spiral_dashboard import TABLES, Dashboard
from bilqis_mlx.presentation.dashboard import build, ingest
from bilqis_mlx.presentation.school_telemetry import SchoolTelemetry, LETTER_TABLES


class EventsTests(unittest.TestCase):
    def test_live_exam_reports_explicit_withheld_capability_as_not_measured(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        telemetry = SchoolTelemetry(board, active_grades=("A",))
        telemetry.ingest({
            "event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "A",
            "generation": 54, "optimizer_step": 301,
            "student_sha256": "a" * 64, "rubric": "b" * 64,
            "assessment_scope_sha256": "c" * 64,
            "cohort_sha256": "d" * 64, "cohort_file": "cohorts/d.json",
            "generator_version": "test/live-v1", "phase": "MAIN",
            "scores": {"A.IDENTITY": {"correct": 12, "total": 12}},
            "withheld_capabilities": ["A.EDGE"],
            "championship_epoch": {
                "earned_roles": [], "active_role_count": 0,
                "active_soup_grades": [], "cross_origin_decisions": [],
            },
        })
        champion = board.rows["SYSTEM & QUALIFICATION"][-1]
        self.assertEqual(champion["kind"], "CHAMPION")
        self.assertIn("withheld NOT_MEASURED: A.EDGE", champion["detail"])

    def test_flash_scheduler_exam_is_scope_bound_and_explicitly_non_title(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        telemetry = SchoolTelemetry(board, active_grades=("A", "B", "C"))
        telemetry.ingest({
            "event": "SCHOOL_FLASH_ROUTINE_EXAM_COMMITTED",
            "grade": "C",
            "generation": 53,
            "optimizer_step": 232472,
            "student_sha256": "a" * 64,
            "rubric": "b" * 64,
            "assessment_scope_sha256": "c" * 64,
            "cohort_sha256": "d" * 64,
            "cohort_file": "cohorts/d.json",
            "generator_version": "test/live-v1",
            "phase": "RECOVERY_1",
            "flash_scheduler_only": True,
            "scores": {
                "A.IDENTITY": {"correct": 12, "total": 12},
                "B.OR": {"correct": 8, "total": 12},
                "C.ADD": {"correct": 20, "total": 21},
            },
            "championship_epoch": {
                "earned_roles": [], "active_role_count": 19,
                "active_soup_grades": ["A", "B", "C"],
                "cross_origin_decisions": [],
            },
        })

        rows = list(board.rows["GRADES & MASTERY"])[-3:]
        self.assertTrue(all("FLASH SAMPLE" in row["outcome"] for row in rows))
        self.assertTrue(all("NO TITLES" in row["outcome"] for row in rows))
        self.assertTrue(all(key[2] == "c" * 64 for key in telemetry.latest))

    def test_dashboard_top_right_shows_step_rate_without_duplicate_all_grade_accuracy(self):
        now = [100.0]
        board = Dashboard(stream=io.StringIO(), show_all_panels=True,
                          clock=lambda: now[0])
        board.state.update(step=100, attempted_steps=0, retained_visits=1, visits=12)
        board.rows["GRADES & MASTERY"].extend([
            {"grade": "A", "latest": "71/72", "right_pct": "98.6%"},
            {"grade": "B", "latest": "47/72", "right_pct": "65.3%"},
            {"grade": "C", "latest": "137/147", "right_pct": "93.2%"},
        ])

        board.draw()
        board.state.update(attempted_steps=48, _rate_sample_eligible=False)
        now[0] = 101.0
        board.draw()  # Buffered boundary replay must not fake throughput.
        board.state["_rate_sample_eligible"] = True
        now[0] = 102.0
        board.draw()
        shown = board.render(width=150, height=38)

        self.assertIn("1,440 attempted steps/min (1 retained)", shown.splitlines()[0])
        self.assertNotIn("ALL 255/291 = 87.6% correct (last measured)", shown)

    def test_saved_grade_a_dashboard_replays_exam_without_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "events.jsonl").write_text(json.dumps({
                "event": "GRADE_A_EXAM_COMMITTED", "generation": 8,
                "phase": "RECOVERY_1", "rubric": "fixture-grade-a-rubric",
                "student_sha256": "fixture-intact-model", "scores": {
                    name: {"correct": 6, "total": 12}
                    for name in ("A.IDENTITY", "A.PARENT", "A.LINK", "A.MEMBER", "A.EDGE", "A.MAPS")
                }}) + "\n")
            board = build(run, stream=io.StringIO())
            output = board.render(width=115, height=38)
            self.assertIn("SEALED EXAM | RECOVERY_1", output)
            self.assertIn("36/ 36/ 36/ 72", output)
            self.assertIn(" 50% [  0%]", output)
            self.assertIn("50.0%", output)
            self.assertIn("RECOVERY_1", output)
            self.assertFalse((run / "state.json").exists())

    def test_event_ingest_updates_live_view_without_running_optimizer(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            ingest(board, {"event": "GRADE_A_TEACHER_VISIT_COMMITTED",
                           "capability": "A.LINK", "generation": 2,
                           "optimizer_step": 116776, "teacher_policy": "abc123",
                           "source_training_accuracy_before": .5,
                           "source_training_accuracy_after": .75,
                           "teacher_reward": .25, "next_phase": "MAIN"})
            shown = board.render(width=115, height=38)
            self.assertIn("PEND", shown)
            self.assertIn("EXAM PENDING", shown)
            self.assertIn("116776", shown)

    def test_letter_renderer_folds_bridge_families_into_mastery(self):
        self.assertEqual([name for name,_ in TABLES],[
            "CANDIDATES","SENTINEL & RETENTION","SOUP & TEACHER",
            "BRIDGE FAMILIES","GRADES & MASTERY","SYSTEM & QUALIFICATION"])
        self.assertEqual([name for name,_ in LETTER_TABLES],[
            "CANDIDATES","SENTINEL & RETENTION","SOUP & TEACHER",
            "GRADES & MASTERY","SYSTEM & QUALIFICATION"])
        with tempfile.TemporaryDirectory() as tmp:
            out=io.StringIO()
            with redirect_stdout(out):
                result=main(["dashboard","--run-dir",tmp])
            self.assertEqual(result,0)
            rendered_lines = out.getvalue().splitlines()
            self.assertTrue(rendered_lines[0].startswith("BILQIS"))
            self.assertIn("RUNTIME", rendered_lines[0])
            self.assertIn("RUN", rendered_lines[0])
            self.assertIn(Path(tmp).name, rendered_lines[1])
            self.assertEqual(rendered_lines[2], "")
            self.assertNotIn("SCHOOL50", rendered_lines[0])
            for name,_ in LETTER_TABLES:
                if name == "GRADES & MASTERY":
                    continue
                self.assertIn(name,out.getvalue())
            wide_lines = build(Path(tmp), stream=io.StringIO()).render(
                width=210, height=38).splitlines()
            grades_at = wide_lines[0].index("GRADES")
            caps_at = wide_lines[0].index("CAPS")
            self.assertEqual(wide_lines[1][grades_at:grades_at + 6].strip(), "0")
            self.assertEqual(wide_lines[1][caps_at:caps_at + 5].strip(), "0")
            self.assertIn("CURRICULUM [0/0 visible]", out.getvalue())
            self.assertNotIn("BRIDGE FAMILIES",out.getvalue())
            self.assertIn("READY_FOR_HUMAN_START",out.getvalue())
