"""A09.1b immutable event reconciliation behavior."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier import PlannerBudget, _build_snapshot
from bilqis_mlx.factory.atlas_frontier_events import (
    CorrectionEvent, FactoryAdmissionEvent, LearningEvidenceEvent,
    PlannerPolicyEvent, SourceReleaseEvent, reconcile,
)
from bilqis_mlx.factory.model import AssessmentClass, LearningEvidence
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier import _candidate, _rights


def _snapshot(**kwargs):
    candidate = kwargs.pop("candidate", _candidate())
    frontier, policy = _rights()
    return _build_snapshot(
        candidate, frontier, policy, budget=PlannerBudget(10, 100, 1000), **kwargs)


def _rehash(snapshot, **changes):
    draft = replace(snapshot, snapshot_sha256="0" * 64, **changes)
    return replace(draft, snapshot_sha256=draft.expected_digest())


def _event(event_type, snapshot, **kwargs):
    event = event_type(
        predecessor_sha256=snapshot.snapshot_sha256,
        generation=snapshot.event_generation + 1,
        source_provenance_sha256=kwargs.pop(
            "source_provenance_sha256", snapshot.source_coverage_sha256),
        event_sha256="0" * 64,
        **kwargs,
    )
    return replace(event, event_sha256=event.expected_digest())


def _evidence(*, passed=True, step=3):
    return LearningEvidence(
        AssessmentClass.PROMOTION, "1" * 64, "2" * 64, step, passed)


class AtlasFrontierEventTests(unittest.TestCase):
    def test_learning_event_is_deterministic_and_replay_is_idempotent(self):
        base = _snapshot()
        evidence = _evidence()
        event = _event(
            LearningEvidenceEvent, base, evidence=(evidence,), mastery_debt=("cap.z",),
            debt_source_sha256="d" * 64, qualification_epoch=1, accepted=True)
        first = reconcile(base, event)
        second = reconcile(base, event)
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())
        self.assertEqual(reconcile(first, event), first)
        self.assertEqual(first.predecessor_sha256, base.snapshot_sha256)
        self.assertEqual(first.event_generation, 1)
        self.assertEqual(first.retained_evidence, (evidence,))
        self.assertEqual(first.retained_mastery_debt, ("cap.z",))
        no_change = _event(
            LearningEvidenceEvent, base, evidence=(), mastery_debt=(),
            debt_source_sha256=None, qualification_epoch=0, accepted=True)
        self.assertIs(reconcile(base, no_change), base)

    def test_source_growth_keeps_old_identity_and_does_not_admit(self):
        base = _snapshot(
            staged_release_sha256s=("9" * 64,),
            retained_mastery_debt=("cap.carried",),
            retained_debt_source_sha256="e" * 64)
        old = base.coverage_rows[0]
        new_row = replace(old, semantic_id="urn:three")
        proposed = _rehash(
            base, semantic_release="3" * 64, atlas_bundle_id="4" * 64,
            source_bundle_id="5" * 64, source_coverage_sha256="6" * 64,
            frozen_census_sha256="7" * 64,
            source_eligible_concept_ids=tuple(sorted(
                (*base.source_eligible_concept_ids, "urn:three"))),
            coverage_rows=tuple(sorted((*base.coverage_rows, new_row),
                                       key=lambda row: (row.semantic_id, row.family_id))),
            rights_epoch=base.rights_epoch + 1)
        event = _event(
            SourceReleaseEvent, base, source_provenance_sha256="6" * 64,
            successor_source=proposed, accepted=True)
        result = reconcile(base, event)
        self.assertTrue(set(base.source_eligible_concept_ids)
                        <= set(result.source_eligible_concept_ids))
        self.assertEqual(result.admitted_factory_release_sha256, None)
        self.assertEqual(result.staged_factory_release_sha256s, ("9" * 64,))
        self.assertEqual(result.retained_mastery_debt, ("cap.carried",))
        self.assertEqual(result.semantic_release, "3" * 64)

    def test_source_shrink_or_unbound_provenance_fails_closed(self):
        base = _snapshot()
        proposed = _rehash(
            base, source_eligible_concept_ids=(base.source_eligible_concept_ids[0],),
            source_coverage_sha256="6" * 64)
        event = _event(
            SourceReleaseEvent, base, source_provenance_sha256="6" * 64,
            successor_source=proposed, accepted=True)
        with self.assertRaises(BilqisError):
            reconcile(base, event)

    def test_source_release_cannot_confer_implementation_or_learning_readiness(self):
        base = _snapshot()
        old = base.coverage_rows[0]
        mutated = replace(
            old,
            implementation_status="ADMITTED",
            reason="SOURCE_RELEASE_CANNOT_BIND_IMPLEMENTATION",
        )
        proposed = _rehash(
            base,
            source_coverage_sha256="6" * 64,
            coverage_rows=tuple(sorted(
                (mutated, *base.coverage_rows[1:]),
                key=lambda row: (row.semantic_id, row.family_id),
            )),
        )
        event = _event(
            SourceReleaseEvent,
            base,
            source_provenance_sha256="6" * 64,
            successor_source=proposed,
            accepted=True,
        )
        with self.assertRaises(BilqisError) as caught:
            reconcile(base, event)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PLANNER_SOURCE_EVENT_IMPLEMENTATION_AUTHORITY_VIOLATION",
        )

    def test_source_release_rejects_duplicate_coverage_identity_before_collapse(self):
        base = _snapshot()
        old = base.coverage_rows[0]
        escalated = replace(
            old,
            implementation_status="ADMITTED",
            reason="SOURCE_RELEASE_CANNOT_BIND_IMPLEMENTATION",
        )
        proposed = _rehash(
            base,
            source_coverage_sha256="6" * 64,
            coverage_rows=tuple(sorted(
                (escalated, *base.coverage_rows),
                key=lambda row: (
                    row.semantic_id,
                    row.family_id,
                    row.implementation_status,
                    row.reason,
                ),
            )),
        )
        event = _event(
            SourceReleaseEvent,
            base,
            source_provenance_sha256="6" * 64,
            successor_source=proposed,
            accepted=True,
        )
        with self.assertRaises(BilqisError) as caught:
            reconcile(base, event)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PLANNER_SOURCE_EVENT_DUPLICATE_COVERAGE_IDENTITY",
        )

        introduced = replace(
            old,
            semantic_id="urn:new",
            implementation_status="ADMITTED",
            reason="SOURCE_RELEASE_CANNOT_BIND_IMPLEMENTATION",
        )
        proposed = _rehash(
            base,
            source_coverage_sha256="7" * 64,
            source_eligible_concept_ids=tuple(sorted(
                (*base.source_eligible_concept_ids, "urn:new"),
            )),
            coverage_rows=tuple(sorted(
                (*base.coverage_rows, introduced),
                key=lambda row: (row.semantic_id, row.family_id),
            )),
        )
        event = _event(
            SourceReleaseEvent,
            base,
            source_provenance_sha256="7" * 64,
            successor_source=proposed,
            accepted=True,
        )
        with self.assertRaises(BilqisError) as caught:
            reconcile(base, event)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PLANNER_SOURCE_EVENT_IMPLEMENTATION_AUTHORITY_VIOLATION",
        )

    def test_correction_removes_only_named_dependent_state(self):
        keep, remove = _evidence(step=1), _evidence(step=2)
        base = _snapshot(
            ready_candidate_ids=("candidate.ready",), retained_evidence=(keep, remove,),
            qualification_epoch=2)
        event = _event(
            CorrectionEvent, base, correction_generation=base.correction_generation + 1,
            invalidated_ready_candidate_ids=("candidate.ready",),
            invalidated_exposed_capability_ids=(),
            invalidated_qualified_capability_ids=(),
            invalidated_evidence=(remove,), accepted=True)
        result = reconcile(base, event)
        self.assertEqual(result.ready_candidate_ids, ())
        self.assertEqual(result.retained_evidence, (keep,))
        self.assertEqual(result.coverage_rows, base.coverage_rows)
        self.assertEqual(result.qualification_epoch, 2)

    def test_admission_requires_an_existing_staged_release(self):
        base = _snapshot(staged_release_sha256s=("9" * 64,))
        event = _event(
            FactoryAdmissionEvent, base, factory_release_sha256="9" * 64,
            admission_receipt_sha256="8" * 64, accepted=True)
        result = reconcile(base, event)
        self.assertEqual(result.admitted_factory_release_sha256, "9" * 64)
        self.assertEqual(result.admission_receipt_sha256, "8" * 64)
        wrong = _event(
            FactoryAdmissionEvent, base, factory_release_sha256="7" * 64,
            admission_receipt_sha256="8" * 64, accepted=True)
        with self.assertRaises(BilqisError):
            reconcile(base, wrong)

    def test_different_event_at_same_generation_is_not_mistaken_for_replay(self):
        base = _snapshot()
        first = _event(
            PlannerPolicyEvent, base, policy_epoch=base.policy_epoch + 1,
            teacher_epoch=base.teacher_epoch, budget=base.budget, accepted=True)
        current = reconcile(base, first)
        other = _event(
            PlannerPolicyEvent, base, policy_epoch=base.policy_epoch + 2,
            teacher_epoch=base.teacher_epoch, budget=base.budget, accepted=True)
        with self.assertRaises(BilqisError):
            reconcile(current, other)

    def test_policy_change_is_versioned_and_no_change_is_fixed_point(self):
        base = _snapshot()
        changed = _event(
            PlannerPolicyEvent, base, policy_epoch=base.policy_epoch + 1,
            teacher_epoch=base.teacher_epoch + 1,
            budget=PlannerBudget(11, 100, 1000), accepted=True)
        result = reconcile(base, changed)
        self.assertEqual(result.policy_epoch, base.policy_epoch + 1)
        self.assertEqual(result.teacher_epoch, base.teacher_epoch + 1)
        self.assertEqual(result.budget.max_candidates, 11)
        same = _event(
            PlannerPolicyEvent, base, policy_epoch=base.policy_epoch,
            teacher_epoch=base.teacher_epoch, budget=base.budget, accepted=True)
        self.assertIs(reconcile(base, same), base)

    def test_unqualified_or_wrong_predecessor_event_never_advances(self):
        base = _snapshot()
        rejected = _event(
            PlannerPolicyEvent, base, policy_epoch=base.policy_epoch + 1,
            teacher_epoch=base.teacher_epoch, budget=base.budget, accepted=False)
        with self.assertRaises(BilqisError):
            reconcile(base, rejected)
        wrong = replace(rejected, accepted=True, predecessor_sha256="f" * 64,
                        event_sha256="0" * 64)
        wrong = replace(wrong, event_sha256=wrong.expected_digest())
        with self.assertRaises(BilqisError):
            reconcile(base, wrong)

    def test_non_source_event_must_bind_current_source_provenance(self):
        base = _snapshot()
        event = _event(
            PlannerPolicyEvent, base, source_provenance_sha256="f" * 64,
            policy_epoch=base.policy_epoch + 1, teacher_epoch=base.teacher_epoch,
            budget=base.budget, accepted=True)
        with self.assertRaises(BilqisError):
            reconcile(base, event)


if __name__ == "__main__":
    unittest.main()
