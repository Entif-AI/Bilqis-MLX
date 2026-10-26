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
        self.assertEqual(projection.summary(), "0.0.0 / 1.2.3")

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

        self.assertEqual(projection.summary(), "1.2.3 / 2.4.6")


if __name__ == "__main__":
    unittest.main()
