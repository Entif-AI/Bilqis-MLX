"""B06 parent acceptance that is not owned by one refinement child."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.frame_encoder import encode_frames
from bilqis_mlx.learning.tests.frames.nested_fixtures import _case as nested_frame_case
from bilqis_mlx.runtime.atlas_refinement import _refine_frame
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents,
    ModelTopologySpecV2,
    expected_bamf_shapes,
)
from bilqis_mlx.runtime.tests.model.refinement.helpers import _case as refinement_policy_case


class B06ParentAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.spec = ModelTopologySpecV2()
        self.extents = GenerationExtents(
            1, 1, hashlib.sha256(b"[11]").hexdigest(), "b" * 64, "c" * 64)
        rng = np.random.default_rng(365)
        self.parameters = {
            item.name: mx.array(
                rng.normal(0, 0.025, item.shape).astype(np.float32))
            for item in expected_bamf_shapes(self.spec, self.extents)
            if item.name.startswith("refine.")
        }
        self.parameters["refine.norm"] = mx.ones((768,), dtype=mx.float32)
        self.parameters["refine.gate_vector"] = mx.zeros((768,), dtype=mx.float32)
        self.parameters["refine.bias"] = mx.array(
            [math.log(1 / 9)], dtype=mx.float32)
        self.hidden, self.seed, self.role = (
            mx.array(rng.normal(0, 0.1, 768).astype(np.float32))
            for _ in range(3)
        )
        self.members = mx.array(
            rng.normal(0, 0.1, (3, 768)).astype(np.float32))

    def test_two_pass_result_repeats_after_parameter_save_resume(self):
        before = _refine_frame(
            self.hidden, self.seed, self.members, self.role, 2, self.parameters)
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "b06-refinement.safetensors"
            mx.save_safetensors(str(path), self.parameters)
            restored = mx.load(str(path))
            after = _refine_frame(
                self.hidden, self.seed, self.members, self.role, 2, restored)
        self.assertTrue(bool(mx.array_equal(before.hidden, after.hidden)))
        self.assertTrue(bool(mx.array_equal(
            before.route_logits, after.route_logits)))

    def test_zero_local_passes_return_baseline_and_preserve_remaining_needs(self):
        policy = refinement_policy_case()
        selection = policy.select(
            explicit_member_question=False, unresolved_nested_query=False)
        self.assertEqual((selection.eligible_count, selection.quota), (9, 2))
        self.assertEqual(len(selection.remaining_frame_handles), 7)
        self.assertTrue(all(choice.passes == 0 for choice in selection.selected))

        baseline = _refine_frame(
            self.hidden, self.seed, self.members, self.role, 0, self.parameters)
        self.assertIs(baseline.hidden, self.hidden)
        self.assertIsNone(baseline.route_logits)

    def test_one_disposable_update_reduces_literal_nested_child_role_loss(self):
        _ast, _config, compiled, vectors, frame_parameters = nested_frame_case()
        encoded = encode_frames(compiled, vectors, frame_parameters)
        row = compiled.compiled.rows[1]
        child_index = next(
            index for index, position in enumerate(row.positions)
            if position.frame_handle == "frame:mixed:0")
        parent_index = next(
            index for index, position in enumerate(row.positions)
            if position.frame_handle == "frame:mixed:2")

        child_hidden = encoded.global_seeds[1, child_index]
        parent_hidden = encoded.global_seeds[1, parent_index]
        members = mx.stack((
            child_hidden,
            vectors.members[1][0].vector,
        ))
        child_role = (
            frame_parameters["features.project_role"]
            @ frame_parameters["features.role"][3]
        )

        def loss(parameters):
            refined = _refine_frame(
                parent_hidden, parent_hidden, members, child_role, 2, parameters)
            return mx.mean((refined.hidden - child_hidden) ** 2)

        before = loss(self.parameters)
        gradients = mx.grad(loss)(self.parameters)
        updated = {
            name: value - mx.array(0.01, dtype=mx.float32) * gradients[name]
            for name, value in self.parameters.items()
        }
        after = loss(updated)
        mx.eval(before, after, updated)
        self.assertTrue(bool(mx.isfinite(before)))
        self.assertTrue(bool(mx.isfinite(after)))
        self.assertLess(float(after), float(before))


if __name__ == "__main__":
    unittest.main()
