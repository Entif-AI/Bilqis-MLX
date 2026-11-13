"""Frame-schema forest witnesses."""
from __future__ import annotations

import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.core import Apply, Operation, Signature, literal
from bilqis_mlx.semantics.frame_schema import (
    ChildFrameRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    bind_ast_frames, bind_frame_instance, frame_instance_from_bytes,
)
from bilqis_mlx.semantics.tests.frame_schema.fixtures import _concept, _snapshot


class FrameForestTests(unittest.TestCase):
    def test_native_apply_requires_exact_released_semantic_contract_digest(self):
        expected_contract = "a" * 64
        operation = Operation(
            17,
            "formal.operator.TRANSFER",
            Signature(("Entity",), "Entity"),
            expected_contract,
        )
        forged = Operation(
            operation.token_index,
            operation.symbol,
            operation.signature,
            "b" * 64,
        )
        entity = _concept("alice", 0)
        snapshot = _snapshot(entity)
        schema = FrameSchema(
            schema_id="formal.frame.CONTRACT",
            revision=1,
            ast_construct="apply:formal.operator.TRANSFER",
            roles=(RoleSpec("operand", ("Entity",), 1, 1),),
            order_mode="ORDERED",
            scope="formal-expression",
            ast_contract_sha256=expected_contract,
        )
        expression = Apply(
            forged,
            (literal("alice", "Entity"),),
            "Entity",
            None,
        )
        with self.assertRaises(BilqisError) as caught:
            bind_ast_frames(
                expression,
                snapshot,
                schema=schema,
                source_instance_id="contract-probe",
                source_span=SourceSpan(0, 5),
                bindings=(RoleOccurrence("operand", 0, concept=entity),),
                causal_prefix_end=5,
                declared_scope="formal-expression",
            )
        self.assertEqual(caught.exception.code, "SEMANTIC_FRAME.BINDING.INVALID")
        self.assertEqual(
            caught.exception.context["reason"],
            "FRAME_AST_CONTRACT_MISMATCH",
        )


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
