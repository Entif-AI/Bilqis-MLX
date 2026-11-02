"""B06.4: refinement parameters are an exact immutable B01 ledger projection."""
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_refinement import (
    RefinementParameterView, _refine_frame, _require_b01_projection, refinement_parameter_view,
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
        self.assertEqual(tuple(view.keys()), tuple(item.name for item in declared))
        self.assertEqual(view.topology_digest, self.spec.digest)
        self.assertEqual(view.extents_digest, self.extents.digest)
        for item in declared:
            self.assertIs(view[item.name], self.full[item.name])

    def test_projection_mapping_is_immutable(self):
        view = refinement_parameter_view(
            self.full, spec=self.spec, extents=self.extents)
        with self.assertRaises(BilqisError):
            view["refine.norm"] = mx.zeros((768,), dtype=mx.float32)
        with self.assertRaises(BilqisError):
            view.update({"refine.norm": mx.zeros((768,), dtype=mx.float32)})

    def test_base_dict_mutation_cannot_replace_aliased_tensor(self):
        view = refinement_parameter_view(
            self.full, spec=self.spec, extents=self.extents)
        original = view["refine.query"]
        with self.assertRaises(TypeError):
            dict.__setitem__(view, "refine.query", mx.zeros_like(original))
        with self.assertRaises(AttributeError):
            tuple.__setitem__(view, 1, mx.zeros_like(original))
        type.__setattr__(type(view), "_indices", {"refine.query": 0})
        self.assertIs(view["refine.query"], original)
        self.assertIs(original, self.full["refine.query"])

    def test_reconstructed_tuple_cannot_claim_b01_projection(self):
        view = refinement_parameter_view(self.full, spec=self.spec, extents=self.extents)
        _require_b01_projection(view)
        values = [tuple.__getitem__(view, i) for i in range(tuple.__len__(view))]
        same_aliases = type(view)(*values)
        with self.assertRaises(BilqisError):
            _require_b01_projection(same_aliases)
        values[1] = mx.zeros_like(values[1])
        forged = type(view)(*values)
        with self.assertRaises(BilqisError):
            _require_b01_projection(forged)
        with self.assertRaises(BilqisError):
            _ = forged.topology_digest

    def test_replaced_accessor_does_not_change_numerical_consumer(self):
        view = refinement_parameter_view(self.full, spec=self.spec, extents=self.extents)
        hidden = mx.arange(768, dtype=mx.float32) / 768
        seed = mx.zeros((768,), dtype=mx.float32)
        members = mx.stack((hidden, hidden + .25))
        role = mx.ones((768,), dtype=mx.float32) * .125
        expected = _refine_frame(hidden, seed, members, role, 1, view)
        type.__setattr__(type(view), "__getitem__", lambda self, key: mx.zeros((1,)))
        actual = _refine_frame(hidden, seed, members, role, 1, view)
        _require_b01_projection(view)
        np.testing.assert_array_equal(np.asarray(actual.hidden), np.asarray(expected.hidden))

    def test_view_identity_metadata_is_canonical(self):
        view = refinement_parameter_view(
            self.full, spec=self.spec, extents=self.extents)
        with self.assertRaises(BilqisError):
            view.topology_digest = "0" * 64
        with self.assertRaises(BilqisError):
            type(view).topology_digest = "0" * 64
        for topology_digest, extents_digest in (
            ("x" * 64, self.extents.digest),
            (self.spec.digest, "0" * 63),
        ):
            with self.subTest(topology_digest=topology_digest, extents_digest=extents_digest), \
                    self.assertRaises(BilqisError):
                RefinementParameterView(
                    topology_digest, extents_digest, view.declarations, view)

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
        direct = {name: self.full[name] for name in view.keys()}
        expected = _refine_frame(hidden, seed, members, role, 2, direct)
        actual = _refine_frame(hidden, seed, members, role, 2, view)
        np.testing.assert_array_equal(np.asarray(actual.hidden), np.asarray(expected.hidden))
        np.testing.assert_array_equal(
            np.asarray(actual.route_logits), np.asarray(expected.route_logits))

    def test_registry_view_is_directly_differentiable_parameter_tree(self):
        view = refinement_parameter_view(
            self.full, spec=self.spec, extents=self.extents)
        hidden = mx.arange(768, dtype=mx.float32) / 768
        seed = mx.zeros((768,), dtype=mx.float32)
        members = mx.stack((hidden, hidden + mx.array(.25, dtype=mx.float32)))
        role = mx.ones((768,), dtype=mx.float32) * mx.array(.125, dtype=mx.float32)

        def loss(parameters):
            result = _refine_frame(hidden, seed, members, role, 2, parameters)
            return mx.sum(result.hidden) + mx.sum(result.route_logits)

        gradients = mx.grad(loss)(view)
        self.assertIsInstance(gradients, RefinementParameterView)
        self.assertEqual(tuple(gradients.keys()), tuple(view.keys()))
        with self.assertRaises(BilqisError):
            _require_b01_projection(gradients)
        for name in view.keys():
            self.assertGreater(float(mx.sum(mx.abs(gradients[name]))), 0.0)

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
