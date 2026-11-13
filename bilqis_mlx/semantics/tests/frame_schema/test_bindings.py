"""Frame-schema bindings witnesses."""
from __future__ import annotations

import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    bind_frame_instance,
)
from bilqis_mlx.semantics.tests.frame_schema.fixtures import _concept, _snapshot


class FrameBindingsTests(unittest.TestCase):
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
        self.assertIn("FRAME_CONCEPT_TYPE_AUTHORITY_MISMATCH",
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
