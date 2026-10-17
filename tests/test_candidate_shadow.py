"""Paired candidate trials remain observational under every outcome."""
from copy import deepcopy
import unittest

from bilqis_mlx.diagnostics.candidate_shadow import TrialShadowPolicy, review_candidate_shadow
from bilqis_mlx.diagnostics.health_shadow import ShadowContext, ShadowPhase
from bilqis_mlx.generated_assessment import make_cohort, score


class CandidateShadowTests(unittest.TestCase):
    def setUp(self):
        rows = [{"id": f"{cap}-{i}", "capability": cap, "gold": "TRUE"}
                for cap in ("A.RETAIN", "B.NEW") for i in range(4)]
        self.cohort = make_cohort(rows, generator_version="fixture/v1", seed=8, rubric_version="fixture/v1")
        correct = {row["id"]: "TRUE" for row in rows}
        wrong = {**correct, "A.RETAIN-0": "FALSE", "A.RETAIN-1": "FALSE"}
        self.parent = score(self.cohort, correct, {"sha256": "a" * 64, "optimizer_step": 10,
                                                "model_and_native_adamw": True})
        self.candidate = score(self.cohort, wrong, {"sha256": "b" * 64, "optimizer_step": 26,
                                                 "model_and_native_adamw": True})
        self.policy = TrialShadowPolicy("fixture-trial", "v1", (("A.RETAIN", 1), ("B.NEW", 1)))

    def review(self, **changes):
        args = dict(policy=self.policy, context=ShadowContext("B", ShadowPhase.REPLAY),
                    required_capabilities=("A.RETAIN", "B.NEW"),
                    trial_parent_sha256="a" * 64, decision_receipts=("fixture:one-recorded-visit",))
        args.update(changes)
        return review_candidate_shadow(self.parent, self.candidate, **args)

    def test_mature_paired_regression_proposes_rejection_without_mutation_or_teacher_penalty(self):
        before = deepcopy((self.parent, self.candidate))
        result = self.review()
        self.assertEqual(result.status, "WOULD_REJECT")
        self.assertEqual(result.regressions, (("A.RETAIN", 2),))
        self.assertFalse(result.actual_veto)
        self.assertEqual(result.actual_teacher_reward_updates, 0)
        self.assertIsNone(result.teacher_reward)
        self.assertEqual((self.parent, self.candidate), before)

    def test_acquisition_regression_remains_observation_only(self):
        result = self.review(context=ShadowContext("B", ShadowPhase.ACQUISITION))
        self.assertEqual(result.status, "ACQUISITION_OBSERVATION_ONLY")
        self.assertFalse(result.actual_veto)

    def test_fresh_cohort_or_wrong_parent_is_not_a_paired_trial(self):
        self.candidate["cohort_sha256"] = "c" * 64
        self.assertEqual(self.review().status, "NOT_MEASURED")
        self.candidate["cohort_sha256"] = self.parent["cohort_sha256"]
        self.assertEqual(self.review(trial_parent_sha256="c" * 64).status, "NOT_MEASURED")

    def test_multiple_actions_do_not_receive_unique_teacher_credit(self):
        result = self.review(decision_receipts=("fixture:visit-1", "fixture:visit-2"))
        self.assertEqual(result.teacher_credit, "NOT_MEASURED_MULTIPLE_ACTIONS")
        self.assertIsNone(result.teacher_reward)

    def test_missing_capability_or_threshold_cannot_reduce_required_denominator(self):
        self.assertEqual(self.review(required_capabilities=("A.RETAIN", "B.NEW", "C.MISSING")).status,
                         "NOT_MEASURED")
        self.assertEqual(self.review(policy=TrialShadowPolicy("fixture", "v1", (("B.NEW", 1),))).status,
                         "NOT_MEASURED")


if __name__ == "__main__":
    unittest.main()
