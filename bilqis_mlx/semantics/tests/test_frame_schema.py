from __future__ import annotations

import unittest

from bilqis_mlx.semantics.core import Apply, Operation, Signature, literal
from bilqis_mlx.semantics.frame_schema import (
    ChildFrameRef,
    ConceptRef,
    FrameSchema,
    RoleOccurrence,
    RoleSpec,
    SourceSpan,
    ast_construct_id,
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


if __name__ == "__main__":
    unittest.main()
