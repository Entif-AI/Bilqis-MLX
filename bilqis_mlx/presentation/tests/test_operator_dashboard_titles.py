"""Human root commands must not accidentally begin optimization."""
import io
import unittest
from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.presentation.school_telemetry import SchoolTelemetry


class OperatorTests(unittest.TestCase):
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
