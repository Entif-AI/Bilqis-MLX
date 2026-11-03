"""Reconstruction compiler regressions."""
import unittest
from bilqis_mlx.semantics.tests.frame_compilation.helpers import (BilqisError, FrameTree, RELEASE, SchemaTagMap, SourceSpan, StreamingAST, _mixed_case, compile_prefix, frame_compiler, reconstruct, replace)


class ReconstructionTests(unittest.TestCase):
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
