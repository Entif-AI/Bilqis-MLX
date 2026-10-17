"""Negative-control replay tests for unratified health-shadow research."""
from __future__ import annotations

import unittest

from bilqis_mlx.diagnostics.health_shadow import (ShadowContext, ShadowHealthState,
    ShadowPhase, ShadowPolicy, replay_health_shadow)
from bilqis_mlx.diagnostics.observations import CapabilityObservation, ExamObservation


POLICY = ShadowPolicy("health-shadow", "v1", 3, 2, 2, 0, 1)


def cap(name: str, correct: int, total: int = 10, *, baseline: int = 5) -> CapabilityObservation:
    return CapabilityObservation(name, correct, total, baseline, total - baseline, baseline, total - baseline,
                                 0, total - correct, total - correct, correct,
                                 component_majority_baseline=baseline, component_classes_measured=True)


def observation(step: int, score: int, *, cohort: str = "c" * 64, source: str = "s" * 64,
                student: str | None = None, caps: tuple[CapabilityObservation, ...] | None = None) -> ExamObservation:
    return ExamObservation(cohort, student or f"{step:064x}", step, "r" * 64, "v1",
                           caps or (cap("B.CAP", score), cap("B.HEALTHY", 10)),
                           source_manifest_sha256=source, generator_code_sha256="g" * 64,
                           run_id="run-1", assessment_scope_sha256="a" * 64)


def replay(history, required=("B.CAP", "B.HEALTHY"), *, active="B", phase=ShadowPhase.REPLAY):
    return replay_health_shadow(tuple(history), required_capabilities=required, policy=POLICY,
                                context=ShadowContext(active, phase))


class HealthShadowTests(unittest.TestCase):
    def test_policy_requires_identity_and_output_carries_digest(self):
        with self.assertRaisesRegex(ValueError, "IDENTITY"):
            ShadowPolicy("", "", 3, 2, 2, 0, 1)
        result = replay((observation(1, 10), observation(2, 9), observation(3, 10)))
        self.assertEqual(result.policy_digest, POLICY.digest)
        self.assertEqual(result.end_of_run_alerts, ())

    def test_normal_variation_and_healthy_peer_do_not_alert(self):
        result = replay((observation(1, 10), observation(2, 9), observation(3, 10)))
        self.assertEqual(result.by_capability["B.CAP"].state, ShadowHealthState.ACTIVE)
        self.assertEqual(result.by_capability["B.HEALTHY"].state, ShadowHealthState.ACTIVE)

    def test_stagnation_near_own_baseline_is_not_global_median_inference(self):
        result = replay((observation(1, 5), observation(2, 5), observation(3, 5)))
        self.assertEqual(result.by_capability["B.CAP"].state, ShadowHealthState.WATCH)
        self.assertEqual(result.required_capability_debt, ("B.CAP",))

    def test_earlier_grade_regression_in_acquisition_stays_watch_over_many_observations(self):
        history = tuple(observation(i, score, caps=(cap("A.CAP", score),))
                        for i, score in enumerate((10, 7, 7, 7), 1))
        result = replay(history, required=("A.CAP",), active="B", phase=ShadowPhase.ACQUISITION)
        self.assertEqual(result.by_capability["A.CAP"].state, ShadowHealthState.WATCH)

    def test_recovery_and_perfect_reintegration_are_distinct_and_debt_uses_latest_score(self):
        recovering = replay([observation(i, score) for i, score in enumerate((10, 10, 7, 7, 8), 1)],
                            required=("B.CAP",))
        self.assertEqual(recovering.by_capability["B.CAP"].state, ShadowHealthState.RECOVERY_RECOMMENDATION)
        self.assertEqual(recovering.required_capability_debt, ("B.CAP",))
        reintegrated = replay([observation(i, score) for i, score in enumerate((10, 10, 7, 7, 8, 10), 1)],
                              required=("B.CAP",))
        self.assertEqual(reintegrated.by_capability["B.CAP"].state, ShadowHealthState.REINTEGRATION_RECOMMENDATION)
        self.assertEqual(reintegrated.required_capability_debt, ())

    def test_latest_contiguous_cohort_is_used_and_gap_is_reported(self):
        result = replay((observation(1, 1, cohort="o" * 64), observation(2, 10),
                         observation(3, 10), observation(4, 7)))
        self.assertTrue(result.lineage_gap)
        self.assertIn("drift", result.lineage_note)
        self.assertEqual(result.by_capability["B.CAP"].state, ShadowHealthState.WATCH)

    def test_rejects_bad_scores_duplicate_capabilities_and_repeated_checkpoint(self):
        with self.assertRaisesRegex(ValueError, "INVALID_CORRECT_TOTAL"):
            replay((observation(1, 10, caps=(cap("B.CAP", 11),)),))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CAPABILITY"):
            replay((observation(1, 10, caps=(cap("B.CAP", 10), cap("B.CAP", 10))),))
        result = replay((observation(1, 10), observation(2, 7, student=f"{1:064x}")), required=("B.CAP",))
        self.assertEqual(result.by_capability["B.CAP"].state, ShadowHealthState.NOT_MEASURED)

    def test_changed_source_starts_new_unmeasured_segment(self):
        result = replay((observation(1, 10), observation(2, 7, source="x" * 64)), required=("B.CAP",))
        self.assertTrue(result.lineage_gap)
        self.assertEqual(result.by_capability["B.CAP"].state, ShadowHealthState.NOT_MEASURED)


if __name__ == "__main__":
    unittest.main()
