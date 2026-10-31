"""MotifKeyTests through the existing engram owner contracts."""
from bilqis_mlx.learning.tests.test_atlas_engram_allocation import (
    BilqisError, Concept, Frame, MotifBudget,
    MotifFrameInput, MotifManifest, RELEASE, Role,
    SCOPE, Schema, TestCase, motif_keys,
    prepare_motifs, replace, source,
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
