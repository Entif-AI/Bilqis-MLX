from __future__ import annotations

import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry,
    AtlasCounts,
    FrozenAtlasSnapshot,
)
from bilqis_mlx.semantics.core import Apply, Operation, Signature, literal
from bilqis_mlx.semantics.frame_schema import (
    AtomicFrame,
    BindingState,
    ChildFrameRef,
    ConceptRef,
    FrameSchema,
    RoleOccurrence,
    RoleSpec,
    SourceSpan,
    ast_construct_id,
    bind_ast_frames,
    bind_frame_instance,
    frame_instance_from_bytes,
    frame_schema_from_bytes,
    make_frame_instance,
    native_ast_content_digest,
)


RELEASE = "1" * 64


def _concept(name: str, index: int, type_name: str = "Entity") -> ConceptRef:
    return ConceptRef(
        semantic_id="formal:" + name,
        semantic_release=RELEASE,
        abi_index=index,
        type_ids=(type_name,),
        source_reference="fixture:" + name,
    )


def _transfer_schema() -> FrameSchema:
    return FrameSchema(
        schema_id="formal.frame.TRANSFER",
        revision=1,
        ast_construct="apply:formal.operator.TRANSFER",
        roles=(
            RoleSpec("agent", ("Entity",), 1, 1),
            RoleSpec("recipient", ("Entity",), 1, 1),
            RoleSpec("theme", ("Entity",), 1, 1),
        ),
        order_mode="ORDERED",
        scope="source-expression",
    )


def _snapshot(*concepts: ConceptRef) -> FrozenAtlasSnapshot:
    entries = tuple(AbiEntry(
        index=item.abi_index,
        bank=0,
        row=item.abi_index,
        semantic_id=item.semantic_id,
        symbol=None,
        source="FORMAL_DOMAIN",
        active=True,
        teaching_candidate=True,
        reason="fixture",
    ) for item in sorted(concepts, key=lambda item: item.abi_index))
    return FrozenAtlasSnapshot(
        schema="bilqis.semantic-atlas-snapshot/v1",
        bundle_id="a" * 64,
        release_sha256=RELEASE,
        source_bundle_id="b" * 64,
        canonical_rdf_sha256="c" * 64,
        coverage_sha256="d" * 64,
        source_rows_sha256="e" * 64,
        conformance_sha256="f" * 64,
        prior_abi_sha256="0" * 64,
        shape_policy_sha256="1" * 64,
        active_set_sha256="2" * 64,
        counts=AtlasCounts(1, 1, 1, len(entries), 1, len(entries), 0, 0, 0, 0),
        formal_domain_bindings=(),
        abi_entries=entries,
        concepts=(),
        relations=(),
        withheld_rows=(),
        semantic_lookup=tuple(sorted((entry.semantic_id, entry.index) for entry in entries)),
        concept_lookup=(),
    )


class FrameSchemaRecordTests(unittest.TestCase):
    def test_native_ast_constructor_and_digest_reuse_existing_semantics_core(self):
        operation = Operation(
            17,
            "formal.operator.TRANSFER",
            Signature(("Entity", "Entity"), "Entity"),
            "a" * 64,
        )
        source = literal("alice", "Entity")
        target = literal("book", "Entity")
        expression = Apply(operation, (source, target), "Entity", None)

        self.assertEqual(ast_construct_id(expression), "apply:formal.operator.TRANSFER")
        self.assertEqual(ast_construct_id(source), "literal:Entity")
        self.assertEqual(native_ast_content_digest(expression),
                         native_ast_content_digest(expression))

    def test_occurrence_identity_is_source_path_identity_not_content_identity(self):
        schema = _transfer_schema()
        bindings = (
            RoleOccurrence("agent", 0, concept=_concept("alice", 10)),
            RoleOccurrence("recipient", 0, concept=_concept("bob", 11)),
            RoleOccurrence("theme", 0, concept=_concept("book", 12)),
        )
        first = make_frame_instance(
            schema,
            source_instance_id="source-record-1",
            structural_path=(0, 2),
            source_span=SourceSpan(4, 19),
            parent_occurrence_id=None,
            bindings=bindings,
            causal_prefix_end=19,
        )
        second = make_frame_instance(
            schema,
            source_instance_id="source-record-2",
            structural_path=(0, 2),
            source_span=SourceSpan(40, 55),
            parent_occurrence_id=None,
            bindings=bindings,
            causal_prefix_end=55,
        )

        self.assertNotEqual(first.occurrence_id, second.occurrence_id)
        self.assertEqual(first.content_digest, second.content_digest)

    def test_transfer_role_swap_changes_content_without_collapsing_same_type_roles(self):
        schema = _transfer_schema()
        alice = _concept("alice", 10)
        bob = _concept("bob", 11)
        book = _concept("book", 12)
        first = make_frame_instance(
            schema,
            source_instance_id="transfer-1",
            structural_path=(0,),
            source_span=SourceSpan(0, 20),
            parent_occurrence_id=None,
            bindings=(
                RoleOccurrence("agent", 0, concept=alice),
                RoleOccurrence("recipient", 0, concept=bob),
                RoleOccurrence("theme", 0, concept=book),
            ),
            causal_prefix_end=20,
        )
        swapped = make_frame_instance(
            schema,
            source_instance_id="transfer-1",
            structural_path=(0,),
            source_span=SourceSpan(0, 20),
            parent_occurrence_id=None,
            bindings=(
                RoleOccurrence("agent", 0, concept=bob),
                RoleOccurrence("recipient", 0, concept=alice),
                RoleOccurrence("theme", 0, concept=book),
            ),
            causal_prefix_end=20,
        )

        self.assertEqual(first.occurrence_id, swapped.occurrence_id)
        self.assertNotEqual(first.content_digest, swapped.content_digest)
        self.assertEqual(first.bindings[0].concept.type_ids,
                         first.bindings[1].concept.type_ids)
        self.assertEqual([binding.key for binding in first.bindings],
                         [("agent", 0), ("recipient", 0), ("theme", 0)])

    def test_role_occurrence_keys_and_explicit_child_edges_roundtrip(self):
        schema = FrameSchema(
            schema_id="formal.frame.GROUP",
            revision=2,
            ast_construct="apply:formal.operator.GROUP",
            roles=(RoleSpec("member", ("Entity",), 1, 2),),
            order_mode="ORDERED",
            scope="nested",
        )
        child = ChildFrameRef("2" * 64, "3" * 64)
        instance = make_frame_instance(
            schema,
            source_instance_id="group-7",
            structural_path=(1, 4),
            source_span=SourceSpan(20, 38),
            parent_occurrence_id="4" * 64,
            bindings=(
                RoleOccurrence("member", 0, concept=_concept("alice", 10)),
                RoleOccurrence("member", 1, child_frame=child),
            ),
            causal_prefix_end=38,
        )

        self.assertEqual([binding.key for binding in instance.bindings],
                         [("member", 0), ("member", 1)])
        self.assertEqual(
            [(edge.parent_occurrence_id, edge.role_id, edge.occurrence_index,
              edge.child_occurrence_id) for edge in instance.child_edges],
            [(instance.occurrence_id, "member", 1, child.occurrence_id)],
        )
        self.assertEqual(frame_schema_from_bytes(schema.canonical_bytes()), schema)
        self.assertEqual(frame_instance_from_bytes(instance.canonical_bytes()), instance)

    def test_declared_none_unknown_and_alternatives_are_not_missing_bindings(self):
        alice = _concept("alice", 0)
        bob = _concept("bob", 1)
        snapshot = _snapshot(alice, bob)
        schema = FrameSchema(
            schema_id="formal.frame.EPISTEMIC",
            revision=1,
            ast_construct="source:epistemic",
            roles=(
                RoleSpec("absent", ("Entity",), 1, 1),
                RoleSpec("unknown", ("Entity",), 1, 1),
                RoleSpec("choice", ("Entity",), 1, 1),
            ),
            order_mode="ORDERED",
            scope="clause",
        )
        tree = bind_ast_frames(
            {"kind": "epistemic", "value": "fixture"},
            snapshot,
            schema=schema,
            source_instance_id="epistemic-1",
            source_span=SourceSpan(0, 12),
            bindings=(
                RoleOccurrence("absent", 0, state=BindingState.NONE),
                RoleOccurrence("unknown", 0, state=BindingState.UNKNOWN),
                RoleOccurrence(
                    "choice",
                    0,
                    state=BindingState.ALTERNATIVES,
                    alternatives=(alice, bob),
                ),
            ),
            causal_prefix_end=12,
            declared_scope="clause",
        )
        instance = tree.root
        self.assertEqual(
            [binding.state for binding in instance.bindings],
            [BindingState.NONE, BindingState.UNKNOWN, BindingState.ALTERNATIVES],
        )
        restored = frame_instance_from_bytes(instance.canonical_bytes())
        self.assertEqual(restored, instance)
        self.assertEqual(restored.bindings[2].alternatives, (alice, bob))

    def test_singular_duplicate_fails_and_plural_occurrence_zero_one_succeeds(self):
        alice = _concept("alice", 0)
        bob = _concept("bob", 1)
        snapshot = _snapshot(alice, bob)
        singular = FrameSchema(
            "formal.frame.SINGLE",
            1,
            "source:group",
            (RoleSpec("member", ("Entity",), 1, 1),),
            "ORDERED",
            "group",
        )
        bindings = (
            RoleOccurrence("member", 0, concept=alice),
            RoleOccurrence("member", 1, concept=bob),
        )
        with self.assertRaises(BilqisError) as caught:
            bind_frame_instance(
                singular,
                snapshot,
                source_instance_id="group-1",
                structural_path=(),
                source_span=SourceSpan(0, 5),
                parent_occurrence_id=None,
                bindings=bindings,
                causal_prefix_end=5,
                declared_scope="group",
            )
        self.assertIn("FRAME_ROLE_CARDINALITY_INVALID",
                      str(caught.exception.context.get("reason")))

        plural = FrameSchema(
            "formal.frame.PLURAL",
            1,
            "source:group",
            (RoleSpec("member", ("Entity",), 1, 2),),
            "ORDERED",
            "group",
        )
        frame = bind_frame_instance(
            plural,
            snapshot,
            source_instance_id="group-1",
            structural_path=(),
            source_span=SourceSpan(0, 5),
            parent_occurrence_id=None,
            bindings=bindings,
            causal_prefix_end=5,
            declared_scope="group",
        )
        self.assertEqual([item.key for item in frame.bindings],
                         [("member", 0), ("member", 1)])

    def test_type_scope_causal_prefix_and_foreign_release_fail_before_use(self):
        entity = _concept("alice", 0)
        snapshot = _snapshot(entity)
        schema = FrameSchema(
            "formal.frame.CHECK",
            1,
            "source:check",
            (RoleSpec("actor", ("Entity",), 1, 1),),
            "ORDERED",
            "clause",
        )
        common = dict(
            schema=schema,
            snapshot=snapshot,
            source_instance_id="check-1",
            structural_path=(),
            source_span=SourceSpan(2, 8),
            parent_occurrence_id=None,
            causal_prefix_end=8,
            declared_scope="clause",
        )
        with self.assertRaises(BilqisError) as wrong_scope:
            bind_frame_instance(
                **{**common, "declared_scope": "sentence"},
                bindings=(RoleOccurrence("actor", 0, concept=entity),),
            )
        self.assertIn("FRAME_SCOPE_MISMATCH",
                      str(wrong_scope.exception.context.get("reason")))

        with self.assertRaises(BilqisError) as future:
            bind_frame_instance(
                **{**common, "causal_prefix_end": 7},
                bindings=(RoleOccurrence("actor", 0, concept=entity),),
            )
        self.assertIn("FRAME_CAUSAL_PREFIX_INVALID",
                      str(future.exception.context.get("reason")))

        wrong_type = ConceptRef(
            semantic_id=entity.semantic_id,
            semantic_release=entity.semantic_release,
            abi_index=entity.abi_index,
            type_ids=("Boolean",),
            source_reference=entity.source_reference,
        )
        with self.assertRaises(BilqisError) as typed:
            bind_frame_instance(
                **common,
                bindings=(RoleOccurrence("actor", 0, concept=wrong_type),),
            )
        self.assertIn("FRAME_ROLE_TYPE_INVALID",
                      str(typed.exception.context.get("reason")))

        foreign = ConceptRef(
            semantic_id=entity.semantic_id,
            semantic_release="9" * 64,
            abi_index=entity.abi_index,
            type_ids=entity.type_ids,
            source_reference=entity.source_reference,
        )
        with self.assertRaises(BilqisError) as release:
            bind_frame_instance(
                **common,
                bindings=(RoleOccurrence("actor", 0, concept=foreign),),
            )
        self.assertIn("FRAME_SEMANTIC_RELEASE_MISMATCH",
                      str(release.exception.context.get("reason")))

    def test_unknown_schema_uses_atomic_fallback_with_source_data_intact(self):
        snapshot = _snapshot(_concept("alice", 0))
        source = {
            "kind": "unreleased_construct",
            "scope": {"negated": True, "modal": "possible"},
            "args": [{"kind": "literal", "value": "alice"}],
        }
        tree = bind_ast_frames(
            source,
            snapshot,
            schema=None,
            source_instance_id="source-unknown-7",
            source_span=SourceSpan(3, 18),
            causal_prefix_end=18,
        )
        self.assertIsInstance(tree.root, AtomicFrame)
        self.assertEqual(tree.root.ast_construct, "source:unreleased_construct")
        self.assertEqual(tree.root.source_data, source)
        self.assertEqual(tree.root.source_span, SourceSpan(3, 18))

    def test_nested_scope_keeps_child_occurrence_and_content_identity_unflattened(self):
        entity = _concept("alice", 0)
        snapshot = _snapshot(entity)
        inner_schema = FrameSchema(
            "formal.frame.NEGATION",
            1,
            "source:negate",
            (RoleSpec("value", ("Entity",), 1, 1),),
            "ORDERED",
            "negation",
        )
        inner = bind_frame_instance(
            inner_schema,
            snapshot,
            source_instance_id="scope-1",
            structural_path=(0,),
            source_span=SourceSpan(4, 9),
            parent_occurrence_id=None,
            bindings=(RoleOccurrence("value", 0, concept=entity),),
            causal_prefix_end=9,
            declared_scope="negation",
        )
        outer_schema = FrameSchema(
            "formal.frame.SCOPE",
            1,
            "source:scope",
            (RoleSpec("body", ("Frame",), 1, 1),),
            "ORDERED",
            "modal-scope",
        )
        outer = bind_frame_instance(
            outer_schema,
            snapshot,
            source_instance_id="scope-1",
            structural_path=(),
            source_span=SourceSpan(0, 12),
            parent_occurrence_id=None,
            bindings=(RoleOccurrence(
                "body",
                0,
                child_frame=ChildFrameRef(inner.occurrence_id, inner.content_digest),
            ),),
            causal_prefix_end=12,
            declared_scope="modal-scope",
        )
        restored = frame_instance_from_bytes(outer.canonical_bytes())
        self.assertEqual(restored.bindings[0].child_frame.occurrence_id,
                         inner.occurrence_id)
        self.assertEqual(restored.bindings[0].child_frame.content_digest,
                         inner.content_digest)
        self.assertEqual(restored.child_edges[0].child_occurrence_id,
                         inner.occurrence_id)


if __name__ == "__main__":
    unittest.main()
