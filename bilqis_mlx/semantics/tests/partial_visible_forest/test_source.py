"""Partial forest source witnesses."""
from __future__ import annotations
from dataclasses import replace
from unittest import TestCase
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics import frame_compiler
from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.semantics.frame_schema import FrameTree
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import RELEASE, _mixed_case


class SourceTests(TestCase):
    def test_partial_visible_forest_rejects_forged_orphan_parent(self):
        ast, config = _mixed_case()
        compiled = compile_prefix(ast, 4, RELEASE, config)
        parent_tree, atomic_tree = ast.frames
        child = parent_tree.children[0].root
        forged = replace(child, parent_occurrence_id="f" * 64)
        forged_ast = replace(
            ast, frames=(
                FrameTree(parent_tree.root, (FrameTree(forged),)),
                atomic_tree))

        with self.assertRaises(BilqisError) as caught:
            frame_compiler.validate_partial_visible_forest(
                compiled, forged_ast, config)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_PARTIAL_PARENT_ORPHAN")
