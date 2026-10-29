"""B07.1 frozen-A03-protocol motif keys and candidate-only allocation proof."""
from dataclasses import dataclass, replace
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram import (
    MAX_CANDIDATE_ALLOCATIONS, CandidateMotifView, MotifBudget,
    MotifFrameInput, MotifManifest, MotifSlot, motif_keys, prepare_motifs,
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


if __name__ == "__main__":
    import unittest
    unittest.main()
