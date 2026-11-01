"""B06.2 complete A05 prefix plus A13 source-gated prediction-local policy."""
from __future__ import annotations

from dataclasses import dataclass, replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.refinement_policy import (
    RefinementSelection, SourceSalience, prefix_inventory_evidence_digest,
    prefix_inventory_handle, salience_evidence_digest,
    select_prediction_refinements,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextHold, ContextMember,
    ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
    frame_evidence_digest, member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_compiler import (
    FrameCompilerConfig, SourceAtom, StreamingAST, atom_evidence_digest,
    compile_prefix,
)
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, FrameTree, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)

from bilqis_mlx.runtime.tests.model.refinement.helpers import _case, _grant_salience, SourceCase, SOURCE_ID

class RefinementPolicyTests(unittest.TestCase):
    def test_quota_8_to_9_and_future_frames_do_not_change_earlier_prediction(self):
        case = _case()
        early = replace(case.task, causal_prefix_end=8)
        before = case.select(frames=case.frames[:8], task=early)
        appended = case.select(task=early)
        self.assertEqual(before, appended)
        self.assertEqual((before.eligible_count, before.quota), (8, 1))
        self.assertEqual(tuple(x.frame_handle for x in before.selected), ("frame:4",))
        self.assertEqual(before.selected[0].passes, 1)
        later = case.select()
        self.assertEqual((later.eligible_count, later.quota), (9, 2))
        self.assertEqual(tuple(x.frame_handle for x in later.selected),
                         ("frame:4", "frame:8"))
        self.assertEqual(len(later.remaining_frame_handles), 7)
        self.assertEqual(later.selected[0].cache_identity,
                         ("generation:1", 9, "query:1",
                          case.frames[4].frame.occurrence_id))

    def test_missing_eligible_visible_frame_cannot_shrink_quota(self):
        case = _case()
        with self.assertRaises(BilqisError):
            case.select(frames=case.frames[:8])
        with self.assertRaises(BilqisError):
            case.select(frames=())
        with self.assertRaises(BilqisError):
            case.select(
                frames=case.frames[:8],
                source_ast=replace(case.ast, frames=case.ast.frames[:8]))
        with self.assertRaises(BilqisError):
            case.select(
                frames=case.frames[:8],
                source_ast=replace(case.ast, frames=case.ast.frames[:8]),
                compiler_config=replace(case.config, approved=project_context(
                    case.frames[:8], case.task, case.frontier, case.policy)))
        self.assertEqual(case.select().quota, 2)

    def test_revoked_complete_prefix_inventory_fails_closed(self):
        case = _case()
        handle = prefix_inventory_handle(SOURCE_ID, case.task.causal_prefix_end)
        revoked = replace(case.frontier, grants=tuple(
            replace(grant, revoked=True)
            if grant.source_handle == handle else grant
            for grant in case.frontier.grants))
        with self.assertRaises(BilqisError):
            case.select(frontier=revoked)

    def test_seed_samples_all_passes_independent_of_future_context(self):
        case = _case()
        early = replace(case.task, causal_prefix_end=8)
        seen = set()
        for index in range(48):
            args = dict(training=True, visit_id=f"visit:{index}", task=early)
            a = case.select(frames=case.frames[:8], **args)
            b = case.select(**args)
            self.assertEqual(a, b)
            seen.add(a.selected[0].passes)
        self.assertEqual(seen, {0, 1, 2})
        self.assertEqual(case.select(
            task=early, explicit_member_question=False).selected[0].passes, 0)
        self.assertEqual(case.select(
            task=early, unresolved_nested_query=True).selected[0].passes, 2)

    def test_invalid_inputs_reject(self):
        case = _case(count=1, target_indices=(0,))
        for changes in (
            {"training": 1},
            {"requested_roles": ("target", "target")},
            {"explicit_member_question": True, "requested_roles": ()},
            {"input_generation": ""},
            {"source_salience": (SourceSalience(
                "unknown", "source:salience:unknown", "a"*64, 0, 1.0),)},
            {"compiler_config": replace(case.config, policy=replace(
                case.policy, policy_epoch=2))},
        ):
            with self.subTest(changes=changes), self.assertRaises(BilqisError):
                case.select(**changes)
