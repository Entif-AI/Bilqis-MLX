"""Events operator contracts preserve the human-run boundary."""
import io
import unittest
from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.presentation.school_telemetry import SchoolTelemetry


class EventsTests(unittest.TestCase):
    def test_live_visit_projects_rows_once_before_durable_replay(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        board.state["attempted_steps"] = 0
        telemetry = SchoolTelemetry(board, active_grades=("B",))
        visit = {
            "event": "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED", "grade": "B",
            "generation": 42, "optimizer_step": 100,
            "capability": "B.OR",
            "source_training_accuracy_before": 0.5,
            "source_training_accuracy_after": 0.5,
            "teacher_reward": 0.0, "teacher_policy": "test",
            "strategy": {}, "loss": 0.1, "gradient_norm": 0.1,
            "attempted_optimizer_updates": 16,
            "retained_optimizer_updates": 16,
            "checkpoint_status": "PROVISIONAL_UNTIL_NEXT_RECOVERY_BOUNDARY",
            "next_phase": "RECOVERY_1",
        }
        telemetry.ingest({**visit, "_live_ephemeral": True,
                          "_dashboard_redraw": False})
        self.assertEqual(board.state["attempted_steps"], 16)
        self.assertEqual(board.state["retained_steps"], 16)
        self.assertEqual(board.state["retained_visits"], 1)
        self.assertEqual(telemetry.visits, 1)
        self.assertEqual(len(board.rows["CANDIDATES"]), 1)
        self.assertEqual(len(board.rows["SOUP & TEACHER"]), 1)

        durable = {**visit, "checkpoint_status": "RECORDED_AT_BOUNDARY"}
        telemetry.ingest(durable)
        self.assertEqual(board.state["attempted_steps"], 16)
        self.assertEqual(board.state["retained_steps"], 16)
        self.assertEqual(board.state["retained_visits"], 1)
        self.assertEqual(telemetry.visits, 1)
        self.assertEqual(len(board.rows["CANDIDATES"]), 1)
        self.assertEqual(len(board.rows["SOUP & TEACHER"]), 1)
        self.assertFalse(durable["_dashboard_redraw"])

    def test_boolean_association_visit_is_visible_in_candidate_and_system_text(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        telemetry = SchoolTelemetry(board, active_grades=("A", "B", "C"))
        telemetry.ingest({
            "event": "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED",
            "grade": "B",
            "active_grade": "B",
            "generation": 43,
            "optimizer_step": 116,
            "capability": "B.IMPLIES",
            "retained_optimizer_updates": 0,
            "candidate_retention": {
                "decision": "REJECT",
                "reason": "NO_MEASURABLE_TARGET_GAIN",
            },
            "boolean_association_bridge": {
                "enabled": True,
                "active_for_visit": True,
                "borrowed_source_grades": ["A", "C"],
                "delivered_examples": 128,
            },
        })

        self.assertIn(
            "COMPOSE A+C->B x128",
            board.rows["CANDIDATES"][-1]["decision"],
        )
        compose = board.rows["SYSTEM & QUALIFICATION"][-1]
        self.assertEqual(compose["kind"], "COMPOSE")
        self.assertEqual(compose["grade"], "B")
        self.assertEqual(compose["detail"], "COMPOSE A+C->B x128 | B.IMPLIES")

    def test_live_exam_reports_actual_champion_title_movement_not_generic_saved_label(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        telemetry = SchoolTelemetry(
            board, active_grades=("B",), champions={"B": {"sha256": "f" * 64}})
        telemetry.ingest({
            "event": "SCHOOL_LIVE_EXAM_COMMITTED",
            "grade": "B",
            "generation": 51,
            "optimizer_step": 232392,
            "student_sha256": "a" * 64,
            "rubric": "b" * 64,
            "assessment_scope_sha256": "c" * 64,
            "cohort_sha256": "d" * 64,
            "cohort_file": "cohorts/d.json",
            "generator_version": "test/live-v1",
            "phase": "RECOVERY_1",
            "scores": {"B.OR": {"correct": 9, "total": 12}},
            "championship_epoch": {
                "earned_roles": ["B.OR"],
                "active_role_count": 1,
                "active_soup_grades": ["B"],
            },
        })

        mastery = board.rows["GRADES & MASTERY"][-1]
        self.assertIn("TITLE MOVED 1", mastery["outcome"])
        self.assertNotIn("CHAMPION SAVED", mastery["outcome"])
        champion = board.rows["SYSTEM & QUALIFICATION"][-1]
        self.assertEqual(champion["kind"], "CHAMPION")
        self.assertEqual(champion["grade"], "B")
        self.assertIn("B.OR 9/12", champion["detail"])
        self.assertIn("step 232392", champion["detail"])

    def test_live_exam_with_existing_champion_but_no_title_change_says_so(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        telemetry = SchoolTelemetry(
            board, active_grades=("B",), champions={"B": {"sha256": "f" * 64}})
        telemetry.ingest({
            "event": "SCHOOL_LIVE_EXAM_COMMITTED",
            "grade": "B",
            "generation": 52,
            "optimizer_step": 232392,
            "student_sha256": "a" * 64,
            "rubric": "b" * 64,
            "assessment_scope_sha256": "c" * 64,
            "cohort_sha256": "e" * 64,
            "cohort_file": "cohorts/e.json",
            "generator_version": "test/live-v1",
            "phase": "RECOVERY_1",
            "scores": {"B.OR": {"correct": 8, "total": 12}},
            "championship_epoch": {
                "earned_roles": [],
                "active_role_count": 1,
                "active_soup_grades": ["B"],
                "cross_origin_decisions": [{
                    "grade": "B",
                    "decision": "DENY_NO_STRICT_SCHOOL_VICTORY",
                }],
            },
        })

        mastery = board.rows["GRADES & MASTERY"][-1]
        self.assertIn("NO TITLE CHANGE", mastery["outcome"])
        self.assertNotIn("CHAMPION SAVED", mastery["outcome"])
        champion = board.rows["SYSTEM & QUALIFICATION"][-1]
        self.assertEqual(champion["kind"], "CHAMPION")
        self.assertIn("DENY_NO_STRICT_SCHOOL_VICTORY", champion["detail"])

    def test_live_exam_reports_settled_pair_as_no_rematch_not_new_measurement(self):
        board = Dashboard(stream=io.StringIO(), show_all_panels=True)
        telemetry = SchoolTelemetry(board, active_grades=("A",))
        telemetry.ingest({
            "event": "SCHOOL_LIVE_EXAM_COMMITTED", "grade": "A",
            "generation": 53, "optimizer_step": 300,
            "student_sha256": "a" * 64, "rubric": "b" * 64,
            "assessment_scope_sha256": "c" * 64,
            "cohort_sha256": "d" * 64, "cohort_file": "cohorts/d.json",
            "generator_version": "test/live-v1", "phase": "MAIN",
            "scores": {"A.IDENTITY": {"correct": 12, "total": 12}},
            "championship_epoch": {
                "earned_roles": [], "active_role_count": 1,
                "active_soup_grades": ["A"],
                "cross_origin_decisions": [{
                    "grade": "A", "capability": "A.IDENTITY",
                    "decision": "TITLE_MATCH_ALREADY_SETTLED",
                }],
            },
        })
        mastery = board.rows["GRADES & MASTERY"][-1]
        self.assertIn("PAIR ALREADY SETTLED", mastery["outcome"])
        champion = board.rows["SYSTEM & QUALIFICATION"][-1]
        self.assertIn("TITLE_MATCH_ALREADY_SETTLED", champion["detail"])
