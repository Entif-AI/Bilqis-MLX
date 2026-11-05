"""Frame occurrence identity, child edges and public records."""
from __future__ import annotations

import pickle
import unittest
from typing import get_type_hints
from unittest import TestCase

from bilqis_mlx.semantics.frame_schema import (
    BindingState, FrameEdge, FrameInstance, RoleOccurrence, SourceSpan,
    make_frame_instance, ChildFrameRef, FrameSchema, RoleSpec,
    frame_instance_from_bytes, frame_schema_from_bytes,
)
from bilqis_mlx.semantics.tests.frame_schema.fixtures import _concept, _transfer_schema


class InstanceIdentityTests(TestCase):
    def test_occurrence_pickle_and_child_edge_type_hints_keep_public_records(self):
        frame = make_frame_instance(
            _transfer_schema(), source_instance_id="source:pickle",
            structural_path=(), source_span=SourceSpan(0, 3),
            parent_occurrence_id=None, causal_prefix_end=3,
            bindings=tuple(RoleOccurrence(role, 0, concept=_concept(role, index))
                           for index, role in enumerate(("agent", "recipient", "theme"))))
        for value in (frame, BindingState.VALUE):
            with self.subTest(record=type(value).__name__):
                restored = pickle.loads(pickle.dumps(value))
                self.assertIs(type(restored), type(value))
                self.assertEqual(restored, value)
                self.assertEqual(
                    type(value).__module__, "bilqis_mlx.semantics.frame_schema")
        self.assertEqual(
            get_type_hints(FrameInstance.child_edges.fget)["return"],
            tuple[FrameEdge, ...])


class FrameInstancesTests(unittest.TestCase):
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
