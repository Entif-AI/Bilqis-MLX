"""B06.3 public refinement consumes the real source-owned B02/B03 path."""
from __future__ import annotations

import os
from unittest import TestCase, skipUnless

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.source_atoms import SourceAtomRow, encode_source_compiled
from bilqis_mlx.runtime.atlas_refinement import refine_selected
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.runtime.refinement_policy import RefinementChoice
from bilqis_mlx.semantics.frame_compiler import PositionKind, compile_prefix_rows

from bilqis_mlx.runtime.tests.model.refinement.source_fixtures import (
    EACH, SEED, SOURCE_ROOT, source_refinement_case,
)


REAL_BUNDLE = os.environ.get("BILQIS_A01_ATLAS_BUNDLE", "")


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class SourceAuthorityRefinementTests(TestCase):
    def setUp(self):
        case = source_refinement_case()
        self.case = case
        self.extents = GenerationExtents(
            1 + max(entry.bank for entry in case.snapshot.abi_entries),
            1, case.snapshot.active_set_sha256, "b" * 64, case.features.digest)
        rows = compile_prefix_rows(
            ((case.ast, len(case.row["tokens"]), case.config),),
            case.snapshot.release_sha256)
        self.compiled = CompiledEncoderInput(
            rows, (case.config,), case.features, self.extents)
        self.source = SourceAtomRow(
            case.selection, case.row, case.graph, SOURCE_ROOT, SEED, EACH)
        rng = np.random.default_rng(736)
        self.parameters = {
            item.name: mx.array(
                rng.normal(0, .01, item.shape).astype(np.float32))
            for item in expected_bamf_shapes(ModelTopologySpecV2(), self.extents)
        }
        self.parameters["features.norm"] = mx.ones((768,), dtype=mx.float32)
        self.parameters["refine.norm"] = mx.ones((768,), dtype=mx.float32)
        encoded = encode_source_compiled(
            self.compiled, self.parameters, (self.source,), case.schema)
        self.encoded = encoded
        self.index, position = next(
            (index, position)
            for index, position in enumerate(encoded.handles[0])
            if position is not None and position.kind is PositionKind.CLOSURE)
        self.choice = RefinementChoice(
            position.frame_handle, position.packed.sidecar.occurrence_id,
            self.index, 0, 0.0, 1,
            ("source-positive-generation", rows.rows[0].visible_end,
             "source-positive-query", position.packed.sidecar.occurrence_id))
        self.backbone = encoded.global_seeds + mx.array(.03125, dtype=mx.float32)
        self.role = mx.ones((768,), dtype=mx.float32) * .125

    def refine(self, parameters=None):
        parameters = self.parameters if parameters is None else parameters
        refinement = {
            name: value for name, value in parameters.items()
            if name.startswith("refine.")
        }
        return refine_selected(
            self.backbone, self.compiled, parameters,
            (self.source,), self.case.schema, 0, self.choice,
            self.role, refinement)

    def test_real_pinned_source_reaches_public_refinement(self):
        result = self.refine()
        expected = self.encoded.handles[0][self.index]
        self.assertEqual(result.frame_handle, expected.frame_handle)
        self.assertEqual(result.occurrence_id, expected.packed.sidecar.occurrence_id)
        self.assertEqual(
            result.member_handles,
            tuple(request.member_handle for request in
                  self.compiled.member_requests[0]))
        self.assertEqual(result.passes, 1)
        self.assertTrue(bool(mx.all(mx.isfinite(result.hidden))))
        self.assertGreater(
            float(mx.max(mx.abs(result.hidden - self.backbone[0, self.index]))), 0)

    def test_public_refinement_keeps_source_encoding_differentiable(self):
        def objective(parameters):
            return mx.sum(self.refine(parameters).hidden)

        gradients = mx.grad(objective)(self.parameters)
        token_rows = self.source.source_row["tokens"]
        identity_gradient = gradients["identity.bank.0"][mx.array(token_rows)]
        self.assertTrue(bool(mx.all(mx.isfinite(identity_gradient))))
        self.assertGreater(float(mx.sum(mx.abs(identity_gradient))), 0)
        self.assertGreater(
            float(mx.sum(mx.abs(gradients["features.project_type"]))), 0)
        self.assertGreater(
            float(mx.sum(mx.abs(gradients["refine.output"]))), 0)
        self.assertTrue(np.isfinite(float(objective(self.parameters))))


if __name__ == "__main__":
    import unittest
    unittest.main()
