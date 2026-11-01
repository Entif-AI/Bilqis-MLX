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
    def test_role_priority_then_attested_salience_then_source_order(self):
        case = _case()
        approved = project_context(
            case.frames, case.task, case.frontier, case.policy)
        by_handle = {item.frame_handle: item for item in approved.eligible.frames}
        signals = (
            SourceSalience("frame:0", "source:salience:0",
                           by_handle["frame:0"].envelope_digest, 1, 100.0),
            SourceSalience("frame:8", "source:salience:8",
                           by_handle["frame:8"].envelope_digest, 9, 5.0),
        )
        result = case.select(
            frontier=_grant_salience(case.frontier, *signals),
            source_salience=signals)
        self.assertEqual(tuple(x.frame_handle for x in result.selected),
                         ("frame:8", "frame:4"))
        self.assertEqual([x.role_matches for x in result.selected], [1, 1])
        plain = case.select(requested_roles=("other",))
        self.assertEqual(tuple(x.frame_handle for x in plain.selected),
                         ("frame:0", "frame:1"))

    def test_revoked_source_and_forged_salience_reject(self):
        case = _case(count=1, target_indices=(0,))
        revoked = replace(case.frontier, grants=tuple(
            replace(grant, revoked=True)
            if grant.source_handle == "source:frame:0" else grant
            for grant in case.frontier.grants))
        held = case.select(frontier=revoked)
        self.assertIsInstance(held, ContextHold)
        self.assertIn("BAMF_CONTEXT_SOURCE_REVOKED", held.reason_codes)
        approved = project_context(
            case.frames, case.task, case.frontier, case.policy)
        witness = SourceSalience(
            "frame:0", "source:salience:0",
            approved.eligible.frames[0].envelope_digest, 1, 1.0)
        attested = _grant_salience(case.frontier, witness)
        self.assertEqual(case.select(
            frontier=attested, source_salience=(witness,)
        ).selected[0].salience, 1.0)
        for bad in (replace(witness, envelope_digest="b"*64),
                    replace(witness, visible_at_prefix=2)):
            with self.assertRaises(BilqisError):
                case.select(frontier=attested, source_salience=(bad,))
        with self.assertRaises(BilqisError):
            case.select(source_salience=(witness,))
        revoked_signal = replace(attested, grants=tuple(
            replace(grant, revoked=True)
            if grant.source_handle == witness.source_handle else grant
            for grant in attested.grants))
        with self.assertRaises(BilqisError):
            case.select(frontier=revoked_signal, source_salience=(witness,))

    def test_future_salience_and_padding_do_not_affect_earlier_view(self):
        case = _case()
        early = replace(case.task, causal_prefix_end=8)
        approved = project_context(
            case.frames, case.task, case.frontier, case.policy)
        witness = SourceSalience(
            "frame:8", "source:salience:8",
            next(x.envelope_digest for x in approved.eligible.frames
                 if x.frame_handle == "frame:8"), 9, 1000.0)
        before = case.select(frames=case.frames[:8], task=early)
        after = case.select(
            task=early, frontier=_grant_salience(case.frontier, witness),
            source_salience=(witness,))
        self.assertEqual(before, after)
        self.assertEqual(
            case.select(task=replace(case.task, causal_prefix_end=0)),
            RefinementSelection("generation:1", 0, "query:1", None, 0, 0, (), ()))
