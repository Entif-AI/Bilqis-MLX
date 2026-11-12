"""B11.3 mixed-frame execution and complete B01 tensor ownership witnesses."""
import unittest

import mlx.core as mx

from bilqis_mlx.learning.frame_embeddings import embedding_parameter_view
from bilqis_mlx.learning.frame_encoder import frame_encoder_parameter_view
from bilqis_mlx.learning.tests.frames.nested_fixtures import _case
from bilqis_mlx.runtime.atlas_refinement import refinement_parameter_view
from bilqis_mlx.runtime.backbone_group_numerical import run_backbone_group_numerical
from bilqis_mlx.runtime.backbone_source_bridge import compute_compiled_h0
from bilqis_mlx.runtime.block_attnres import depth_parameter_view
from bilqis_mlx.runtime.model_topology_v2 import (
    ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.runtime.topology_v2.construction import create_unbound_bamf_state
from bilqis_mlx.semantics.frame_codec import PackDisposition
from bilqis_mlx.semantics.frame_compiler import PositionKind


class AtlasModelMixedFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ast, _, compiled, vectors, _ = _case()
        cls.ast = ast
        cls.compiled = compiled
        cls.vectors = vectors
        cls.spec = ModelTopologySpecV2()
        cls.parameters, optimizer, cls.manifest = create_unbound_bamf_state(
            cls.spec, compiled.extents, run_seed=473)
        del optimizer

    @classmethod
    def _group_parameters(cls, group_index):
        start = (group_index - 1) * 4
        prefixes = tuple(
            f"blocks.{layer}." for layer in range(start, start + 4))
        return {
            name: value for name, value in cls.parameters.items()
            if name.startswith(prefixes)
        }

    @classmethod
    def _stack(cls, hidden):
        valid = mx.array([
            [position is not None for position in row]
            for row in cls.compiled.compiled.padded_positions
        ], dtype=mx.bool_)
        scope = mx.zeros(valid.shape, dtype=mx.int32)
        current = hidden
        for group_index in (1, 2, 3):
            current = run_backbone_group_numerical(
                current, cls._group_parameters(group_index),
                group_index=group_index, spec=cls.spec,
                extents=cls.compiled.extents, scope_ids=scope, valid=valid,
                generation="4" * 64, prefix_digest="5" * 64).hidden
        return current

    def test_constructor_and_views_use_only_the_expanded_b01_parameter_specs(self):
        declared = expected_bamf_shapes(self.spec, self.compiled.extents)
        names = tuple(item.name for item in declared)
        self.assertEqual(tuple(self.parameters), names)
        self.assertEqual(
            tuple(item["name"] for item in self.manifest["parameters"]), names)
        self.assertEqual(
            {name.split(".")[0] for name in names},
            {"identity", "features", "frame", "blocks", "depth", "motif",
             "plastic", "refine", "readout"})

        frame = frame_encoder_parameter_view(
            self.parameters, spec=self.spec, extents=self.compiled.extents)
        embedding = embedding_parameter_view(
            self.parameters, spec=self.spec, extents=self.compiled.extents)
        depth = depth_parameter_view(
            self.parameters, spec=self.spec, extents=self.compiled.extents,
            boundary_group=1)
        refinement = refinement_parameter_view(
            self.parameters, spec=self.spec, extents=self.compiled.extents)
        self.assertTrue(all(
            name.startswith(("frame.", "features."))
            and value is self.parameters[name]
            for name, value in frame.items()))
        self.assertTrue(all(
            name.startswith(("identity.bank.", "features."))
            and value is self.parameters[name]
            for name, value in embedding.items()))
        self.assertIs(frame["features.type"], embedding["features.type"])
        self.assertIs(depth["norm"], self.parameters["depth.norm"])
        self.assertIs(refinement["refine.norm"], self.parameters["refine.norm"])

    def test_mixed_atomic_packed_nested_batch_runs_12_layer_forward_and_backward(self):
        row = self.compiled.compiled.rows[1]
        closures = tuple(
            (index, position) for index, position in enumerate(row.positions)
            if position.kind is PositionKind.CLOSURE)
        dispositions = tuple(position.packed.disposition for _, position in closures)
        self.assertEqual(
            dispositions,
            (PackDisposition.EXTENDED, PackDisposition.ATOMIC,
             PackDisposition.EXTENDED))
        child, _atomic, parent = (position.packed.sidecar for _, position in closures)
        self.assertEqual(child.parent_occurrence_id, parent.occurrence_id)

        h0 = compute_compiled_h0(
            self.compiled, self.vectors, self.parameters,
            spec=self.spec, extents=self.compiled.extents).hidden
        final = self._stack(h0)
        self.assertEqual(final.shape, h0.shape)
        self.assertTrue(bool(mx.all(mx.isfinite(final))))

        weights = mx.arange(self.spec.width, dtype=mx.float32)
        gradient = mx.grad(
            lambda hidden: mx.sum(self._stack(hidden) * weights))(h0)
        mx.eval(gradient)
        self.assertTrue(bool(mx.all(mx.isfinite(gradient))))
        self.assertGreater(float(mx.sum(mx.abs(gradient))), 0)
        for index, _position in closures:
            self.assertGreater(float(mx.sum(mx.abs(gradient[1, index]))), 0)

        name = "blocks.0.query"
        def parameter_loss(value):
            current = h0
            valid = mx.array([
                [position is not None for position in padded]
                for padded in self.compiled.compiled.padded_positions
            ], dtype=mx.bool_)
            scope = mx.zeros(valid.shape, dtype=mx.int32)
            for group_index in (1, 2, 3):
                parameters = self._group_parameters(group_index)
                if group_index == 1:
                    parameters[name] = value
                current = run_backbone_group_numerical(
                    current, parameters, group_index=group_index,
                    spec=self.spec, extents=self.compiled.extents,
                    scope_ids=scope, valid=valid, generation="4" * 64,
                    prefix_digest="5" * 64).hidden
            return mx.sum(current * weights)
        parameter_gradient = mx.grad(parameter_loss)(self.parameters[name])
        mx.eval(parameter_gradient)
        self.assertTrue(bool(mx.all(mx.isfinite(parameter_gradient))))
        self.assertGreater(float(mx.sum(mx.abs(parameter_gradient))), 0)


if __name__ == "__main__":
    unittest.main()
