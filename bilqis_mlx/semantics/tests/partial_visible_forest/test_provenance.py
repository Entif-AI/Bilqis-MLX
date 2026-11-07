"""Partial forest provenance witnesses."""
from __future__ import annotations
from unittest import TestCase
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics import frame_compiler
from bilqis_mlx.semantics.frame_compiler import (
    StreamingAST, compile_prefix, reconstruct,
)
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import RELEASE, _mixed_case


class ProvenanceTests(TestCase):
    def test_partial_visible_forest_preserves_hidden_parent_provenance(self):
        ast, config = _mixed_case()
        parent = ast.frames[0].root
        child = ast.frames[0].children[0].root
        compiled = compile_prefix(ast, 4, RELEASE, config)

        visible = reconstruct(compiled)
        temporary = StreamingAST(
            visible.source_instance_id, visible.atoms, visible.frames)
        with self.assertRaises(BilqisError) as caught:
            compile_prefix(temporary, 4, RELEASE, config)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_ROOT_PARENT_INVALID")

        receipt = frame_compiler.validate_partial_visible_forest(
            compiled, ast, config)

        self.assertEqual(receipt.compiler_cache_key, compiled.cache_key)
        self.assertEqual(receipt.visible_end, 4)
        self.assertEqual(len(receipt.visible_forest), 1)
        self.assertEqual(receipt.visible_forest[0].root, child)
        self.assertEqual(
            receipt.visible_forest[0].root.parent_occurrence_id,
            parent.occurrence_id)
        self.assertEqual(len(receipt.hidden_parents), 1)
        self.assertEqual(
            receipt.hidden_parents[0].child_occurrence_id,
            child.occurrence_id)
        self.assertEqual(
            receipt.hidden_parents[0].parent_occurrence_id,
            parent.occurrence_id)
        self.assertNotIn(parent, tuple(tree.root for tree in receipt.visible_forest))
