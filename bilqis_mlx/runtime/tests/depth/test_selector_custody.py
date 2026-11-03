"""B05.3 joins singular B01 selector ownership to the real B13 cold reader."""
from dataclasses import replace
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import CandidateState
from bilqis_mlx.runtime.atlas_optimizer import _create_unbound_bamf_optimizer
from bilqis_mlx.runtime.bamf_bundle import load_bamf_bundle, save_bamf_bundle
from bilqis_mlx.runtime.block_attnres import (
    depth_parameter_view, _numerical_depth_select_with_diagnostics,
)
from bilqis_mlx.runtime.model_topology_v2 import expected_bamf_shapes
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import candidate, parent_state
from bilqis_mlx.runtime.tests.depth.depth_helpers import _released_features, _hidden, _summaries


SHARED = ("norm", "query", "key", "value", "output")
DEPTH_NAMES = {*("depth." + name for name in SHARED),
               *(f"depth.gate.{group}.{part}" for group in range(3)
                 for part in ("vector", "bias"))}


@unittest.skipUnless(os.environ.get("BILQIS_BAMF_FULL_WITNESS"),
                     "full disposable B05/B13 CPU custody witness is opt-in")
class SelectorCustodyTests(unittest.TestCase):
    def test_real_constructor_and_cold_bundle_preserve_all_three_selectors(self):
        previous = mx.default_device()
        mx.set_default_device(mx.cpu)
        try:
            self.exercise_selector_custody()
        finally:
            mx.set_default_device(previous)

    def exercise_selector_custody(self):
        original = candidate(parent_state())
        spec = original.topology
        extents = replace(original.extents, semantic_bank_count=2,
                          factor_map_digest=_released_features().features.digest)
        numerical, decay, construction = _create_unbound_bamf_optimizer(
            spec, extents, run_seed=451)
        ledger = expected_bamf_shapes(spec, extents)
        self.assertEqual(set(numerical.parameters), {item.name for item in ledger})
        self.assertEqual(set(decay), set(numerical.parameters))
        self.assertEqual(construction["initialization_status"], "UNBOUND")
        self.assertEqual({item.name for item in ledger if item.name.startswith("depth.")},
                         DEPTH_NAMES)
        for item in ledger:
            self.assertEqual(numerical.parameters[item.name].shape, item.shape)
            self.assertEqual(decay[item.name], item.decay)
        manifest = {item["name"]: item for item in construction["parameters"]}
        self.assertEqual(len(construction["parameters"]), len(ledger))
        self.assertEqual(set(manifest), set(numerical.parameters))
        for item in ledger:
            if item.name in DEPTH_NAMES:
                self.assertEqual(manifest[item.name]["shape"], list(item.shape))
                self.assertEqual(manifest[item.name]["initializer"], item.initializer.value)
                self.assertEqual(manifest[item.name]["group"], item.group.value)
                self.assertEqual(manifest[item.name]["category"], item.category.value)
        # Expanding semantic banks must leave the shared selector namespace singular.
        unexpanded = expected_bamf_shapes(spec, original.extents)
        self.assertEqual({item.name for item in ledger} - {item.name for item in unexpanded},
                         {"identity.bank.1"})
        before = self.selectors(numerical.parameters, spec, extents)
        for index in range(3):
            np.testing.assert_array_equal(
                np.asarray(numerical.parameters[f"depth.gate.{index}.vector"]), 0)
            np.testing.assert_allclose(
                np.asarray(numerical.parameters[f"depth.gate.{index}.bias"]),
                math.log(1 / 9), rtol=1e-6)
        retained = CandidateState(numerical, original.retained_state.policy,
                                  original.retained_state.allocations, 0)
        value = replace(original, extents=extents, retained_state=retained,
                        compiler_features={**original.compiler_features,
                                           "factor_map_sha256": extents.factor_map_digest},
                        semantic_abi={**original.semantic_abi,
                                      "semantic_bank_count": 2,
                                      "bank_identities": ["bank:0", "bank:1"]})
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(root / "plane.db")}):
                bundle = root / "selector-custody"
                saved = save_bamf_bundle(value, bundle)
                restored = load_bamf_bundle(
                    bundle, expected_manifest_sha256=saved["manifest_sha256"])
                after = self.selectors(restored.retained_state.optimizer.parameters,
                                       restored.topology, restored.extents)
        for old, new in zip(before, after, strict=True):
            for field in ("output", "alpha", "gate"):
                np.testing.assert_array_equal(np.asarray(getattr(old, field)),
                                              np.asarray(getattr(new, field)))
        for field in ("parameters", "m", "v", "update_counts"):
            old_tree = getattr(numerical, field)
            new_tree = getattr(restored.retained_state.optimizer, field)
            for name in DEPTH_NAMES:
                self.assertEqual(old_tree[name].shape, new_tree[name].shape)
                self.assertEqual(old_tree[name].dtype, new_tree[name].dtype)
                self.assertTrue(bool(mx.array_equal(old_tree[name], new_tree[name])))
        self.assertEqual(restored.retained_state.optimizer_step, 0)
        self.reject_misowned_selector(numerical.parameters, spec, extents)

    def selectors(self, parameters, spec, extents):
        views = tuple(depth_parameter_view(parameters, spec=spec, extents=extents,
                                           boundary_group=group) for group in (1, 2, 3))
        for name in SHARED:
            self.assertIs(views[0][name], views[1][name])
            self.assertIs(views[0][name], views[2][name])
            self.assertIs(views[0][name], parameters["depth." + name])
        self.assertEqual(len({id(view["gate_vector"]) for view in views}), 3)
        self.assertEqual(len({id(view["gate_bias"]) for view in views}), 3)
        for group, view in enumerate(views):
            self.assertIs(view["gate_vector"], parameters[f"depth.gate.{group}.vector"])
            self.assertIs(view["gate_bias"], parameters[f"depth.gate.{group}.bias"])
        current = _hidden([[1, 3, 2], [2, 4, 1]])
        diagnostics = tuple(_numerical_depth_select_with_diagnostics(
            current, _summaries(group), _released_features(group), view)
            for group, view in zip((1, 2, 3), views, strict=True))
        for group, result in zip((1, 2, 3), diagnostics, strict=True):
            self.assertEqual(result.alpha.shape[-1], group + 1)
            np.testing.assert_allclose(np.asarray(result.alpha.sum(axis=-1)), 1, atol=1e-6)
            np.testing.assert_allclose(np.asarray(result.gate), .01, atol=1e-7)
            for array in (result.output, result.alpha, result.gate):
                self.assertTrue(bool(mx.all(mx.isfinite(array))))
        return diagnostics

    def reject_misowned_selector(self, parameters, spec, extents):
        for path in ("depth.query", "depth.gate.2.vector"):
            changed = dict(parameters)
            changed["blocks.0." + path] = changed.pop(path)
            with self.subTest(path=path), self.assertRaises(BilqisError):
                depth_parameter_view(changed, spec=spec, extents=extents, boundary_group=1)
