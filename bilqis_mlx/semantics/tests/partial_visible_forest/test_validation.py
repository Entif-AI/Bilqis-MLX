"""Partial forest validation witnesses."""
from __future__ import annotations
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from bilqis_mlx.semantics import frame_compiler
from bilqis_mlx.semantics import partial_visible_forest as public_forest
from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.semantics.frame_schema import FrameTree
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import RELEASE, _mixed_case
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.frame_schema import SourceSpan


class ValidationTests(TestCase):
    def test_public_reconstruct_hook_remains_late_bound(self):
        ast, config = _mixed_case()
        compiled = compile_prefix(ast, 4, RELEASE, config)
        with patch.object(
                public_forest, "reconstruct",
                side_effect=RuntimeError("public reconstruct injected")):
            with self.assertRaisesRegex(
                    RuntimeError, "public reconstruct injected"):
                frame_compiler.validate_partial_visible_forest(
                    compiled, ast, config)

    def test_public_compile_hook_remains_late_bound(self):
        ast, config = _mixed_case()
        compiled = compile_prefix(ast, 4, RELEASE, config)
        with patch.object(
                public_forest, "compile_prefix",
                side_effect=RuntimeError("public compile_prefix injected")):
            with self.assertRaisesRegex(
                    RuntimeError, "public compile_prefix injected"):
                frame_compiler.validate_partial_visible_forest(
                    compiled, ast, config)

    def test_partial_visible_forest_excludes_future_and_preserves_full_identities(self):
        ast, config = _mixed_case()
        parent = ast.frames[0].root
        child = ast.frames[0].children[0].root
        before = (
            parent.occurrence_id, parent.content_digest,
            child.occurrence_id, child.content_digest)

        at_three = frame_compiler.validate_partial_visible_forest(
            compile_prefix(ast, 3, RELEASE, config), ast, config)
        self.assertEqual(at_three.visible_forest, ())
        self.assertEqual(at_three.hidden_parents, ())

        at_four = frame_compiler.validate_partial_visible_forest(
            compile_prefix(ast, 4, RELEASE, config), ast, config)
        self.assertEqual(
            tuple(tree.root.occurrence_id for tree in at_four.visible_forest),
            (child.occurrence_id,))
        self.assertFalse(any(
            tree.root.occurrence_id == parent.occurrence_id
            for tree in at_four.visible_forest))

        at_eight = frame_compiler.validate_partial_visible_forest(
            compile_prefix(ast, 8, RELEASE, config), ast, config)
        full_parent = next(
            tree for tree in at_eight.visible_forest
            if tree.root.occurrence_id == parent.occurrence_id)
        after = (
            full_parent.root.occurrence_id, full_parent.root.content_digest,
            full_parent.children[0].root.occurrence_id,
            full_parent.children[0].root.content_digest)
        self.assertEqual(after, before)
        self.assertEqual(at_eight.hidden_parents, ())

    def test_partial_visible_forest_receipt_rejects_source_scope_release_drift(self):
        ast, config = _mixed_case()
        compiled = compile_prefix(ast, 4, RELEASE, config)
        receipt = frame_compiler.validate_partial_visible_forest(
            compiled, ast, config)

        changed_source = replace(ast, source_instance_id="synthetic:other-source")
        with self.assertRaises(BilqisError) as caught:
            frame_compiler.validate_partial_visible_forest(
                compiled, changed_source, config, expected_receipt=receipt)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")

        parent_tree, atomic_tree = ast.frames
        changed_parent = replace(
            parent_tree.root, source_span=SourceSpan(0, 7))
        changed_parent_source = replace(
            ast, frames=(
                FrameTree(changed_parent, parent_tree.children),
                atomic_tree))
        with self.assertRaises(BilqisError) as caught:
            frame_compiler.validate_partial_visible_forest(
                compiled, changed_parent_source, config,
                expected_receipt=receipt)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")

        changed_schemas = tuple(
            replace(schema, scope="forged:hidden-parent-scope")
            if schema.schema_id == parent_tree.root.frame_schema_id
            else schema
            for schema in config.schemas)
        changed_parent_scope = replace(config, schemas=changed_schemas)
        with self.assertRaises(BilqisError) as caught:
            frame_compiler.validate_partial_visible_forest(
                compiled, ast, changed_parent_scope,
                expected_receipt=receipt)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_PARTIAL_RECEIPT_DRIFT")

        changed_scope = replace(
            config, task=replace(config.task, scope="synthetic:other-scope"))
        with self.assertRaises(BilqisError) as caught:
            frame_compiler.validate_partial_visible_forest(
                compiled, ast, changed_scope, expected_receipt=receipt)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")

        other_release = "b" * 64
        changed_release = replace(
            config,
            schema_map=SchemaTagMap.from_schemas(
                other_release, config.schemas),
            task=replace(config.task, semantic_release=other_release))
        with self.assertRaises(BilqisError) as caught:
            frame_compiler.validate_partial_visible_forest(
                compiled, ast, changed_release, expected_receipt=receipt)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")
