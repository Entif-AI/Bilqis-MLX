"""Frame-schema ast_identity witnesses."""
from __future__ import annotations

import unittest

from bilqis_mlx.semantics.core import (
    Apply, Operation, Signature, expression_digest, literal,
)
from bilqis_mlx.semantics.frame_schema import (
    AtomicFrame, SourceSpan, ast_construct_id, bind_ast_frames,
    native_ast_content_digest,
)
from bilqis_mlx.semantics.tests.frame_schema.fixtures import _concept, _snapshot


class FrameAstIdentityTests(unittest.TestCase):
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
        self.assertEqual(
            native_ast_content_digest(expression),
            expression_digest(expression),
        )
        changed_operation = Operation(
            operation.token_index,
            operation.symbol,
            operation.signature,
            "b" * 64,
        )
        changed = Apply(
            changed_operation,
            expression.arguments,
            expression.type_name,
            expression.world_contract,
        )
        self.assertNotEqual(
            native_ast_content_digest(expression),
            native_ast_content_digest(changed),
        )


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
