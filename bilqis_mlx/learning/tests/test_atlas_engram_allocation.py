"""B07.1 frozen-A03-protocol motif keys and candidate-only allocation proof."""
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
from unittest import TestCase
from unittest.mock import patch
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram import (
    MAX_CANDIDATE_ALLOCATIONS, INITIAL_MOTIF_CAPACITY,
    MAX_MOTIF_CAPACITY, MOTIF_PAGE_STATE_BYTES, CandidateMotifView,
    MotifBudget, MotifFrameInput, MotifManifest, MotifPageGrowth,
    MotifSlot, candidate_motif_manifest, initialize_planned_motif_slot,
    motif_keys, prepare_motifs, _plan_page_growth,
)
from bilqis_mlx.learning.atlas_engram_transaction import (
    CandidateMotifSnapshot, MotifAliasArtifact, MotifAllocationSnapshot,
    prepare_candidate_motif_snapshot, verify_candidate_motif_snapshot,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
    initialize_bamf_row,
)


RELEASE = "a" * 64
SCOPE = "source:scope:1"
_COUNT = 0


@dataclass(frozen=True)
class Role:
    role_id: str
    allowed_type_ids: tuple[str, ...]
    min_cardinality: int = 0
    max_cardinality: int = 1


@dataclass(frozen=True)
class Schema:
    roles: tuple[Role, ...]
    schema_id: str = "source:relation"
    revision: int = 1
    ast_construct: str = "apply:relation"
    ast_contract_sha256: str = "b" * 64
    order_mode: str = "ORDERED"
    scope: str = SCOPE
    schema_version: str = "bilqis.semantic-frame-schema/v1"


@dataclass(frozen=True)
class Concept:
    semantic_id: str
    type_ids: tuple[str, ...]
    semantic_release: str = RELEASE
    source_reference: str = "source:approved:row"
    schema_version: str = "bilqis.semantic-concept-ref/v1"


@dataclass(frozen=True)
class Child:
    occurrence_id: str = "c" * 64
    content_digest: str = "d" * 64
    type_ids: tuple[str, ...] = ("Frame",)
    schema_version: str = "bilqis.semantic-child-frame-ref/v1"


@dataclass(frozen=True)
class Binding:
    role_id: str
    occurrence_index: int
    concept: Concept | None = None
    child_frame: Child | None = None
    state: str = "VALUE"
    alternatives: tuple[Concept, ...] = ()


@dataclass(frozen=True)
class Frame:
    bindings: tuple[Binding, ...]
    schema_role_order: tuple[str, ...]
    occurrence_id: str = "1" * 64
    content_digest: str = "2" * 64
    frame_schema_id: str = "source:relation"
    frame_schema_revision: int = 1
    schema_version: str = "bilqis.semantic-frame-instance/v2"


def source(
    actor="urn:actor:alice", patient="urn:patient:bob", *,
    scope=SCOPE, state="VALUE", child=False, types=("Person",),
    occurrence="1" * 64,
):
    schema = Schema((
        Role("actor", ("Frame", "Person")),
        Role("patient", ("Person",)),
    ), scope=scope)
    actor_binding = (
        Binding("actor", 0, child_frame=Child()) if child else
        Binding("actor", 0, concept=Concept(actor, types)))
    patient_binding = Binding("patient", 0, concept=Concept(patient, ("Person",)))
    if state == "NONE":
        actor_binding = Binding("actor", 0, state="NONE")
    elif state == "UNKNOWN":
        actor_binding = Binding("actor", 0, state="UNKNOWN")
    elif state == "ALTERNATIVES":
        actor_binding = Binding(
            "actor", 0, state="ALTERNATIVES",
            alternatives=(Concept(actor, types), Concept("urn:actor:carol", types)))
    frame = Frame((actor_binding, patient_binding),
                  ("actor", "patient"), occurrence_id=occurrence)
    return MotifFrameInput(frame, schema)


@lru_cache(maxsize=1)
def full_first_page() -> MotifManifest:
    base = motif_keys(source(), RELEASE)[0]
    return MotifManifest(
        RELEASE,
        tuple(MotifSlot(index, replace(base, relation_signature=f"{index:064x}"))
              for index in range(INITIAL_MOTIF_CAPACITY)),
    )


class MotifKeyTests(TestCase):
    def test_different_fillers_share_typed_structural_but_not_exact_key(self):
        a, b = source(), source(actor="urn:actor:carol", patient="urn:patient:dave")
        a_exact, a_structural = motif_keys(a, RELEASE)
        b_exact, b_structural = motif_keys(b, RELEASE)
        self.assertNotEqual(a_exact, b_exact)
        self.assertNotEqual(a_exact.digest, b_exact.digest)
        self.assertEqual(a_structural, b_structural)
        self.assertEqual(a_structural.digest, b_structural.digest)
        self.assertEqual(
            [(member.role_id, member.occurrence_index)
             for member in a_structural.members],
            [("actor", 0), ("patient", 0)])
        self.assertEqual(a_structural.scope, SCOPE)

    def test_role_swap_scope_and_child_structure_change_key(self):
        original = source()
        swapped = source(actor="urn:patient:bob", patient="urn:actor:alice")
        other_scope = source(scope="source:scope:2")
        child = source(child=True)
        for changed in (swapped, other_scope, child):
            self.assertNotEqual(motif_keys(original, RELEASE)[0],
                                motif_keys(changed, RELEASE)[0])
        self.assertNotEqual(motif_keys(original, RELEASE)[1],
                            motif_keys(other_scope, RELEASE)[1])
        self.assertNotEqual(motif_keys(original, RELEASE)[1],
                            motif_keys(child, RELEASE)[1])
        self.assertNotEqual(
            motif_keys(original, RELEASE)[0].relation_signature,
            motif_keys(child, RELEASE)[0].relation_signature)

    def test_none_unknown_alternatives_are_distinct_and_not_invented(self):
        keys = [motif_keys(source(state=state), RELEASE)
                for state in ("VALUE", "NONE", "UNKNOWN", "ALTERNATIVES")]
        self.assertEqual(len({item[0] for item in keys}), 4)
        self.assertEqual(len({item[1] for item in keys}), 4)
        self.assertEqual(
            [item[0].members[0].state for item in keys],
            ["VALUE", "NONE", "UNKNOWN", "ALTERNATIVES"])

    def test_distinct_child_occurrences_preserve_exact_identity(self):
        first = source(child=True)
        changed_binding = replace(
            first.frame.bindings[0],
            child_frame=replace(first.frame.bindings[0].child_frame,
                                occurrence_id="e" * 64))
        second = replace(first, frame=replace(
            first.frame, bindings=(changed_binding, first.frame.bindings[1])))
        a_exact, a_structural = motif_keys(first, RELEASE)
        b_exact, b_structural = motif_keys(second, RELEASE)
        self.assertNotEqual(a_exact, b_exact)
        self.assertEqual(a_structural, b_structural)

    def test_structural_child_filler_abstracts_exact_content_but_keeps_relation(self):
        first = source(child=True)
        original = first.frame.bindings[0]
        second = replace(first, frame=replace(
            first.frame, bindings=(
                replace(original, child_frame=replace(
                    original.child_frame, occurrence_id="e" * 64,
                    content_digest="f" * 64)),
                first.frame.bindings[1])))
        exact_a, structural_a = motif_keys(first, RELEASE)
        exact_b, structural_b = motif_keys(second, RELEASE)
        self.assertNotEqual(exact_a.relation_signature,
                            exact_b.relation_signature)
        self.assertEqual(structural_a.relation_signature,
                         structural_b.relation_signature)
        self.assertNotEqual(exact_a, exact_b)
        self.assertEqual(structural_a, structural_b)

    def test_valid_empty_optional_frame_has_canonical_motif_key(self):
        schema = Schema((Role("optional", ("Person",), 0, 1),))
        frame = Frame((), ("optional",))
        source_frame = MotifFrameInput(frame, schema)
        exact, structural = motif_keys(source_frame, RELEASE)
        self.assertEqual(exact.members, ())
        self.assertEqual(structural.members, ())
        self.assertNotEqual(exact, structural)
        view = prepare_motifs(
            (source_frame,), MotifManifest(RELEASE), MotifBudget(2))
        self.assertEqual([slot.key.kind for slot in view.plan.allocated],
                         ["STRUCTURAL", "EXACT"])

    def test_foreign_release_schema_and_type_reject_before_key_admission(self):
        valid = source()
        changes = (
            replace(valid, frame=replace(valid.frame, frame_schema_revision=2)),
            replace(valid, frame=replace(valid.frame,
                                         schema_role_order=("patient", "actor"))),
            replace(valid, frame=replace(valid.frame, schema_version="v1")),
            replace(valid, frame=replace(
                valid.frame, bindings=(
                    replace(valid.frame.bindings[0], concept=Concept(
                        "urn:actor:alice", ("Number",))), valid.frame.bindings[1]))),
            replace(valid, frame=replace(
                valid.frame, bindings=(
                    replace(valid.frame.bindings[0], concept=Concept(
                        "urn:actor:alice", ("Person",),
                        semantic_release="9" * 64)), valid.frame.bindings[1]))),
        )
        for changed in changes:
            with self.subTest(changed=changed), self.assertRaises(BilqisError):
                motif_keys(changed, RELEASE)


class MotifPreparationTests(TestCase):
    def test_exact_hit_precedes_structural_hit(self):
        sample = source()
        exact, structural = motif_keys(sample, RELEASE)
        parent = MotifManifest(RELEASE, (
            MotifSlot(0, structural), MotifSlot(1, exact)))
        before = parent.digest
        view = prepare_motifs((sample,), parent, MotifBudget(0))
        self.assertEqual(view.matches[0].disposition, "EXACT")
        self.assertEqual(view.matches[0].slot_id, 1)
        self.assertEqual(view.plan.allocated, ())
        self.assertEqual(view.plan.pending, ())
        self.assertEqual(parent.digest, before)

    def test_structural_first_then_exact_and_deterministic_use_priority(self):
        frequent = source(actor="urn:actor:frequent", occurrence="3" * 64)
        rare = source(actor="urn:actor:rare", occurrence="4" * 64)
        observations = (rare, frequent, frequent, frequent)
        first = prepare_motifs(observations, MotifManifest(RELEASE), MotifBudget(4))
        second = prepare_motifs(observations, MotifManifest(RELEASE), MotifBudget(4))
        self.assertEqual(first, second)
        self.assertEqual([slot.slot_id for slot in first.plan.allocated], [0, 1, 2])
        self.assertEqual(
            [slot.key.kind for slot in first.plan.allocated],
            ["STRUCTURAL", "EXACT", "EXACT"])
        self.assertEqual(first.plan.allocated[1].key,
                         motif_keys(frequent, RELEASE)[0])
        self.assertEqual(first.matches[0].disposition, "EXACT")
        self.assertEqual(first.matches[1].disposition, "EXACT")
        self.assertEqual(first.plan.pending, ())

    def test_at_most_64_new_slots_and_unallocated_keys_remain_pending(self):
        observations = tuple(
            source(actor=f"urn:actor:{i}", occurrence=f"{i:064x}")
            for i in range(70))
        parent = MotifManifest(RELEASE)
        view = prepare_motifs(observations, parent, MotifBudget(64))
        self.assertIsInstance(view, CandidateMotifView)
        self.assertEqual(len(view.plan.allocated), MAX_CANDIDATE_ALLOCATIONS)
        self.assertEqual(len(view.plan.pending), 7)
        self.assertEqual(view.plan.allocated[0].key.kind, "STRUCTURAL")
        self.assertEqual(len(parent.slots), 0)
        self.assertEqual(len(view.matches), 70)
        self.assertEqual(
            sum(item.disposition == "STRUCTURAL" for item in view.matches), 7)

    def test_zero_allocation_budget_keeps_factorized_fallback_and_parent_bytes(self):
        occupied = motif_keys(source(), RELEASE)[0]
        parent = MotifManifest(RELEASE, (MotifSlot(0, occupied),))
        sample = source(types=("Frame",), actor="urn:child:other")
        before = parent.digest
        view = prepare_motifs((sample,), parent, MotifBudget(0))
        self.assertEqual(view.matches[0].disposition, "FACTORIZED_FALLBACK")
        self.assertIsNone(view.matches[0].slot_id)
        self.assertEqual(view.plan.allocated, ())
        self.assertEqual(len(view.plan.pending), 2)
        self.assertEqual(parent.digest, before)

    def test_forced_hash_bucket_collision_never_aliases_full_key(self):
        a = motif_keys(source(), RELEASE)[0]
        b = motif_keys(source(actor="urn:actor:carol"), RELEASE)[0]
        c = motif_keys(source(actor="urn:actor:dan"), RELEASE)[0]
        manifest = MotifManifest(RELEASE, (MotifSlot(0, a), MotifSlot(1, b)))
        with patch("bilqis_mlx.learning.atlas_engram._bucket", return_value="collision"):
            self.assertEqual(manifest.lookup(a), 0)
            self.assertEqual(manifest.lookup(b), 1)
            self.assertIsNone(manifest.lookup(c))

    def test_budget_and_manifest_fail_closed(self):
        for invalid in (-1, 65, True):
            with self.assertRaises(BilqisError):
                MotifBudget(invalid)
        exact = motif_keys(source(), RELEASE)[0]
        with self.assertRaises(BilqisError):
            MotifManifest(RELEASE, (MotifSlot(1, exact),))
        with self.assertRaises(BilqisError):
            MotifManifest(RELEASE, (MotifSlot(0, exact), MotifSlot(1, exact)))
        with self.assertRaises(BilqisError):
            MotifManifest(RELEASE, (MotifSlot(0, exact),), capacity=0)
        with self.assertRaises(BilqisError):
            MotifManifest(RELEASE, (MotifSlot(0, exact),), capacity=1)
        with self.assertRaises(BilqisError):
            MotifManifest(RELEASE, (MotifSlot(0, exact),), capacity=65537)

    def test_full_page_grows_once_only_with_explicit_state_budget(self):
        parent = full_first_page()
        before = parent.digest
        insufficient = prepare_motifs(
            (source(),), parent,
            MotifBudget(2, page_growth_bytes=MOTIF_PAGE_STATE_BYTES - 1))
        self.assertEqual(insufficient.page_growth.added_pages, 0)
        self.assertEqual(insufficient.plan.allocated, ())
        self.assertEqual(len(insufficient.plan.pending), 2)
        self.assertEqual(insufficient.matches[0].disposition, "FACTORIZED_FALLBACK")
        self.assertEqual(parent.digest, before)

        candidate = prepare_motifs(
            (source(),), parent,
            MotifBudget(2, page_growth_bytes=MOTIF_PAGE_STATE_BYTES))
        self.assertEqual(candidate.page_growth.added_pages, 1)
        self.assertEqual(candidate.page_growth.reserved_state_bytes, 25165824)
        self.assertEqual(candidate.page_growth.declared_budget_bytes, 25165824)
        self.assertEqual(candidate.page_growth.candidate_capacity, 32768)
        self.assertEqual([slot.slot_id for slot in candidate.plan.allocated],
                         [16384, 16385])
        self.assertEqual(candidate.plan.pending, ())
        next_manifest = candidate_motif_manifest(parent, candidate)
        self.assertEqual(next_manifest.capacity, 32768)
        self.assertEqual(next_manifest.slots[:16384], parent.slots)
        self.assertEqual(next_manifest.lookup(candidate.plan.allocated[0].key), 16384)
        self.assertEqual(parent.capacity, 16384)
        self.assertEqual(parent.digest, before)

    def test_planned_row_uses_b01_deterministic_seed_and_page_identity(self):
        candidate = prepare_motifs(
            (source(),), full_first_page(),
            MotifBudget(2, page_growth_bytes=MOTIF_PAGE_STATE_BYTES))
        topology = ModelTopologySpecV2()
        extents = GenerationExtents(1, 2, "a" * 64, "b" * 64, "c" * 64)
        slot = candidate.plan.allocated[0]
        first = initialize_planned_motif_slot(
            candidate, slot.slot_id, run_seed=17,
            topology=topology, extents=extents)
        second = initialize_planned_motif_slot(
            candidate, slot.slot_id, run_seed=17,
            topology=topology, extents=extents)
        self.assertEqual(first.shape, (128,))
        self.assertEqual(first.dtype, np.float32)
        self.assertEqual(hashlib.sha256(first.tobytes()).hexdigest(),
                         "b1755e52244d359a20084634c1329b87c09b9786491d8eaad1ac5b58ecc06599")
        np.testing.assert_array_equal(first, second)
        declared = next(item for item in expected_bamf_shapes(topology, extents)
                        if item.name == "motif.page.1")
        np.testing.assert_array_equal(
            first, initialize_bamf_row(
                declared, run_seed=17, row_id=slot.key.digest))
        self.assertFalse(np.array_equal(
            first, initialize_planned_motif_slot(
                candidate, slot.slot_id, run_seed=18,
                topology=topology, extents=extents)))
        with self.assertRaises(BilqisError):
            initialize_planned_motif_slot(
                candidate, 0, run_seed=17, topology=topology, extents=extents)
        with self.assertRaises(BilqisError):
            initialize_planned_motif_slot(
                candidate, slot.slot_id, run_seed=17, topology=topology,
                extents=GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64))

    def test_growth_when_candidate_fills_last_existing_slot(self):
        parent = MotifManifest(RELEASE, full_first_page().slots[:-1])
        without_growth = prepare_motifs(
            (source(),), parent, MotifBudget(2))
        self.assertEqual([slot.slot_id for slot in without_growth.plan.allocated],
                         [16383])
        self.assertEqual(len(without_growth.plan.pending), 1)
        self.assertEqual(without_growth.page_growth.added_pages, 0)
        with_growth = prepare_motifs(
            (source(),), parent,
            MotifBudget(2, page_growth_bytes=MOTIF_PAGE_STATE_BYTES))
        self.assertEqual([slot.slot_id for slot in with_growth.plan.allocated],
                         [16383, 16384])
        self.assertEqual(with_growth.page_growth.added_pages, 1)
        self.assertEqual(with_growth.plan.pending, ())
        self.assertEqual(parent.capacity, 16384)

    def test_page_growth_never_exceeds_four_pages_or_forges_parent(self):
        self.assertEqual(MAX_MOTIF_CAPACITY, 65536)
        with self.assertRaises(BilqisError):
            MotifPageGrowth(65536, 81920, 1, MOTIF_PAGE_STATE_BYTES,
                            MOTIF_PAGE_STATE_BYTES)
        with self.assertRaises(BilqisError):
            MotifPageGrowth(16384, 49152, 2, MOTIF_PAGE_STATE_BYTES * 2,
                            MOTIF_PAGE_STATE_BYTES * 2)
        with self.assertRaises(BilqisError):
            MotifPageGrowth(16384, 32768, 1, MOTIF_PAGE_STATE_BYTES,
                            MOTIF_PAGE_STATE_BYTES - 1)
        self.assertEqual(
            _plan_page_growth(65536, 65536, 2, MOTIF_PAGE_STATE_BYTES * 2).added_pages,
            0)
        self.assertEqual(
            _plan_page_growth(16384, 16383, 2, MOTIF_PAGE_STATE_BYTES).added_pages,
            1)
        for bad in (-1, True, 1.5):
            with self.assertRaises(BilqisError):
                MotifBudget(1, page_growth_bytes=bad)
        parent = MotifManifest(RELEASE)
        candidate = prepare_motifs((source(),), parent, MotifBudget(2))
        foreign = MotifManifest("9" * 64)
        with self.assertRaises(BilqisError):
            candidate_motif_manifest(foreign, candidate)
        forged = replace(candidate, page_growth=MotifPageGrowth(
            16384, 32768, 1, MOTIF_PAGE_STATE_BYTES, MOTIF_PAGE_STATE_BYTES))
        with self.assertRaises(BilqisError):
            candidate_motif_manifest(parent, forged)


class MotifTransactionTests(TestCase):
    def test_rejection_preserves_parent_slots_counters_and_replay_is_deterministic(self):
        parent = MotifAllocationSnapshot(MotifManifest(RELEASE))
        before = parent.digest
        observations = (source(), source(actor="urn:actor:carol"))
        first = prepare_candidate_motif_snapshot(
            observations, parent, MotifBudget(4))
        second = prepare_candidate_motif_snapshot(
            observations, parent, MotifBudget(4))
        self.assertIsInstance(first, CandidateMotifSnapshot)
        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(len(first.proposed.manifest.slots), 3)
        self.assertEqual(len(first.proposed.observed_uses), 3)
        self.assertEqual(parent.digest, before)
        self.assertEqual(parent.manifest.slots, ())
        self.assertEqual(parent.observed_uses, ())
        verify_candidate_motif_snapshot(
            first, frames=observations, parent=parent, budget=MotifBudget(4))

    def test_prior_accepted_counters_change_priority_without_parent_mutation(self):
        rare = source(actor="urn:actor:rare", occurrence="3" * 64)
        frequent = source(actor="urn:actor:frequent", occurrence="4" * 64)
        rare_exact = motif_keys(rare, RELEASE)[0]
        parent = MotifAllocationSnapshot(
            MotifManifest(RELEASE), ((rare_exact.digest, 100),))
        before = parent.digest
        proposal = prepare_candidate_motif_snapshot(
            (rare, frequent, frequent, frequent), parent, MotifBudget(3))
        allocated = proposal.view.plan.allocated
        self.assertEqual([slot.key.kind for slot in allocated],
                         ["STRUCTURAL", "EXACT", "EXACT"])
        self.assertEqual(allocated[1].key, rare_exact)
        self.assertEqual(dict(proposal.proposed.observed_uses)[rare_exact.digest], 101)
        self.assertEqual(parent.digest, before)
        self.assertEqual(parent.observed_uses, ((rare_exact.digest, 100),))

    def test_replay_rejects_validly_shaped_forged_counters_slots_and_parent(self):
        parent = MotifAllocationSnapshot(MotifManifest(RELEASE))
        frames = (source(),)
        budget = MotifBudget(2)
        candidate = prepare_candidate_motif_snapshot(frames, parent, budget)
        wrong_counts = replace(candidate.proposed, observed_uses=(
            (candidate.proposed.observed_uses[0][0], 999),))
        with self.assertRaises(BilqisError):
            verify_candidate_motif_snapshot(
                replace(candidate, proposed=wrong_counts),
                frames=frames, parent=parent, budget=budget)
        foreign_parent = MotifAllocationSnapshot(
            MotifManifest(RELEASE, (candidate.proposed.manifest.slots[0],)))
        with self.assertRaises(BilqisError):
            verify_candidate_motif_snapshot(
                candidate, frames=frames, parent=foreign_parent, budget=budget)
        changed_slot = replace(
            candidate.proposed.manifest.slots[1],
            key=motif_keys(source(actor="urn:actor:other"), RELEASE)[0])
        forged_manifest = replace(
            candidate.proposed.manifest,
            slots=(candidate.proposed.manifest.slots[0], changed_slot))
        with self.assertRaises(BilqisError):
            verify_candidate_motif_snapshot(
                replace(candidate, proposed=replace(
                    candidate.proposed, manifest=forged_manifest)),
                frames=frames, parent=parent, budget=budget)

    def test_alias_is_explicit_attested_artifact_not_an_implicit_slot_remap(self):
        exact = motif_keys(source(), RELEASE)[0]
        parent = MotifAllocationSnapshot(
            MotifManifest(RELEASE, (MotifSlot(0, exact),)))
        alias = MotifAliasArtifact(
            "9" * 64, "8" * 64, RELEASE, exact.digest, "7" * 64)
        proposal = prepare_candidate_motif_snapshot(
            (source(),), parent, MotifBudget(0), source_aliases=(alias,))
        self.assertEqual(proposal.proposed.aliases, (alias,))
        self.assertEqual(proposal.proposed.manifest.slots, parent.manifest.slots)
        self.assertEqual(proposal.proposed.manifest.lookup(exact), 0)
        self.assertEqual(parent.aliases, ())
        verify_candidate_motif_snapshot(
            proposal, frames=(source(),), parent=parent,
            budget=MotifBudget(0), source_aliases=(alias,))
        with self.assertRaises(BilqisError):
            prepare_candidate_motif_snapshot(
                (source(),), parent, MotifBudget(0),
                source_aliases=(alias, replace(alias, source_attestation_digest="6"*64)))
        with self.assertRaises(BilqisError):
            prepare_candidate_motif_snapshot(
                (source(),), parent, MotifBudget(0),
                source_aliases=(replace(alias, new_key_digest="5"*64),))

    def test_full_capacity_and_no_budget_keep_parent_state_unchanged(self):
        parent = MotifAllocationSnapshot(full_first_page())
        before = parent.digest
        candidate = prepare_candidate_motif_snapshot(
            (source(),), parent, MotifBudget(0))
        self.assertEqual(candidate.proposed.manifest, parent.manifest)
        self.assertEqual(candidate.view.plan.allocated, ())
        self.assertEqual(len(candidate.view.plan.pending), 2)
        self.assertEqual(len(candidate.proposed.pending_keys), 2)
        self.assertEqual(parent.digest, before)
        self.assertNotEqual(candidate.proposed.observed_uses, parent.observed_uses)

    def test_pending_keys_survive_candidate_boundary_and_allocate_without_reobservation(self):
        parent = MotifAllocationSnapshot(MotifManifest(RELEASE))
        observed = prepare_candidate_motif_snapshot(
            (source(),), parent, MotifBudget(0))
        self.assertEqual(len(observed.proposed.pending_keys), 2)
        self.assertEqual(len(observed.proposed.manifest.slots), 0)
        # Treat this snapshot only as a hypothetical B13-retained input.
        # No operation in this module publishes or accepts it.
        next_candidate = prepare_candidate_motif_snapshot(
            (), observed.proposed, MotifBudget(2))
        self.assertEqual(len(next_candidate.view.plan.allocated), 2)
        self.assertEqual(next_candidate.proposed.pending_keys, ())
        self.assertEqual(
            tuple(slot.key for slot in next_candidate.proposed.manifest.slots),
            observed.proposed.pending_keys)
        self.assertEqual(
            next_candidate.proposed.observed_uses,
            observed.proposed.observed_uses)
        self.assertEqual(parent.manifest.slots, ())
        self.assertEqual(parent.pending_keys, ())

    def test_candidate_page_growth_preserves_every_old_slot_and_parent_counter(self):
        parent = MotifAllocationSnapshot(
            full_first_page(), (("f" * 64, 7),))
        before = parent.digest
        candidate = prepare_candidate_motif_snapshot(
            (source(),), parent,
            MotifBudget(2, page_growth_bytes=MOTIF_PAGE_STATE_BYTES))
        self.assertEqual(candidate.view.page_growth.added_pages, 1)
        self.assertEqual(candidate.proposed.manifest.capacity, 32768)
        self.assertEqual(
            candidate.proposed.manifest.slots[:INITIAL_MOTIF_CAPACITY],
            parent.manifest.slots)
        self.assertEqual(
            [slot.slot_id for slot in candidate.view.plan.allocated],
            [16384, 16385])
        self.assertEqual(
            dict(candidate.proposed.observed_uses)["f" * 64], 7)
        self.assertEqual(parent.digest, before)

    def test_canonical_counter_validation_rejects_forged_state(self):
        parent = MotifManifest(RELEASE)
        for counts in (
            (("a" * 64, True),),
            (("a" * 64, 0),),
            (("b" * 64, 1), ("a" * 64, 2)),
            (("a" * 64, 1), ("a" * 64, 2)),
            (("not-a-digest", 1),),
        ):
            with self.subTest(counts=counts), self.assertRaises(BilqisError):
                MotifAllocationSnapshot(parent, counts)


if __name__ == "__main__":
    import unittest
    unittest.main()
