import io
import unittest

from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES
from bilqis_mlx.presentation.teacher_vnext import teacher_fields


def promotion_exam(grade, stage, phase, *, generation=1):
    return {
        "event": "SCHOOL_LIVE_EXAM_COMMITTED",
        "grade": grade,
        "generation": generation,
        "introduction_stage": stage,
        "phase": phase,
    }


class OperatorMetricsTests(unittest.TestCase):
    def test_graduation_projection_counts_distinct_model_grades_not_repeat_boundaries(self):
        from bilqis_mlx.presentation.progression_projection import GraduationProjection

        projection = GraduationProjection()
        projection.observe({"event": "SCHOOL_NEW_RUN_INITIALIZED", "grade": "A"})
        for generation in (1, 3):
            projection.observe(promotion_exam("A", 0, "PROMOTION_SWEEP", generation=generation))
            projection.observe(promotion_exam(
                "A", 0, "AWAITING_NEXT_GRADE_WITH_DEBT", generation=generation + 1))
        projection.observe({
            "event": "SCHOOL_EXECUTION_PROFILE_ADOPTED", "grade": "B",
            "transition_kind": "APPEND_GRADE",
        })
        for generation in (5, 7, 9):
            projection.observe(promotion_exam("B", 0, "PROMOTION_SWEEP", generation=generation))
            projection.observe(promotion_exam(
                "B", 0, "AWAITING_NEXT_GRADE_WITH_DEBT", generation=generation + 1))
        projection.observe({
            "event": "SCHOOL_SEMANTIC_CATALOG_PROFILE_ADOPTED", "grade": "C",
        })

        self.assertEqual(projection.summary(), "0.0.0 / 3.5.5")

    def test_compact_header_reports_active_integer_root_scope(self):
        board = Dashboard(
            stream=io.StringIO(), clock=lambda: 1.0,
            show_all_panels=True, tables=LETTER_TABLES,
            compact_header=True)
        board.state.update(numeric_maximum=10)

        headings, values = board.render(width=320, height=20).splitlines()[:2]

        start = headings.index("INTROOT")
        self.assertEqual(values[start:start + 7].strip(), "0...10")

    def test_broken_wide_c_receipt_projects_pending_entry_rung_four(self):
        from bilqis_mlx.profiles.catalog import displayed_numeric_maximum

        self.assertEqual(displayed_numeric_maximum({
            "result": "ACTIVE_GRADE_A", "numeric_maximum": 10,
            "numeric_scope_final_maximum": None,
            "school": {"active_grades": ["A", "B", "C"]},
        }), 4)
        self.assertEqual(displayed_numeric_maximum({
            "result": "ACTIVE_GRADE_C", "numeric_maximum": 10,
            "numeric_scope_final_maximum": 10,
            "school": {"active_grades": ["A", "B", "C"]},
        }), 10)

    def test_compact_header_reports_growth_per_retention_and_graduation_triplets(self):
        board = Dashboard(
            stream=io.StringIO(), clock=lambda: 3600.0,
            show_all_panels=True, tables=LETTER_TABLES,
            compact_header=True)
        board.started = 0.0
        board.state.update(
            retained_visits=32, visits=407, attempted_steps=6400,
            grew=10, graduations="2.11.18 / 5.28.57")

        headings, values = board.render(width=320, height=20).splitlines()[:2]

        start = headings.index("G/RTN")
        self.assertEqual(values[start:start + 6].strip(), "+0.31")
        start = headings.rindex("GRAD")
        self.assertEqual(
            values[start:start + len("2.11.18 / 5.28.57")].strip(),
            "2.11.18 / 5.28.57")

    def test_compact_header_explicitly_marks_graduation_sweep(self):
        board = Dashboard(
            stream=io.StringIO(), clock=lambda: 1.0,
            show_all_panels=True, tables=LETTER_TABLES,
            compact_header=True)
        board.started = 0.0
        board.state.update(
            phase="PROMOTION_SWEEP", prefix="B", visits=12,
            graduations="0.1.2 / 3.7.11")

        headings, values = board.render(width=260, height=20).splitlines()[:2]

        start = headings.index("SWEEP")
        self.assertEqual(values[start:start + len("GRADUATION B")].strip(),
                         "GRADUATION B")

    def test_policy_retention_probability_uses_supported_pre_outcome_evidence(self):
        history = {}
        base = {
            "grade": "C",
            "capability": "C.ADD",
            "teacher_policy": "policy-alpha",
            "candidate_retention": {"phase": "RECOVERY_1"},
        }
        outcomes = ("PROVISIONAL", "REJECT", "REJECT", "REJECT",
                    "PROVISIONAL", "REJECT", "REJECT", "REJECT")
        for decision in outcomes:
            fields = teacher_fields({
                **base,
                "candidate_retention": {
                    "phase": "RECOVERY_1", "decision": decision,
                },
            }, history)

        # Eight prior observations now support the next prediction at 2 / 8.
        fields = teacher_fields({
            **base,
            "candidate_retention": {
                "phase": "RECOVERY_1", "decision": "REJECT",
            },
        }, history)
        self.assertEqual(fields["p_ret"], "25.0%")
        self.assertEqual(fields["health"], "PRODUCTIVE")

    def test_historical_explicit_policy_prediction_still_wins(self):
        fields = teacher_fields({
            "teacher_outcome_prediction_before": {
                "retention_probability": .375,
            },
            "teacher_health": {"status": "PRODUCTIVE"},
        }, {})
        self.assertEqual(fields["p_ret"], "37.5%")
        self.assertEqual(fields["health"], "PRODUCTIVE")

    def test_graduation_projection_tracks_current_and_lifetime_attempts(self):
        from bilqis_mlx.presentation.progression_projection import GraduationProjection

        projection = GraduationProjection()

        # Lifetime: one semantic-stage success.
        projection.observe(promotion_exam("A", 0, "PROMOTION_SWEEP", generation=1))
        projection.observe(promotion_exam("A", 0, "MAIN", generation=2))
        projection.observe(promotion_exam("A", 1, "MAIN", generation=3))

        # Lifetime: one grade-boundary success.
        projection.observe(promotion_exam("A", 1, "PROMOTION_SWEEP", generation=4))
        projection.observe(
            promotion_exam("A", 1, "AWAITING_NEXT_GRADE_WITH_DEBT", generation=5))

        # Lifetime: one failed attempt.
        projection.observe(promotion_exam("B", 0, "PROMOTION_SWEEP", generation=6))
        projection.observe(promotion_exam("B", 0, "RECOVERY_1", generation=7))
        self.assertEqual(projection.summary(), "0.0.0 / 2.2.3")

        projection.begin_execution()

        # Current run: semantic-stage success.
        projection.observe(promotion_exam("B", 0, "PROMOTION_SWEEP", generation=8))
        projection.observe(promotion_exam("B", 0, "MAIN", generation=9))
        projection.observe(promotion_exam("B", 1, "MAIN", generation=10))

        # Current run: direct transition to a pre-admitted next letter grade.
        projection.observe(promotion_exam("B", 1, "PROMOTION_SWEEP", generation=11))
        projection.observe(promotion_exam("B", 1, "MAIN", generation=12))
        projection.observe({
            "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
            "grade": "C",
        })

        # Current run: failed sweep.
        projection.observe(promotion_exam("C", 0, "PROMOTION_SWEEP", generation=13))
        projection.observe(promotion_exam("C", 0, "RECOVERY_1", generation=14))

        self.assertEqual(projection.summary(), "1.2.3 / 3.4.6")


if __name__ == "__main__":
    unittest.main()
