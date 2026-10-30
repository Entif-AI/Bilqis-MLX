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

class ContextEligibilityTests1(ContextEligibilityTests):
    def test_c09_boundary_rejects_malformed_event(self):
        frames, task, frontier, policy = _case(count=1)
        prior = project_context(frames, task, frontier, policy)
        revoked = replace(frontier, grants=(
            replace(frontier.grants[0], revoked=True), *frontier.grants[1:]))
        transition = transition_context(prior, frames, task, revoked, policy)
        event = transition.invalidations[0]
        bad_fields = (
            ("old_context_digest", "bad"),
            ("new_context_digest", "bad"),
            ("new_context_digest", event.old_context_digest),
            ("reason_codes", ()),
            ("reason_codes", ("same", "same")),
            ("principal_id", ""),
            ("tenant_id", ""),
            ("scope", ""),
            ("semantic_release", "bad"),
            ("policy_epoch", -1),
            ("rights_epoch", -1),
            ("correction_generation", -1),
            ("causal_prefix_end", -1),
            ("invalidated_handles", ()),
            ("invalidated_handles", ("same", "same")),
            ("schema_version", "wrong"),
        )
        for field, value in bad_fields:
            with self.subTest(field=field, value=value):
                with self.assertRaises(BilqisError) as caught:
                    replace(event, **{field: value})
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_CONTEXT_C09_INVALIDATION_INVALID")
        invalid_transitions = (
            {"current": "not-a-projection"},
            {"invalidations": ("not-an-event",)},
            {"invalidations": (event, event)},
            {"invalidations": (replace(
                event, new_context_digest="b" * 64),)},
            {"schema_version": "wrong"},
        )
        for changed in invalid_transitions:
            with self.subTest(transition=changed):
                with self.assertRaises(BilqisError) as caught:
                    replace(transition, **changed)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_CONTEXT_TRANSITION_INVALID")

    def test_c09_transition_is_pure_and_unchanged_or_reordered_views_do_not_invalidate(self):
        frames, task, frontier, policy = _case(count=2, two_roles=True)
        prior = project_context(frames, task, frontier, policy)
        initial = transition_context(None, frames, task, frontier, policy)
        self.assertIsInstance(initial, ContextTransition)
        self.assertEqual(initial.invalidations, ())
        self.assertEqual(initial.current.digest, prior.digest)
        same = transition_context(prior, frames, task, frontier, policy)
        reordered = transition_context(
            prior, tuple(reversed(frames)), task, frontier, policy)
        self.assertEqual(same.invalidations, ())
        self.assertEqual(reordered.invalidations, ())
        self.assertEqual(reordered.current.digest, prior.digest)

    def test_c09_revocation_and_policy_time_changes_emit_exact_local_receipts(self):
        frames, task, frontier, policy = _case(count=1)
        prior = project_context(frames, task, frontier, policy)
        revoked_grant = replace(frontier.grants[0], revoked=True)
        revoked = replace(
            frontier, grants=(revoked_grant, *frontier.grants[1:]))
        lost = transition_context(prior, frames, task, revoked, policy)
        self.assertIsInstance(lost.current, ContextHold)
        self.assertEqual(len(lost.invalidations), 1)
        event = lost.invalidations[0]
        self.assertIsInstance(event, C09ContextInvalidation)
        self.assertEqual(event.schema_version, "bilqis.c09-context-invalidation/v1")
        self.assertEqual(event.old_context_digest, prior.digest)
        self.assertIsNone(event.new_context_digest)
        self.assertEqual(
            event.invalidated_handles,
            ("frame:0", "source:member:0:subject"))
        self.assertEqual(len(event.event_id), 64)
        self.assertEqual(
            event.event_id,
            transition_context(prior, frames, task, revoked, policy)
            .invalidations[0].event_id)
        later = transition_context(
            prior, frames, replace(task, effective_time=6), frontier, policy)
        self.assertIsInstance(later.current, ApprovedContextProjection)
        self.assertNotEqual(later.current.digest, prior.digest)
        self.assertEqual(
            later.invalidations[0].reason_codes,
            ("BAMF_CONTEXT_APPROVED_VIEW_CHANGED",))
        changed_policy = transition_context(
            prior, frames, task, frontier,
            replace(policy, policy_epoch=2))
        self.assertIsInstance(changed_policy.current, ContextHold)
        self.assertEqual(len(changed_policy.invalidations), 1)

    def test_c09_public_fixture_actor_and_scope_isolation(self):
        frames, task, frontier, policy = _case(count=1)
        prior = project_context(frames, task, frontier, policy)
        actor = "synthetic:independent-actor"
        other_task = replace(task, principal_id=actor)
        other_frames = tuple(
            replace(envelope, principal_id=actor) for envelope in frames)
        other_frontier = replace(
            frontier, grants=tuple(
                replace(grant, principal_id=actor)
                for grant in frontier.grants))
        other_view = project_context(
            other_frames, other_task, other_frontier, policy)
        self.assertIsInstance(other_view, ApprovedContextProjection)
        self.assertNotEqual(other_view.digest, prior.digest)
        with self.assertRaises(BilqisError) as caught:
            transition_context(
                prior, other_frames, other_task, other_frontier, policy)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_CONTEXT_TRANSITION_ACTOR_SCOPE_DRIFT")
        with self.assertRaises(BilqisError):
            transition_context(
                prior, frames, replace(task, scope="synthetic:other-scope"),
                frontier, policy)
        for changed in (
            replace(task, purpose="synthetic:other-purpose"),
            replace(task, jurisdiction="synthetic:other-region"),
            replace(task, semantic_release="b" * 64),
        ):
            with self.subTest(partition=changed):
                with self.assertRaises(BilqisError) as caught:
                    transition_context(
                        prior, frames, changed, frontier, policy)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_CONTEXT_TRANSITION_ACTOR_SCOPE_DRIFT")

    def test_approved_projection_is_the_only_readout_and_cache_identity(self):
        frames, task, frontier, policy = _case(count=2, two_roles=True)
        projected = project_context(frames, task, frontier, policy)
        self.assertIsInstance(projected, ApprovedContextProjection)
        self.assertEqual(
            projected.digest,
            check_context_eligibility(frames, task, frontier, policy).digest)
        self.assertEqual(
            projected.attention_handles,
            (("frame:0", "source:member:0:subject"),
             ("frame:0", "source:member:0:object"),
             ("frame:1", "source:member:1:subject")),
        )
        self.assertEqual(projected.frame("frame:0"), frames[0].frame)
        self.assertEqual(
            projected.member("source:member:0:object"),
            frames[0].frame.bindings[1])
        self.assertNotEqual(projected.cache_key("node:A"),
                            projected.cache_key("node:B"))
        later = project_context(
            frames, replace(task, effective_time=6), frontier, policy)
        self.assertNotEqual(projected.cache_key("node:A"),
                            later.cache_key("node:A"))
        with self.assertRaises(BilqisError):
            projected.member("source:member:future")
        with self.assertRaises(BilqisError):
            projected.frame("frame:future")
        denied = project_context(
            frames, task, frontier,
            replace(policy, allowed_join_pairs=()))
        self.assertIsInstance(denied, ContextHold)
        self.assertFalse(hasattr(denied, "attention_handles"))
