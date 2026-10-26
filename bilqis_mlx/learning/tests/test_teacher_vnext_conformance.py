import json
from pathlib import Path
import unittest


FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "teacher_vnext_conformance_v1.json"
)


class TeacherVNextConformanceTests(unittest.TestCase):
    def test_architecture_neutral_fixture_round_trips_portable_contract(self):
        from bilqis_mlx.learning.teacher_outcomes import (
            observe, predict, proposed_action, student_region,
            validate_portable_observation,
        )

        fixture = json.loads(FIXTURE.read_text())
        region = student_region(**fixture["region"])
        action = proposed_action(**fixture["action"])
        observation = observe(
            {}, region=region, action=action, **fixture["outcome"])
        validate_portable_observation(observation)

        expected = fixture["expected"]
        for field in (
            "capability_score_band", "grade_score_band",
            "grade_score_shape",
            "rejection_pressure_band", "attempts_since_retained_band",
            "mastery_debt_band", "mastery_debt_shape",
        ):
            self.assertEqual(region[field], expected[field])

        teacher = {}
        observation = observe(
            teacher, region=region, action=action, **fixture["outcome"])
        estimate = predict(teacher, region=region, action=action)
        self.assertEqual(
            estimate["retention_probability"],
            expected["retention_probability_after_one"])
        self.assertEqual(
            estimate["expected_target_delta"],
            expected["expected_target_delta_after_one"])
        self.assertEqual(
            estimate["expected_protected_net_delta"],
            expected["expected_protected_net_delta_after_one"])
        self.assertEqual(
            estimate["expected_candidate_steps"],
            expected["expected_candidate_steps_after_one"])

    def test_portable_region_rejects_exact_checkpoint_identity(self):
        from bilqis_mlx.learning.teacher_outcomes import (
            OBSERVATION_SCHEMA, REGION_SCHEMA, validate_portable_observation,
        )

        observation = {
            "schema": OBSERVATION_SCHEMA,
            "region": {
                "schema": REGION_SCHEMA,
                "key": "region",
                "student_sha256": "a" * 64,
            },
            "proposed_action": {
                "family": "GLOBAL_CHALLENGER",
                "effective_policy_key": "key",
            },
            "retained": False,
            "rejection_reason": "NO_MEASURABLE_TARGET_GAIN",
            "target_delta": 0,
            "protected_net_delta": 0,
            "worst_protected_loss": 0,
            "attempted_steps": 16,
            "retained_steps": 0,
            "wall_seconds": 1.0,
        }
        with self.assertRaisesRegex(ValueError, "TEACHER_OUTCOME_REGION_OVERFRAGMENTED"):
            validate_portable_observation(observation)


if __name__ == "__main__":
    unittest.main()
