"""Behavior tests split from their shared fixture owner."""
from __future__ import annotations
from dataclasses import replace
import unittest
from unittest.mock import patch
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.context_eligibility import PUBLIC_FORMAL, ApprovedContextProjection, C09ContextInvalidation, ContextEligibility, ContextHold, ContextMember, ContextTransition, ContextPolicy, EligibleContext, SourceFrontier, SourceGrant, TaskScope, check_context_eligibility, frame_evidence_digest, member_evidence_digest, project_context, transition_context
from bilqis_mlx.semantics.frame_adapters import public_formal_context
from bilqis_mlx.semantics.frame_schema import ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan, make_frame_instance
from bilqis_mlx.semantics.tests.test_context_eligibility import RELEASE, PRINCIPAL, TENANT, REGION, SCOPE, _frame, _case, ContextEligibilityTests

class ContextEligibilityTests3(ContextEligibilityTests):
    def test_revocation_and_missing_member_grant_hold_before_readout(self):
        frames, task, frontier, policy = _case(count=1)
        self.assertIsInstance(
            check_context_eligibility(frames, task, frontier, policy),
            EligibleContext,
        )
        revoked = replace(
            frontier.grants[0], revoked=True)
        revoked_frontier = replace(
            frontier, grants=(revoked, *frontier.grants[1:]))
        held = check_context_eligibility(
            frames, task, revoked_frontier, policy)
        self.assertIsInstance(held, ContextHold)
        self.assertIn("BAMF_CONTEXT_SOURCE_REVOKED", held.reason_codes)
        self.assertFalse(hasattr(held, "frames"))

        missing_member = replace(frontier, grants=frontier.grants[:1])
        held = check_context_eligibility(frames, task, missing_member, policy)
        self.assertIn("BAMF_CONTEXT_SOURCE_UNKNOWN", held.reason_codes)
        self.assertIn("source:member:0:subject", held.source_handles)

    def test_time_and_policy_changes_produce_distinct_cache_identities(self):
        frames, task, frontier, policy = _case(count=1)
        original = check_context_eligibility(frames, task, frontier, policy)
        self.assertIsInstance(original, EligibleContext)
        later = check_context_eligibility(
            frames, replace(task, effective_time=6), frontier, policy)
        self.assertIsInstance(later, EligibleContext)
        self.assertNotEqual(original.digest, later.digest)
        newer_policy = replace(policy, policy_epoch=2)
        newer_frames = (replace(frames[0], policy_epoch=2),)
        updated = check_context_eligibility(
            newer_frames, task, frontier, newer_policy)
        self.assertIsInstance(updated, EligibleContext)
        self.assertNotEqual(original.digest, updated.digest)

    def test_invisible_constituent_and_future_source_are_never_eligible(self):
        frames, task, frontier, policy = _case(count=1)
        future_member = replace(
            frames[0].members[0], visible_at_prefix=9)
        held = check_context_eligibility(
            (replace(frames[0], members=(future_member,)),),
            task, frontier, policy)
        self.assertIn("BAMF_CONTEXT_INVISIBLE_PREFIX", held.reason_codes)
        future_grant = replace(frontier.grants[-1], observed_at=4)
        held = check_context_eligibility(
            frames, task,
            replace(frontier, grants=(*frontier.grants[:-1], future_grant)),
            policy)
        self.assertIn("BAMF_CONTEXT_TEMPORAL_MISMATCH", held.reason_codes)

    def test_release_purpose_and_rights_are_independent_denial_reasons(self):
        frames, task, frontier, policy = _case(count=1)
        held = check_context_eligibility(
            (replace(frames[0], semantic_release="b" * 64),),
            task, frontier, policy)
        self.assertIn("BAMF_CONTEXT_RELEASE_MISMATCH", held.reason_codes)
        held = check_context_eligibility(
            frames, replace(task, purpose=None), frontier, policy)
        self.assertIn("BAMF_CONTEXT_PURPOSE_UNRESOLVED", held.reason_codes)
        held = check_context_eligibility(
            frames, task, replace(frontier, rights_epoch=2), policy)
        self.assertIn("BAMF_CONTEXT_RIGHTS_EPOCH_MISMATCH", held.reason_codes)
        held = check_context_eligibility(
            frames, task, replace(frontier, correction_generation=2), policy)
        self.assertIn("BAMF_CONTEXT_CORRECTION_STALE", held.reason_codes)

    def test_all_pairs_do_not_override_a_forbidden_three_frame_set(self):
        frames, task, frontier, policy = _case(count=3)
        held = check_context_eligibility(
            frames, task, frontier,
            replace(policy, allowed_join_sets=()))
        self.assertIsInstance(held, ContextHold)
        self.assertIn("BAMF_CONTEXT_FORBIDDEN_JOIN", held.reason_codes)
        self.assertEqual(len(held.source_handles), 3)

    def test_member_binding_and_scope_are_validated_before_context_admission(self):
        frames, task, frontier, policy = _case(count=1)
        held = check_context_eligibility(
            (replace(frames[0], members=()),), task, frontier, policy)
        self.assertIn("BAMF_CONTEXT_MEMBER_MISMATCH", held.reason_codes)
        held = check_context_eligibility(
            frames, replace(task, scope="synthetic:other"), frontier, policy)
        self.assertIn("BAMF_CONTEXT_SCOPE_FORBIDDEN", held.reason_codes)
        self.assertLessEqual(len(held.diagnostics), 16)

    def test_malformed_input_records_raise_registered_boundary_error(self):
        frames, task, frontier, policy = _case(count=1)
        with self.assertRaises(BilqisError) as caught:
            check_context_eligibility([frames[0]], task, frontier, policy)
        self.assertEqual(caught.exception.code, "SEMANTIC_FRAME.BINDING.INVALID")
        with self.assertRaises(BilqisError):
            replace(frames[0], policy_epoch=-1)

    def test_source_availability_does_not_grant_training_purpose(self):
        frames, task, frontier, policy = _case(count=1)
        restricted = replace(
            frontier.grants[0], permitted_purposes=("ASSESSMENT",))
        changed = replace(
            frontier, grants=(restricted, *frontier.grants[1:]))
        held = check_context_eligibility(frames, task, changed, policy)
        self.assertIsInstance(held, ContextHold)
        self.assertIn("BAMF_CONTEXT_PURPOSE_FORBIDDEN", held.reason_codes)

    def test_unrelated_source_grant_does_not_invalidate_approved_context(self):
        frames, task, frontier, policy = _case(count=1)
        original = check_context_eligibility(frames, task, frontier, policy)
        unrelated = replace(
            frontier.grants[0], source_handle="source:unrelated")
        changed = replace(
            frontier,
            grants=tuple(sorted(
                (*frontier.grants, unrelated),
                key=lambda grant: grant.source_handle)),
        )
        updated = check_context_eligibility(frames, task, changed, policy)
        self.assertIsInstance(updated, EligibleContext)
        self.assertEqual(original.digest, updated.digest)

    def test_revoked_evidence_cannot_be_relabelled_with_another_live_handle(self):
        frames, task, frontier, policy = _case(count=2)
        revoked_handles = {
            frames[0].source_handle,
            *(member.source_handle for member in frames[0].members),
        }
        revoked_frontier = replace(
            frontier,
            grants=tuple(
                replace(grant, revoked=True)
                if grant.source_handle in revoked_handles else grant
                for grant in frontier.grants
            ),
        )
        self.assertIn(
            "BAMF_CONTEXT_SOURCE_REVOKED",
            check_context_eligibility(
                (frames[0],), task, revoked_frontier, policy).reason_codes,
        )
        relabelled = replace(
            frames[0],
            source_handle=frames[1].source_handle,
            members=tuple(
                replace(member, source_handle=frames[1].members[index].source_handle)
                for index, member in enumerate(frames[0].members)
            ),
        )
        held = check_context_eligibility(
            (relabelled,), task, revoked_frontier, policy)
        self.assertIsInstance(held, ContextHold)
        self.assertIn("BAMF_CONTEXT_EVIDENCE_MISMATCH", held.reason_codes)

    def test_source_locus_tampering_is_detected_even_when_content_id_is_same(self):
        frames, task, frontier, policy = _case(count=1)
        binding = frames[0].frame.bindings[0]
        forged = replace(
            binding, concept=replace(
                binding.concept, source_reference="synthetic:forged-locus"))
        altered_frame = replace(frames[0].frame, bindings=(forged,))
        self.assertEqual(
            altered_frame.content_digest, frames[0].frame.content_digest)
        held = check_context_eligibility(
            (replace(frames[0], frame=altered_frame),),
            task, frontier, policy)
        self.assertIn("BAMF_CONTEXT_EVIDENCE_MISMATCH", held.reason_codes)

    def test_visibility_cannot_be_backdated_under_an_existing_source_grant(self):
        frames, task, frontier, policy = _case(count=1)
        future = replace(frames[0].members[0], visible_at_prefix=9)
        future_grant = replace(
            frontier.grants[-1],
            evidence_digest=member_evidence_digest(frames[0].frame, future))
        source_frontier = replace(
            frontier, grants=(*frontier.grants[:-1], future_grant))
        held = check_context_eligibility(
            (replace(frames[0], members=(future,)),),
            task, source_frontier, policy)
        self.assertIn("BAMF_CONTEXT_INVISIBLE_PREFIX", held.reason_codes)
        held = check_context_eligibility(
            frames, task, source_frontier, policy)
        self.assertIn("BAMF_CONTEXT_EVIDENCE_MISMATCH", held.reason_codes)
