"""Frame-schema roles witnesses."""
from __future__ import annotations

import unittest

from bilqis_mlx.semantics.frame_schema import (
    BindingState, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    bind_ast_frames, frame_instance_from_bytes,
)
from bilqis_mlx.semantics.tests.frame_schema.fixtures import _concept, _snapshot


class FrameRolesTests(unittest.TestCase):
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
