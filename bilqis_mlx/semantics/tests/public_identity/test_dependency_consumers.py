"""Literal public consumers re-enter their original facade dependency hooks."""
import os
import unittest
from unittest.mock import patch

from bilqis_mlx.semantics import (
    frame_compiler as compiler, frame_schema as schema,
    partial_visible_forest as forest, released_frame_schemas as released,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import RELEASE, _mixed_case


class ConsumerDependencyTests(unittest.TestCase):
    def test_compiler_reenters_public_context_approval_with_original_arguments(self):
        ast, config = _mixed_case()
        original = compiler.project_context
        with patch.object(compiler, "project_context", wraps=original) as approved:
            result = compiler.compile_prefix(ast, 4, RELEASE, config)
        self.assertEqual(result.visible_end, 4)
        approved.assert_called_once()
        envelopes, task, frontier, policy = approved.call_args.args
        self.assertEqual(len(envelopes), 1)
        self.assertEqual(task.causal_prefix_end, 4)
        self.assertIs(frontier, config.frontier)
        self.assertIs(policy, config.policy)

    def test_partial_forest_reenters_public_reconstruction_then_compiler(self):
        ast, config = _mixed_case()
        compiled = compiler.compile_prefix(ast, 4, RELEASE, config)
        order = []
        reconstruct, compile_prefix = forest.reconstruct, forest.compile_prefix

        def reconstruct_hook(value):
            order.append("reconstruct")
            self.assertIs(value, compiled)
            return reconstruct(value)

        def compile_hook(*args, **kwargs):
            order.append("compile")
            return compile_prefix(*args, **kwargs)

        with (patch.object(forest, "reconstruct", side_effect=reconstruct_hook),
              patch.object(forest, "compile_prefix", side_effect=compile_hook)):
            result = forest.validate_partial_visible_forest(compiled, ast, config)
        self.assertEqual(order, ["reconstruct", "compile"])
        self.assertEqual(result.source_instance_id, ast.source_instance_id)

    def test_frame_constructor_reenters_public_identity_helper_without_identity_change(self):
        ast, config = _mixed_case()
        before = ast.frames[0].children[0].root
        frame_schema = next(item for item in config.schemas
                            if item.schema_id == before.frame_schema_id)
        with patch.object(schema, "occurrence_id", wraps=schema.occurrence_id) as identity:
            after = schema.make_frame_instance(
                frame_schema, source_instance_id=before.source_instance_id,
                structural_path=before.structural_path, source_span=before.source_span,
                parent_occurrence_id=before.parent_occurrence_id, bindings=before.bindings,
                causal_prefix_end=before.causal_prefix_end)
        identity.assert_called_once_with(before.source_instance_id, before.structural_path)
        self.assertEqual(after, before)
        self.assertIs(type(after), schema.FrameInstance)
        self.assertEqual(after.canonical_bytes(), before.canonical_bytes())

    @unittest.skipUnless(os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
                         "repo-pinned A01 source artifact required")
    def test_real_released_lookup_reenters_public_atlas_then_release_loader(self):
        selection = AtlasArtifactSelection(
            os.environ["BILQIS_ATLAS_REAL_ARTIFACT"],
            "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7",
            "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306",
            "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec")
        staged = released._load_pinned_released_frame_schemas("micro", selection)
        body = staged.manifest.bodies[0]
        order = []
        atlas, load = released.load_pinned_atlas_snapshot, released.load_released_frame_schemas

        def atlas_hook(value):
            order.append("atlas")
            self.assertIs(value, selection)
            return atlas(value)

        def load_hook(*args, **kwargs):
            order.append("release")
            return load(*args, **kwargs)

        with (patch.object(released, "load_pinned_atlas_snapshot", side_effect=atlas_hook),
              patch.object(released, "load_released_frame_schemas", side_effect=load_hook)):
            actual, witness = released.lookup_source_pinned_frame_schema(
                body.schema_id, body.revision, source_family="micro",
                atlas_selection=selection)
        self.assertEqual(order, ["atlas", "release"])
        self.assertEqual(actual, body.parse())
        self.assertEqual(witness.schema_body_sha256, body.schema_body_sha256)
