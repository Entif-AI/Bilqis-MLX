"""B06.3: bind local refinement to exact B03 frame outputs."""
from dataclasses import replace
import inspect
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_encoder import CompiledEmbeddingVectors, encode_frames
from bilqis_mlx.learning.tests.frames.nested_fixtures import _case
from bilqis_mlx.learning.tests.test_frame_encoder import FrameEncoderTests
from bilqis_mlx.runtime.atlas_refinement import _refine_frame, _refine_selected, refine_selected
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2, expected_bamf_shapes
from bilqis_mlx.runtime.refinement_policy import RefinementChoice
from bilqis_mlx.semantics.frame_compiler import PositionKind


class RefinementExecutionTests(unittest.TestCase):
    def setUp(self):
        _, _, compiled, vectors, encoder_parameters = _case()
        self.compiled = compiled
        self.vectors = vectors
        self.encoder_parameters = encoder_parameters
        self.encoding = encode_frames(compiled, vectors, encoder_parameters)
        self.row = 1
        self.index = next(
            index for index, position in enumerate(self.encoding.handles[self.row])
            if position is not None and position.kind is PositionKind.CLOSURE
            and position.frame_handle == "frame:mixed:2")
        position = self.encoding.handles[self.row][self.index]
        self.choice = RefinementChoice(
            position.frame_handle, position.packed.sidecar.occurrence_id,
            self.index, 1, 0.0, 2,
            ("generation", 8, "query", position.packed.sidecar.occurrence_id))
        rng = np.random.default_rng(454)
        self.parameters = {
            item.name: mx.array(rng.normal(0, .025, item.shape).astype(np.float32))
            for item in expected_bamf_shapes(ModelTopologySpecV2(), compiled.extents)
            if item.name.startswith("refine.")
        }
        self.parameters["refine.norm"] = mx.ones((768,), dtype=mx.float32)
        self.parameters["refine.gate_vector"] = mx.zeros((768,), dtype=mx.float32)
        self.backbone = self.encoding.global_seeds + mx.array(.03125, dtype=mx.float32)
        self.role = mx.array(rng.normal(0, .1, 768).astype(np.float32))

    def test_exact_b03_frame_inputs_drive_the_existing_numerical_kernel(self):
        before_backbone = np.asarray(self.backbone).copy()
        before_seed = np.asarray(self.encoding.global_seeds).copy()
        before_members = np.asarray(self.encoding.members[self.row][self.index]).copy()
        actual = _refine_selected(
            self.backbone, self.compiled, self.encoding,
            self.row, self.choice,
            self.role, self.parameters)
        expected = _refine_frame(
            self.backbone[self.row, self.index],
            self.encoding.global_seeds[self.row, self.index],
            self.encoding.members[self.row][self.index],
            self.role, self.choice.passes, self.parameters)
        factor = self.encoding.features[self.row][self.index]
        self.assertEqual(actual.frame_handle, self.choice.frame_handle)
        self.assertEqual(actual.occurrence_id, self.choice.occurrence_id)
        self.assertEqual(
            actual.refinement_key,
            (self.choice.cache_identity, self.row,
             self.compiled.compiled.rows[self.row].cache_key))
        self.assertEqual(actual.member_handles,
                         tuple(item.member_handle for item in factor.requests))
        self.assertEqual(actual.passes, self.choice.passes)
        np.testing.assert_array_equal(np.asarray(actual.hidden), np.asarray(expected.hidden))
        np.testing.assert_array_equal(np.asarray(actual.route_logits),
                                      np.asarray(expected.route_logits))
        np.testing.assert_array_equal(np.asarray(self.backbone), before_backbone)
        np.testing.assert_array_equal(np.asarray(self.encoding.global_seeds), before_seed)
        np.testing.assert_array_equal(
            np.asarray(self.encoding.members[self.row][self.index]), before_members)

    def test_backbone_gradient_is_prediction_local_to_the_exact_frame_position(self):
        def objective(backbone):
            return mx.sum(_refine_selected(
                backbone, self.compiled, self.encoding,
                self.row, self.choice,
                self.role, self.parameters).hidden)
        gradient = mx.grad(objective)(self.backbone)
        self.assertGreater(float(mx.sum(mx.abs(gradient[self.row, self.index]))), 0)
        masked = np.asarray(gradient).copy()
        masked[self.row, self.index] = 0
        self.assertEqual(float(np.abs(masked).sum()), 0.0)

    def test_numerical_b03_encoding_preserves_encoder_gradient_flow(self):
        def objective(frame_parameters):
            encoding = encode_frames(self.compiled, self.vectors, frame_parameters)
            backbone = encoding.global_seeds + mx.array(.03125, dtype=mx.float32)
            return mx.sum(_refine_selected(
                backbone, self.compiled, encoding,
                self.row, self.choice, self.role, self.parameters).hidden)

        gradients = mx.grad(objective)(self.encoder_parameters)
        self.assertTrue(all(bool(mx.all(mx.isfinite(value)))
                            for value in gradients.values()))
        self.assertGreater(
            float(mx.sum(mx.abs(gradients["frame.project_output"]))), 0)

    def test_public_refinement_has_no_caller_vector_or_encoding_authority(self):
        parameters = inspect.signature(refine_selected).parameters
        self.assertNotIn("vectors", parameters)
        self.assertNotIn("encoding", parameters)
        self.assertEqual(
            tuple(parameters),
            ("backbone_hidden", "compiled", "frame_parameters", "sources",
             "feature_schema", "row_index", "choice", "query_role", "parameters"))

        with self.assertRaises((BilqisError, AttributeError, TypeError, ValueError)):
            refine_selected(
                self.backbone, self.compiled, self.encoder_parameters,
                (object(),), object(), self.row, self.choice,
                self.role, self.parameters)

    def test_exact_forged_vector_adversary_cannot_enter_public_refinement(self):
        forged_vectors = CompiledEmbeddingVectors(
            self.vectors.atoms,
            tuple(
                tuple(replace(item, vector=item.vector + mx.array(50, dtype=mx.float32))
                      for item in row)
                for row in self.vectors.members),
            self.vectors.atomic_frames)
        forged_encoding = encode_frames(
            self.compiled, forged_vectors, self.encoder_parameters)

        with self.assertRaises(TypeError):
            refine_selected(
                self.backbone, self.compiled, forged_encoding,
                self.row, self.choice, self.role, self.parameters)

    def test_unrelated_backbone_positions_cannot_change_selected_result(self):
        baseline = _refine_selected(
            self.backbone, self.compiled, self.encoding,
            self.row, self.choice,
            self.role, self.parameters).hidden
        other = 0 if self.index != 0 else 1
        changed = self.backbone.at[self.row, other].add(
            mx.ones((768,), dtype=mx.float32) * 100)
        actual = _refine_selected(
            changed, self.compiled, self.encoding,
            self.row, self.choice,
            self.role, self.parameters).hidden
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(baseline))

    def test_zero_pass_returns_the_exact_selected_backbone_value(self):
        choice = replace(self.choice, passes=0)
        actual = _refine_selected(
            self.backbone, self.compiled, self.encoding,
            self.row, choice,
            self.role, self.parameters)
        np.testing.assert_array_equal(
            np.asarray(actual.hidden),
            np.asarray(self.backbone[self.row, self.index]))
        self.assertIsNone(actual.route_logits)
        self.assertEqual(actual.passes, 0)

    def test_choice_and_encoding_identity_must_match_exact_b03_output(self):
        for choice in (
            replace(self.choice, frame_handle="frame:invented"),
            replace(self.choice, occurrence_id="f" * 64),
            replace(self.choice, cache_identity=("generation", 8, "query", "f" * 64)),
            replace(self.choice, cache_identity=("generation", 7, "query", self.choice.occurrence_id)),
        ):
            with self.subTest(choice=choice), self.assertRaises(BilqisError):
                _refine_selected(
                    self.backbone, self.compiled, self.encoding,
                    self.row, choice,
                    self.role, self.parameters)
        with self.assertRaises(BilqisError):
            _refine_selected(
                self.backbone.astype(mx.float16), self.compiled, self.encoding, self.row,
                self.choice, self.role, self.parameters)
        with self.assertRaises(BilqisError):
            _refine_selected(
                self.backbone, self.compiled, self.encoding,
                True, self.choice,
                self.role, self.parameters)
        with self.assertRaises(BilqisError):
            _refine_selected(
                self.backbone, self.compiled, object(),
                self.row, self.choice,
                self.role, self.parameters)

    def test_same_prediction_key_cannot_alias_two_batch_rows(self):
        fixture = FrameEncoderTests()
        fixture.setUp()
        single, vectors, _ = fixture.compiled_inputs()
        row = single.compiled.rows[0]
        padded = single.compiled.padded_positions[0]
        mask = single.compiled.padding_mask[0]
        rows = replace(
            single.compiled, rows=(row, row),
            padded_positions=(padded, padded), padding_mask=(mask, mask))
        compiled = type(single)(
            rows, (single.compiler_configs[0], single.compiler_configs[0]),
            single.features, single.extents)
        duplicated_vectors = type(vectors)(
            (vectors.atoms[0], vectors.atoms[0]),
            (vectors.members[0], vectors.members[0]))
        encoding = encode_frames(compiled, duplicated_vectors, fixture.params)
        index = next(
            index for index, position in enumerate(encoding.handles[0])
            if position is not None and position.kind is PositionKind.CLOSURE)
        position = encoding.handles[0][index]
        choice = RefinementChoice(
            position.frame_handle, position.packed.sidecar.occurrence_id,
            index, 0, 0.0, 1,
            ("generation-A", 8, "query-A", position.packed.sidecar.occurrence_id))
        rng = np.random.default_rng(456)
        parameters = {
            item.name: mx.array(rng.normal(0, .025, item.shape).astype(np.float32))
            for item in expected_bamf_shapes(ModelTopologySpecV2(), compiled.extents)
            if item.name.startswith("refine.")
        }
        parameters["refine.norm"] = mx.ones((768,), dtype=mx.float32)
        parameters["refine.gate_vector"] = mx.zeros((768,), dtype=mx.float32)
        backbone = encoding.global_seeds.at[1].add(
            mx.ones_like(encoding.global_seeds[1]) * 8)
        first = _refine_selected(
            backbone, compiled, encoding,
            0, choice, self.role, parameters)
        second = _refine_selected(
            backbone, compiled, encoding,
            1, choice, self.role, parameters)
        self.assertEqual(first.refinement_key[0], second.refinement_key[0])
        self.assertNotEqual(first.refinement_key, second.refinement_key)
        self.assertEqual(first.refinement_key[1:], (0, row.cache_key))
        self.assertEqual(second.refinement_key[1:], (1, row.cache_key))
        self.assertGreater(float(mx.max(mx.abs(first.hidden - second.hidden))), 1)

    def test_atomic_closure_uses_its_exact_b03_source_handle(self):
        index = next(
            index for index, position in enumerate(self.encoding.handles[self.row])
            if position is not None and position.kind is PositionKind.CLOSURE
            and position.frame_handle == "frame:mixed:1")
        position = self.encoding.handles[self.row][index]
        choice = RefinementChoice(
            position.frame_handle, position.packed.sidecar.occurrence_id,
            index, 0, 0.0, 1,
            ("generation", 8, "atomic", position.packed.sidecar.occurrence_id))
        actual = _refine_selected(
            self.backbone, self.compiled, self.encoding,
            self.row, choice,
            self.role, self.parameters)
        self.assertEqual(actual.member_handles, ("source:member:mixed:1:0",))
        self.assertGreater(float(mx.sum(mx.abs(
            actual.hidden - self.backbone[self.row, index]))), 0)

    def test_empty_structural_closure_zero_pass_is_identity_positive_pass_rejects(self):
        fixture = FrameEncoderTests()
        fixture.setUp()
        compiled, vectors, _ = fixture.empty_inputs()
        encoding = encode_frames(compiled, vectors, fixture.params)
        index = next(
            index for index, position in enumerate(encoding.handles[0])
            if position is not None and position.kind is PositionKind.CLOSURE)
        position = encoding.handles[0][index]
        rng = np.random.default_rng(455)
        parameters = {
            item.name: mx.array(rng.normal(0, .025, item.shape).astype(np.float32))
            for item in expected_bamf_shapes(ModelTopologySpecV2(), compiled.extents)
            if item.name.startswith("refine.")
        }
        parameters["refine.norm"] = mx.ones((768,), dtype=mx.float32)
        parameters["refine.gate_vector"] = mx.zeros((768,), dtype=mx.float32)
        backbone = encoding.global_seeds + mx.array(.0625, dtype=mx.float32)
        cache = ("generation", 8, "empty", position.packed.sidecar.occurrence_id)
        zero = RefinementChoice(position.frame_handle, position.packed.sidecar.occurrence_id,
                                index, 0, 0.0, 0, cache)
        actual = _refine_selected(
            backbone, compiled, encoding, 0, zero,
            self.role, parameters)
        self.assertEqual(actual.member_handles, ())
        np.testing.assert_array_equal(
            np.asarray(actual.hidden), np.asarray(backbone[0, index]))
        with self.assertRaises(BilqisError):
            _refine_selected(
                backbone, compiled, encoding, 0,
                replace(zero, passes=1),
                self.role, parameters)


if __name__ == "__main__":
    unittest.main()
