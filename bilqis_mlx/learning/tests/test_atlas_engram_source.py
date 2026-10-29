"""B07 source-qualified motif planning against real A03/A13 records."""
from dataclasses import replace
from unittest import TestCase

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram import MotifBudget, MotifManifest
from bilqis_mlx.learning.atlas_engram_source import (
    ApprovedMotifCandidate, _probe_approved_motifs,
)
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry, AtlasConcept, AtlasCounts, FrozenAtlasConcept,
    FrozenAtlasSnapshot, SourceRecordRef,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextHold, ContextMember,
    ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
    frame_evidence_digest, member_evidence_digest,
)
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)

RELEASE = "a" * 64

def approved_source_case(*, forged_type: bool = False):
    concept = ConceptRef(
        "formal:entity.0", RELEASE, 0,
        ("Number",) if forged_type else ("Entity",), "source:fixture:entity.0")
    schema = FrameSchema(
        "source:relation", 1, "source:relation",
        (RoleSpec("actor", ("Entity", "Number"), 1, 1),),
        "ORDERED", "source-expression")
    frame = make_frame_instance(
        schema, source_instance_id="source:frame:0",
        structural_path=(), source_span=SourceSpan(0, 8),
        parent_occurrence_id=None,
        bindings=(RoleOccurrence("actor", 0, concept=concept),),
        causal_prefix_end=8)
    member = ContextMember("actor", 0, "source:member:actor", 8)
    grants = (
        SourceGrant(
            "source:frame", "synthetic:principal", "synthetic:tenant",
            PUBLIC_FORMAL, RELEASE, frame_evidence_digest(frame),
            ("TRAINING",), ("synthetic:region",), ("synthetic:public",),
            1, 1, 2, 0),
        SourceGrant(
            member.source_handle, "synthetic:principal", "synthetic:tenant",
            PUBLIC_FORMAL, RELEASE, member_evidence_digest(frame, member),
            ("TRAINING",), ("synthetic:region",), ("synthetic:public",),
            1, 1, 2, 0),
    )
    envelope = ContextEligibility(
        "frame:0", frame, "source:frame", (member,),
        "synthetic:principal", "synthetic:tenant", "TRAINING",
        PUBLIC_FORMAL, RELEASE, "synthetic:region", "synthetic:public",
        PUBLIC_FORMAL, 1, 1, 1, 2, 0, None, 8)
    task = TaskScope(
        "synthetic:principal", "synthetic:tenant", "TRAINING",
        RELEASE, "synthetic:region", "synthetic:public", 3, 5, 8)
    policy = ContextPolicy(
        "synthetic:policy", 1, 1, ("TRAINING",), (PUBLIC_FORMAL,),
        ("synthetic:region",), ("synthetic:public",), (PUBLIC_FORMAL,),
        ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        ((PUBLIC_FORMAL, PUBLIC_FORMAL, PUBLIC_FORMAL),))
    frontier = SourceFrontier(
        1, 1, tuple(sorted(grants, key=lambda item: item.source_handle)))
    entry = AbiEntry(0, 0, 0, concept.semantic_id, None, "FORMAL_DOMAIN",
                     True, True, "fixture")
    source_concept = AtlasConcept(
        concept.semantic_id, "concept", ("Entity",), (), (), (), (),
        (SourceRecordRef("fixture", "fixture", concept.semantic_id),))
    frozen = FrozenAtlasConcept(
        source_concept, 0, 0, 0, True, "ADMITTED", True, "fixture")
    snapshot = FrozenAtlasSnapshot(
        "bilqis.semantic-atlas-snapshot/v1",
        "a" * 64, RELEASE, "b" * 64, "c" * 64, "d" * 64,
        "e" * 64, "f" * 64, "0" * 64, "1" * 64, "2" * 64,
        AtlasCounts(1, 1, 1, 1, 1, 1, 0, 0, 0, 0),
        (), (entry,), (frozen,), (), (), ((concept.semantic_id, 0),),
        ((concept.semantic_id, 0),))
    return (envelope,), task, frontier, policy, (schema,), snapshot


class ApprovedMotifSourceTests(TestCase):
    def test_real_a03_frame_and_a13_grants_gate_motif_allocation(self):
        envelopes, task, frontier, policy, schemas, snapshot = approved_source_case()
        result = _probe_approved_motifs(
            envelopes, task, frontier, policy, schemas, snapshot,
            MotifManifest(RELEASE), MotifBudget(2))
        self.assertIsInstance(result, ApprovedMotifCandidate)
        self.assertEqual(len(result.candidate.plan.allocated), 2)
        self.assertEqual(result.candidate.matches[0].disposition, "EXACT")
        self.assertEqual(len(result.approved_context_digest), 64)
        self.assertEqual(result.candidate.plan.allocated[0].key.kind, "STRUCTURAL")

    def test_revoked_source_member_does_not_allocate_motif(self):
        envelopes, task, frontier, policy, schemas, snapshot = approved_source_case()
        revoked = replace(frontier, grants=tuple(
            replace(grant, revoked=True)
            if grant.source_handle == "source:member:actor" else grant
            for grant in frontier.grants))
        result = _probe_approved_motifs(
            envelopes, task, revoked, policy, schemas, snapshot,
            MotifManifest(RELEASE), MotifBudget(2))
        self.assertIsInstance(result, ContextHold)
        self.assertIn("BAMF_CONTEXT_SOURCE_REVOKED", result.reason_codes)

    def test_source_owned_types_reject_forged_but_role_allowed_type(self):
        envelopes, task, frontier, policy, schemas, snapshot = approved_source_case(
            forged_type=True)
        with self.assertRaises(BilqisError) as caught:
            _probe_approved_motifs(
                envelopes, task, frontier, policy, schemas, snapshot,
                MotifManifest(RELEASE), MotifBudget(2))
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_CONCEPT_TYPE_AUTHORITY_MISMATCH")

    def test_source_qualified_but_inactive_abi_cannot_become_motif(self):
        envelopes, task, frontier, policy, schemas, snapshot = approved_source_case()
        inactive = replace(
            snapshot,
            abi_entries=(replace(snapshot.abi_entries[0], active=False),),
            concepts=(replace(snapshot.concepts[0], active=False),))
        with self.assertRaises(BilqisError) as caught:
            _probe_approved_motifs(
                envelopes, task, frontier, policy, schemas, inactive,
                MotifManifest(RELEASE), MotifBudget(2))
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_MOTIF_SEMANTIC_NOT_ADMITTED")

    def test_source_schema_or_release_mismatch_fails_closed(self):
        envelopes, task, frontier, policy, schemas, snapshot = approved_source_case()
        for changed in (
            {"schemas": ()},
            {"snapshot": replace(snapshot, release_sha256="9" * 64)},
            {"parent_manifest": MotifManifest("9" * 64)},
        ):
            args = dict(
                envelopes=envelopes, task=task, frontier=frontier,
                policy=policy, schemas=schemas, snapshot=snapshot,
                parent_manifest=MotifManifest(RELEASE), budget=MotifBudget(2))
            args.update(changed)
            with self.subTest(changed=changed), self.assertRaises(BilqisError):
                _probe_approved_motifs(**args)
