"""B06.3: bind local refinement to exact B03 frame outputs."""
from dataclasses import replace
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_encoder import encode_frames
from bilqis_mlx.learning.tests.frames.nested_fixtures import _case
from bilqis_mlx.learning.tests.test_frame_encoder import FrameEncoderTests
from bilqis_mlx.runtime.atlas_refinement import _refine_frame, refine_selected
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
        actual = refine_selected(
            self.backbone, self.compiled, self.vectors, self.encoder_parameters,
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
            return mx.sum(refine_selected(
                backbone, self.compiled, self.vectors, self.encoder_parameters,
                self.row, self.choice,
                self.role, self.parameters).hidden)
        gradient = mx.grad(objective)(self.backbone)
        self.assertGreater(float(mx.sum(mx.abs(gradient[self.row, self.index]))), 0)
        masked = np.asarray(gradient).copy()
        masked[self.row, self.index] = 0
        self.assertEqual(float(np.abs(masked).sum()), 0.0)

    def test_unrelated_backbone_positions_cannot_change_selected_result(self):
        baseline = refine_selected(
            self.backbone, self.compiled, self.vectors, self.encoder_parameters,
            self.row, self.choice,
            self.role, self.parameters).hidden
        other = 0 if self.index != 0 else 1
        changed = self.backbone.at[self.row, other].add(
            mx.ones((768,), dtype=mx.float32) * 100)
        actual = refine_selected(
            changed, self.compiled, self.vectors, self.encoder_parameters,
            self.row, self.choice,
            self.role, self.parameters).hidden
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(baseline))

    def test_zero_pass_returns_the_exact_selected_backbone_value(self):
        choice = replace(self.choice, passes=0)
        actual = refine_selected(
            self.backbone, self.compiled, self.vectors, self.encoder_parameters,
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
                refine_selected(
                    self.backbone, self.compiled, self.vectors, self.encoder_parameters,
                    self.row, choice,
                    self.role, self.parameters)
        with self.assertRaises(BilqisError):
            refine_selected(
                self.backbone.astype(mx.float16), self.compiled, self.vectors,
                self.encoder_parameters, self.row,
                self.choice, self.role, self.parameters)
        with self.assertRaises(BilqisError):
            refine_selected(
                self.backbone, self.compiled, self.vectors, self.encoder_parameters,
                True, self.choice,
                self.role, self.parameters)
        with self.assertRaises(BilqisError):
            refine_selected(
                self.backbone, self.compiled, object(), self.encoder_parameters,
                self.row, self.choice,
                self.role, self.parameters)

    def test_replaced_frame_encoding_is_not_an_accepted_execution_boundary(self):
        changed = tuple(
            tuple(member + mx.array(50, dtype=mx.float32) for member in row)
            for row in self.encoding.members)
        forged = replace(self.encoding, members=changed)
        with self.assertRaises(BilqisError):
            refine_selected(
                self.backbone, self.compiled, forged, self.encoder_parameters,
                self.row, self.choice, self.role, self.parameters)

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
        first = refine_selected(
            backbone, compiled, duplicated_vectors, fixture.params,
            0, choice, self.role, parameters)
        second = refine_selected(
            backbone, compiled, duplicated_vectors, fixture.params,
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
        actual = refine_selected(
            self.backbone, self.compiled, self.vectors, self.encoder_parameters,
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
        actual = refine_selected(
            backbone, compiled, vectors, fixture.params, 0, zero,
            self.role, parameters)
        self.assertEqual(actual.member_handles, ())
        np.testing.assert_array_equal(
            np.asarray(actual.hidden), np.asarray(backbone[0, index]))
        with self.assertRaises(BilqisError):
            refine_selected(
                backbone, compiled, vectors, fixture.params, 0,
                replace(zero, passes=1),
                self.role, parameters)


if __name__ == "__main__":
    unittest.main()
