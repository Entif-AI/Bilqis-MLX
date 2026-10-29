"""B06.2 prediction-local selection against the actual A13 source gate."""
from __future__ import annotations

from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.refinement_policy import (
    RefinementSelection, SourceSalience, salience_evidence_digest,
    select_prediction_refinements,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextHold, ContextMember,
    ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
    frame_evidence_digest, member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.frame_schema import (
    ChildFrameRef, ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)


RELEASE = "a" * 64
PRINCIPAL = "synthetic:student"
TENANT = "synthetic:tenant"
REGION = "synthetic:region"
SCOPE = "synthetic:public"


def _case(count=9, *, target_indices=(4, 8)):
    frames = []
    grants = []
    for index in range(count):
        role = "target" if index in target_indices else "other"
        schema = FrameSchema(
            "synthetic:" + role, 1, "source:synthetic",
            (RoleSpec(role, ("Entity",), 1, 1),), "ORDERED", "synthetic")
        frame = make_frame_instance(
            schema, source_instance_id=f"source:{index}", structural_path=(),
            source_span=SourceSpan(index, index + 1),
            parent_occurrence_id=None,
            bindings=(RoleOccurrence(role, 0, concept=ConceptRef(
                f"formal:entity.{index}", RELEASE, index, ("Entity",),
                f"source:concept:{index}")),),
            causal_prefix_end=index + 1,
        )
        member = ContextMember(role, 0, f"source:member:{index}", index + 1)
        frame_handle = f"frame:{index}"
        source_handle = f"source:frame:{index}"
        evidence = {
            source_handle: frame_evidence_digest(frame),
            member.source_handle: member_evidence_digest(frame, member),
        }
        for handle, digest in evidence.items():
            grants.append(SourceGrant(
                handle, PRINCIPAL, TENANT, PUBLIC_FORMAL, RELEASE, digest,
                ("TRAINING",), (REGION,), (SCOPE,),
                rights_epoch=1, correction_generation=1,
                observed_at=0, effective_from=0,
            ))
        frames.append(ContextEligibility(
            frame_handle, frame, source_handle, (member,),
            PRINCIPAL, TENANT, "TRAINING", PUBLIC_FORMAL, RELEASE,
            REGION, SCOPE, PUBLIC_FORMAL, 1, 1, 1, 0, 0, None,
            index + 1,
        ))
    frontier = SourceFrontier(
        1, 1, tuple(sorted(grants, key=lambda item: item.source_handle)))
    policy = ContextPolicy(
        "synthetic:policy", 1, 1,
        ("TRAINING",), (PUBLIC_FORMAL,), (REGION,), (SCOPE,),
        (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        tuple((PUBLIC_FORMAL,) * n for n in range(3, count + 1)),
    )
    task = TaskScope(
        PRINCIPAL, TENANT, "TRAINING", RELEASE, REGION, SCOPE,
        observed_frontier=1, effective_time=1, causal_prefix_end=count,
    )
    return tuple(frames), task, frontier, policy


def _select(frames, task, frontier, policy, **changes):
    arguments = dict(
        frames=frames, task_scope=task, source_frontier=frontier,
        policy=policy, input_generation="generation:1", query_id="query:1",
        requested_roles=("target",), run_seed="run:1", visit_id="visit:1",
        training=False, explicit_member_question=True,
        unresolved_nested_query=False,
    )
    arguments.update(changes)
    return select_prediction_refinements(**arguments)


def _grant_salience(frontier, *witnesses):
    extra = tuple(SourceGrant(
        witness.source_handle, PRINCIPAL, TENANT, PUBLIC_FORMAL, RELEASE,
        salience_evidence_digest(witness),
        ("TRAINING",), (REGION,), (SCOPE,),
        rights_epoch=1, correction_generation=1,
        observed_at=0, effective_from=0,
    ) for witness in witnesses)
    return replace(frontier, grants=tuple(sorted(
        (*frontier.grants, *extra), key=lambda item: item.source_handle)))


class RefinementPolicyTests(unittest.TestCase):
    def test_quota_8_to_9_and_future_frame_do_not_change_earlier_prediction(self):
        frames, task, frontier, policy = _case()
        early = replace(task, causal_prefix_end=8)
        before = _select(frames[:8], early, frontier, policy)
        appended = _select(frames, early, frontier, policy)
        self.assertIsInstance(before, RefinementSelection)
        self.assertEqual(before, appended)
        self.assertEqual((before.eligible_count, before.quota), (8, 1))
        self.assertEqual(tuple(x.frame_handle for x in before.selected), ("frame:4",))
        self.assertEqual(before.selected[0].passes, 1)
        later = _select(frames, task, frontier, policy)
        self.assertEqual((later.eligible_count, later.quota), (9, 2))
        self.assertEqual(tuple(x.frame_handle for x in later.selected),
                         ("frame:4", "frame:8"))
        self.assertEqual(len(later.remaining_frame_handles), 7)
        self.assertEqual(later.selected[0].cache_identity,
                         ("generation:1", 9, "query:1",
                          frames[4].frame.occurrence_id))

    def test_role_priority_then_source_visible_salience_then_source_order(self):
        frames, task, frontier, policy = _case()
        approved = project_context(frames, task, frontier, policy)
        by_handle = {item.frame_handle: item for item in approved.eligible.frames}
        signals = (
            SourceSalience("frame:0", "source:salience:0",
                           by_handle["frame:0"].envelope_digest, 1, 100.0),
            SourceSalience("frame:8", "source:salience:8",
                           by_handle["frame:8"].envelope_digest, 9, 5.0),
        )
        result = _select(frames, task, _grant_salience(frontier, *signals),
                         policy, source_salience=signals)
        self.assertEqual(tuple(x.frame_handle for x in result.selected),
                         ("frame:8", "frame:4"))
        # A nonmatching frame with higher salience cannot beat a role match.
        self.assertEqual(result.selected[0].role_matches, 1)
        self.assertEqual(result.selected[1].role_matches, 1)
        plain = _select(frames, task, frontier, policy,
                        requested_roles=("other",))
        self.assertEqual(tuple(x.frame_handle for x in plain.selected),
                         ("frame:0", "frame:1"))

    def test_training_seed_samples_all_passes_and_ignores_future_context(self):
        frames, task, frontier, policy = _case()
        early = replace(task, causal_prefix_end=8)
        seen = set()
        for index in range(48):
            args = dict(training=True, visit_id=f"visit:{index}")
            a = _select(frames[:8], early, frontier, policy, **args)
            b = _select(frames, early, frontier, policy, **args)
            self.assertEqual(a, b)
            seen.add(a.selected[0].passes)
        self.assertEqual(seen, {0, 1, 2})
        self.assertEqual(
            _select(frames, early, frontier, policy,
                    training=False, explicit_member_question=False).selected[0].passes,
            0)

    def test_unresolved_nested_query_permits_two_passes_without_reusing_backbone(self):
        frames, task, frontier, policy = _case(count=1, target_indices=(0,))
        self.assertEqual(
            _select(frames, task, frontier, policy,
                    unresolved_nested_query=True).selected[0].passes, 2)
        schema = FrameSchema(
            "synthetic:nested", 1, "source:synthetic",
            (RoleSpec("target", ("Frame",), 1, 1),),
            "ORDERED", "synthetic",
        )
        nested = make_frame_instance(
            schema, source_instance_id="source:nested", structural_path=(),
            source_span=SourceSpan(0, 1), parent_occurrence_id=None,
            bindings=(RoleOccurrence("target", 0, child_frame=ChildFrameRef(
                "b" * 64, "c" * 64)),), causal_prefix_end=1,
        )
        envelope = replace(frames[0], frame=nested)
        grants = tuple(replace(
            grant,
            evidence_digest=(
                frame_evidence_digest(nested)
                if grant.source_handle == envelope.source_handle
                else member_evidence_digest(nested, envelope.members[0])
            )) for grant in frontier.grants)
        updated_frontier = replace(frontier, grants=grants)
        one = _select((envelope,), task, updated_frontier, policy)
        two = _select((envelope,), task, updated_frontier, policy,
                      unresolved_nested_query=True)
        self.assertEqual(one.selected[0].passes, 1)
        self.assertEqual(two.selected[0].passes, 2)
        self.assertEqual(one.selected[0].cache_identity,
                         two.selected[0].cache_identity)

    def test_revoked_or_forged_source_evidence_never_enters_selection(self):
        frames, task, frontier, policy = _case(count=1, target_indices=(0,))
        revoked = replace(frontier, grants=tuple(
            replace(grant, revoked=True) if grant.source_handle == "source:frame:0"
            else grant for grant in frontier.grants))
        held = _select(frames, task, revoked, policy)
        self.assertIsInstance(held, ContextHold)
        self.assertIn("BAMF_CONTEXT_SOURCE_REVOKED", held.reason_codes)
        approved = project_context(frames, task, frontier, policy)
        witness = SourceSalience(
            "frame:0", "source:salience:0",
            approved.eligible.frames[0].envelope_digest, 1, 1.0)
        attested = _grant_salience(frontier, witness)
        self.assertEqual(
            _select(frames, task, attested, policy,
                    source_salience=(witness,)).selected[0].salience, 1.0)
        with self.assertRaises(BilqisError):
            _select(frames, task, attested, policy, source_salience=(
                replace(witness, envelope_digest="b" * 64),))
        with self.assertRaises(BilqisError):
            _select(frames, task, attested, policy, source_salience=(
                replace(witness, visible_at_prefix=2),))
        with self.assertRaises(BilqisError):
            _select(frames, task, frontier, policy, source_salience=(witness,))
        revoked_signal = replace(attested, grants=tuple(
            replace(grant, revoked=True)
            if grant.source_handle == witness.source_handle else grant
            for grant in attested.grants))
        with self.assertRaises(BilqisError):
            _select(frames, task, revoked_signal, policy,
                    source_salience=(witness,))

    def test_future_salience_and_padding_do_not_affect_earlier_view(self):
        frames, task, frontier, policy = _case()
        early = replace(task, causal_prefix_end=8)
        full = project_context(frames, task, frontier, policy)
        witness = SourceSalience(
            "frame:8", "source:salience:8",
            next(x.envelope_digest for x in full.eligible.frames
                 if x.frame_handle == "frame:8"), 9, 1000.0)
        before = _select(frames[:8], early, frontier, policy)
        after = _select(frames, early, _grant_salience(frontier, witness), policy,
                        source_salience=(witness,))
        self.assertEqual(before, after)
        self.assertEqual(
            _select(frames, replace(task, causal_prefix_end=0), frontier, policy),
            RefinementSelection("generation:1", 0, "query:1", None, 0, 0, (), ()))

    def test_invalid_inputs_reject_without_creating_a_source_credential(self):
        frames, task, frontier, policy = _case(count=1, target_indices=(0,))
        for changes in (
            {"training": 1},
            {"requested_roles": ("target", "target")},
            {"explicit_member_question": True, "requested_roles": ()},
            {"input_generation": ""},
            {"source_salience": (
                SourceSalience("unknown", "source:salience:unknown",
                               "a" * 64, 0, 1.0),)},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(BilqisError):
                    _select(frames, task, frontier, policy, **changes)


if __name__ == "__main__":
    unittest.main()
