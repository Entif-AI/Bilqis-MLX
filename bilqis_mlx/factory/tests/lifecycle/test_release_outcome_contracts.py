"""Pure plans cannot manufacture cutover or measured selection authority."""
from dataclasses import replace
import unittest

from bilqis_mlx.grade_release_plan import (CompleteBundleRef, CutoverAction, CutoverIntent,
    CutoverObservation, CutoverPlanStatus, plan_disposable_cutover)
from bilqis_mlx.selection_outcomes import (CapabilityOutcome, ComparisonStatus,
    SelectionTrial, compare_selection_trials)


class ReleasePlanTests(unittest.TestCase):
    def setUp(self):
        self.parent = CompleteBundleRef("a" * 64, "b" * 64, "c" * 64, 42, 2)
        self.intent = CutoverIntent(1, "parent/v1", "next/v1", self.parent,
            "d" * 64, "e" * 64, "f" * 64, "1" * 64, "2" * 64, 3)
        self.staged = replace(self.parent, catalog_sha256="2" * 64, vocabulary_size=3)

    def test_initial_and_staged_plans_always_require_executor_and_readback(self):
        for staged in (None, self.staged):
            with self.subTest(staged=staged):
                obs = CutoverObservation(1, self.parent, self.intent.identity, staged, "3" * 64 if staged else None)
                plan = plan_disposable_cutover(self.intent, obs)
                self.assertEqual(plan.status, CutoverPlanStatus.DRAFT_EXECUTOR_REQUIRED)
                self.assertIn(CutoverAction.READ_BACK_COMPLETE_BUNDLE, plan.actions)
                self.assertFalse(plan.training_authorized)

    def test_parent_drift_pending_intent_and_orphan_readback_are_blocked(self):
        baseline = CutoverObservation(1, self.parent)
        for updates in ({"current_generation": 2}, {"pending_intent_sha256": "9" * 64},
                        {"independent_bundle_readback_sha256": "3" * 64},
                        {"staged": replace(self.staged, optimizer_step=43)}):
            with self.subTest(updates=updates):
                plan = plan_disposable_cutover(self.intent, replace(baseline, **updates))
                self.assertEqual(plan.status, CutoverPlanStatus.BLOCKED)
                self.assertEqual(plan.actions, ())

    def test_reported_commit_does_not_skip_independent_readback(self):
        obs = CutoverObservation(2, self.staged, self.intent.identity, self.staged, "3" * 64)
        plan = plan_disposable_cutover(self.intent, obs)
        self.assertIn(CutoverAction.READ_BACK_COMPLETE_BUNDLE, plan.actions)

    def test_release_names_are_typed_not_truthy(self):
        for bad in ([], ["fake"], 123, " "):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                replace(self.intent, successor_release=bad)


class SelectionOutcomeTests(unittest.TestCase):
    def trial(self, candidate, scores=(8, 8), steps=10, attention=3):
        return SelectionTrial(candidate, "a" * 64, "b" * 64, "c" * 64, "d" * 64,
            "e" * 64, tuple(CapabilityOutcome(f"A.{i}", 8, score, 10) for i, score in enumerate(scores)),
            steps, attention, True)

    def test_ties_tradeoffs_and_negative_transfer_remain_visible(self):
        trials = (self.trial("base"), self.trial("dominated", (7, 7), 12),
                  self.trial("tradeoff", (9, 6)), self.trial("tie"))
        result = compare_selection_trials(trials)
        self.assertEqual(result.status, ComparisonStatus.UNQUALIFIED_FRONTIER)
        self.assertEqual(result.dominated, ("dominated",))
        self.assertEqual(result.frontier, ("base", "tie", "tradeoff"))
        self.assertIsNone(result.selected_grade)

    def test_missing_or_unmatched_observations_are_not_measured(self):
        trial = self.trial("a")
        for changes in ({"human_attention_seconds": None}, {"cumulative_replay_complete": False},
                        {"parent_bundle_sha256": "f" * 64}, {"assessment_sha256": "f" * 64},
                        {"protocol_sha256": "f" * 64}, {"source_scope_sha256": "f" * 64}):
            with self.subTest(changes=changes):
                result = compare_selection_trials((trial, replace(self.trial("b"), **changes)))
                self.assertEqual(result.status, ComparisonStatus.NOT_MEASURED)

    def test_malformed_candidate_and_capability_have_typed_errors(self):
        for bad in (["x"], {}, 1, " "):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                replace(self.trial("x"), candidate=bad)
            with self.subTest(capability=bad), self.assertRaises(ValueError):
                CapabilityOutcome(bad, 1, 2, 3)
