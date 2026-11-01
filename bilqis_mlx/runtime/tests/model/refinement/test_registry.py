"""B06.4: refinement parameters are an exact immutable B01 ledger projection."""
import unittest
from dataclasses import replace

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_refinement import (
    RefinementParameterView, _refine_frame, refinement_parameter_view,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, create_unbound_bamf_state,
    expected_bamf_shapes, initialize_bamf_parameter,
)


class RefinementRegistryTests(unittest.TestCase):
    def setUp(self):
        self.spec = ModelTopologySpecV2()
        self.extents = GenerationExtents(1, 1, "1" * 64, "2" * 64, "3" * 64)
        self.full, _, _ = create_unbound_bamf_state(
            self.spec, self.extents, run_seed=455)

    def test_view_is_exact_ordered_alias_projection_of_b01_ledger(self):
        view = refinement_parameter_view(
            self.full, spec=self.spec, extents=self.extents)
        declared = tuple(item for item in expected_bamf_shapes(self.spec, self.extents)
                         if item.name.startswith("refine."))
        self.assertIsInstance(view, RefinementParameterView)
        self.assertEqual(view.declarations, declared)
        self.assertEqual(tuple(view), tuple(item.name for item in declared))
        self.assertEqual(view.topology_digest, self.spec.digest)
        self.assertEqual(view.extents_digest, self.extents.digest)
        for item in declared:
            self.assertIs(view[item.name], self.full[item.name])

    def test_projection_mapping_is_immutable(self):
        view = refinement_parameter_view(
            self.full, spec=self.spec, extents=self.extents)
        with self.assertRaises(TypeError):
            view._parameters["refine.norm"] = mx.zeros((768,), dtype=mx.float32)
        with self.assertRaises(TypeError):
            view["refine.norm"] = mx.zeros((768,), dtype=mx.float32)

    def test_view_identity_metadata_is_canonical(self):
        view = refinement_parameter_view(
            self.full, spec=self.spec, extents=self.extents)
        for changes in (
            {"topology_digest": "x" * 64},
            {"extents_digest": "0" * 63},
            {"schema_version": "bilqis.mlx.refinement-parameter-view/v0"},
        ):
            with self.subTest(changes=changes), self.assertRaises(BilqisError):
                replace(view, **changes)

    def test_b01_constructor_matches_every_refinement_parameter_spec(self):
        run_seed = 455
        full, _, manifest = create_unbound_bamf_state(
            self.spec, self.extents, run_seed=run_seed)
        view = refinement_parameter_view(full, spec=self.spec, extents=self.extents)
        manifest_by_name = {item["name"]: item for item in manifest["parameters"]}
        self.assertEqual(set(manifest_by_name), set(full))
        for item in view.declarations:
            expected = initialize_bamf_parameter(item, run_seed=run_seed)
            np.testing.assert_array_equal(np.asarray(view[item.name]), expected)
            self.assertEqual(manifest_by_name[item.name]["shape"], list(item.shape))
            self.assertEqual(manifest_by_name[item.name]["initializer"], item.initializer.value)
            self.assertEqual(manifest_by_name[item.name]["group"], item.group.value)
            self.assertEqual(manifest_by_name[item.name]["decay"], item.decay)

    def test_generation_extents_are_bound_without_redefining_refine_geometry(self):
        changed = GenerationExtents(2, 2, "4" * 64, "5" * 64, "6" * 64)
        full, _, _ = create_unbound_bamf_state(self.spec, changed, run_seed=455)
        first = refinement_parameter_view(
            self.full, spec=self.spec, extents=self.extents)
        second = refinement_parameter_view(full, spec=self.spec, extents=changed)
        self.assertEqual(first.declarations, second.declarations)
        self.assertNotEqual(first.extents_digest, second.extents_digest)
        self.assertEqual(first.topology_digest, second.topology_digest)

    def test_numerical_kernel_consumes_the_registry_view_without_rekeying(self):
        view = refinement_parameter_view(
            self.full, spec=self.spec, extents=self.extents)
        hidden = mx.arange(768, dtype=mx.float32) / 768
        seed = mx.zeros((768,), dtype=mx.float32)
        members = mx.stack((hidden, hidden + mx.array(.25, dtype=mx.float32)))
        role = mx.ones((768,), dtype=mx.float32) * mx.array(.125, dtype=mx.float32)
        direct = {name: self.full[name] for name in view}
        expected = _refine_frame(hidden, seed, members, role, 2, direct)
        actual = _refine_frame(hidden, seed, members, role, 2, view)
        np.testing.assert_array_equal(np.asarray(actual.hidden), np.asarray(expected.hidden))
        np.testing.assert_array_equal(
            np.asarray(actual.route_logits), np.asarray(expected.route_logits))

    def test_full_tree_drift_rejects_before_projection(self):
        extra = {**self.full, "refine.shadow": mx.zeros((1,), dtype=mx.float32)}
        missing = dict(self.full)
        missing.pop("refine.query")
        wrong = dict(self.full)
        wrong["refine.query"] = mx.zeros((768, 192), dtype=mx.float32)
        for tree in (extra, missing, wrong):
            with self.subTest(tree=len(tree)), self.assertRaises(BilqisError):
                refinement_parameter_view(tree, spec=self.spec, extents=self.extents)


if __name__ == "__main__":
    unittest.main()
