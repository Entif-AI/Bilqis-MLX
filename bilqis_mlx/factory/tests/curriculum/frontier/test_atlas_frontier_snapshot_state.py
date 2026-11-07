"""A09.1a snapshot state, evidence, and identity invariants."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier import PlannerBudget, _build_snapshot
from bilqis_mlx.factory.model import AssessmentClass, LearningEvidence
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier import (
    _candidate, _rights,
)


class AtlasFrontierSnapshotStateTests(unittest.TestCase):
    def test_held_and_unimplemented_are_distinct_and_grade_neutral(self):
        candidate = _candidate()
        frontier, policy = _rights()
        budget = PlannerBudget(10, 100, 1000)
        first = _build_snapshot(
            candidate, frontier, policy, budget=budget,
            grade_labels=("B", "A"))
        second = _build_snapshot(
            candidate, frontier, policy, budget=budget,
            grade_labels=("A", "B"))
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())
        self.assertEqual(first.snapshot_sha256, second.snapshot_sha256)
        self.assertEqual(first.grade_labels, ("A", "B"))
        self.assertEqual(len(first.coverage_rows), 2)
        self.assertTrue(all(
            row.source_disposition == "SOURCE_ELIGIBLE"
            and row.implementation_status == "IMPLEMENTATION_UNCOVERED"
            for row in first.coverage_rows))
        self.assertEqual(first.source_held_rows[0].owner, "source:owner")
        self.assertEqual(
            first.source_held_rows[0].reason_code, "RIGHTS_MISSING")
        self.assertEqual(first.admitted_factory_release_sha256, None)
        self.assertEqual(first.qualification_epoch, 0)
        first.verify()
        with self.assertRaises(BilqisError):
            replace(
                first, source_held_rows=(
                    replace(
                        first.source_held_rows[0],
                        source_disposition="SOURCE_ELIGIBLE"),))
        with self.assertRaises(BilqisError):
            replace(first, snapshot_sha256="0" * 64).verify()
        with self.assertRaises(BilqisError):
            replace(first, schema="bilqis.factory-curriculum-snapshot/v999")

    def test_staged_admitted_and_learning_claims_remain_independent(self):
        candidate = replace(
            _candidate(), unverified_exposure_claims=("urn:one",),
            unverified_qualification_claims=("urn:two",))
        frontier, policy = _rights()
        snapshot = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            staged_release_sha256s=("a" * 64,),
            admitted_release_sha256="b" * 64,
            admission_receipt_sha256="c" * 64)
        self.assertEqual(snapshot.staged_factory_release_sha256s, ("a" * 64,))
        self.assertEqual(snapshot.admitted_factory_release_sha256, "b" * 64)
        self.assertEqual(snapshot.unverified_exposed_capability_ids, ("urn:one",))
        self.assertEqual(snapshot.unverified_qualified_capability_ids, ("urn:two",))
        self.assertEqual(snapshot.qualification_epoch, 0)

    def test_retained_evidence_order_is_fully_canonical(self):
        candidate = _candidate()
        frontier, policy = _rights()
        common = dict(
            assessment_class=AssessmentClass.PROMOTION,
            cohort_sha256="1" * 64,
            checkpoint_sha256="2" * 64,
            optimizer_step=3,
        )
        passing = LearningEvidence(**common, passed=True)
        failing = LearningEvidence(**common, passed=False)
        contaminated = LearningEvidence(
            **common, passed=True, contaminated_for_qualification=True)
        first = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            retained_evidence=(passing, failing, contaminated))
        second = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            retained_evidence=(contaminated, failing, passing))
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())
        self.assertEqual(first.snapshot_sha256, second.snapshot_sha256)

    def test_frontier_and_named_learning_states_are_snapshot_identity(self):
        candidate = replace(
            _candidate(), unverified_exposure_claims=("urn:one",),
            unverified_qualification_claims=("urn:two",))
        frontier, policy = _rights()
        base = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            candidate_frontier_sha256="3" * 64,
            ready_candidate_ids=("candidate.ready",), qualification_epoch=7)
        changed = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            candidate_frontier_sha256="4" * 64,
            ready_candidate_ids=("candidate.ready",), qualification_epoch=7)
        changed_state = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            candidate_frontier_sha256="3" * 64,
            ready_candidate_ids=("candidate.other",), qualification_epoch=8)
        self.assertEqual(base.candidate_frontier_sha256, "3" * 64)
        self.assertEqual(base.ready_candidate_ids, ("candidate.ready",))
        self.assertEqual(base.unverified_exposed_capability_ids, ("urn:one",))
        self.assertEqual(base.unverified_qualified_capability_ids, ("urn:two",))
        self.assertEqual(base.qualification_epoch, 7)
        self.assertNotEqual(base.snapshot_sha256, changed.snapshot_sha256)
        self.assertNotEqual(base.snapshot_sha256, changed_state.snapshot_sha256)

    def test_rights_epoch_and_budget_changes_are_visible(self):
        candidate = _candidate()
        frontier, policy = _rights()
        base = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000))
        changed = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(11, 100, 1000))
        self.assertNotEqual(base.snapshot_sha256, changed.snapshot_sha256)
        debt = _build_snapshot(
            candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000),
            retained_mastery_debt=("cap.z", "cap.a"),
            retained_debt_source_sha256="e" * 64)
        self.assertEqual(
            debt.retained_mastery_debt, ("cap.a", "cap.z"))
        self.assertNotEqual(base.snapshot_sha256, debt.snapshot_sha256)
        with self.assertRaises(BilqisError):
            _build_snapshot(
                candidate, frontier, policy,
                budget=PlannerBudget(10, 100, 1000),
                retained_mastery_debt=("cap.a",))
        with self.assertRaises(BilqisError):
            _build_snapshot(
                candidate, replace(frontier, rights_epoch=2),
                policy, budget=PlannerBudget(10, 100, 1000))


if __name__ == "__main__":
    unittest.main()
