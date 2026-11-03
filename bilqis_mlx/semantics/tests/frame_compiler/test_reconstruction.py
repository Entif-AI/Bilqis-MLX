"""Frame compiler: reconstruction contracts."""
from __future__ import annotations
from dataclasses import replace
from unittest import TestCase
from bilqis_mlx.semantics.frame_codec import PackDisposition
from bilqis_mlx.semantics.frame_compiler import PositionKind, compile_prefix, reconstruct
from bilqis_mlx.semantics.frame_schema import AtomicFrame
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import (
    RELEASE, _mixed_case,
)


class ReconstructionTests(TestCase):
    def test_nested_child_closes_before_parent_and_atomic_round_trips(self):
        ast, config = _mixed_case()
        self.assertEqual(
            compile_prefix(ast, 8, RELEASE, config),
            compile_prefix(
                replace(ast, frames=tuple(reversed(ast.frames))),
                8, RELEASE, config))
        at_four = reconstruct(compile_prefix(ast, 4, RELEASE, config))
        self.assertEqual(len(at_four.frames), 1)
        self.assertEqual(at_four.frames[0].root.frame_schema_id, "frame:child")
        at_six = reconstruct(compile_prefix(ast, 6, RELEASE, config))
        self.assertEqual(len(at_six.frames), 2)
        self.assertTrue(any(isinstance(tree.root, AtomicFrame)
                            for tree in at_six.frames))
        at_eight = compile_prefix(ast, 8, RELEASE, config)
        closures = tuple(
            position for position in at_eight.positions
            if position.kind is PositionKind.CLOSURE)
        self.assertEqual(len(closures), 3)
        self.assertEqual(tuple(
            position.packed.disposition for position in closures), (
                PackDisposition.EXTENDED,
                PackDisposition.ATOMIC,
                PackDisposition.EXTENDED))
        visible = reconstruct(at_eight)
        parent = next(
            tree for tree in visible.frames
            if getattr(tree.root, "frame_schema_id", None) == "frame:parent")
        self.assertEqual(len(parent.children), 1)
        self.assertEqual(
            parent.children[0].root.frame_schema_id, "frame:child")
        self.assertEqual(visible.atoms, ast.atoms)
        self.assertEqual(at_eight.stats.disposition_shares, (
            ("COMPACT", 0, 3), ("EXTENDED", 2, 3),
            ("ATOMIC", 1, 3)))
        self.assertGreater(at_eight.stats.sidecar_bytes, 0)
