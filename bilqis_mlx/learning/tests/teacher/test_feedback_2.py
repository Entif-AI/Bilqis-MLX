"""Feedback."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests,
)


class Feedback2Tests(CausalTeacherExperimentTests):
    def test_realized_delivery_identity_tracks_delivery_not_requested_old_mix(self):
        import bilqis_mlx.learning.learning_experiment as experiment
        controls = ({
            "effective_old_grade_examples": 5,
            "depth_control": "SOURCE_TOKEN_LENGTH_PROXY",
            "contrast_control": "SOURCE_GROUP_DIVERSITY",
        },)
        common = dict(
            candidate_steps=16, batch_size=32, policy_controls=controls,
            guidance_applied_steps=0, enrichment_examples=0)
        requested_four = experiment.realized_teacher_action(
            {"lr": .0001, "old": 4, "distill": .15}, **common)
        requested_twenty = experiment.realized_teacher_action(
            {"lr": .0001, "old": 20, "distill": .15}, **common)
        changed_delivery = experiment.realized_teacher_action(
            {"lr": .0001, "old": 20, "distill": .15}, **{
                **common,
                "policy_controls": ({
                    "effective_old_grade_examples": 6,
                    "depth_control": "SOURCE_TOKEN_LENGTH_PROXY",
                    "contrast_control": "SOURCE_GROUP_DIVERSITY",
                },),
            })

        self.assertEqual(requested_four["key"], requested_twenty["key"])
        self.assertNotEqual(requested_four["key"], changed_delivery["key"])
