"""B05.2a source-backed adapter execution at all three depth boundaries."""
from unittest import skipUnless

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.source_atoms.backbone import (
    complete_source_backbone_producer,
    finalize_source_backbone_hidden,
)
from bilqis_mlx.learning.source_atoms.tests.backbone_test_support import (
    SourceBackboneTestBase,
)
from bilqis_mlx.runtime.backbone_group_numerical import _content_digest
from bilqis_mlx.runtime.block_attnres import depth_parameter_view, source_depth_select
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE


def _nonzero_adapters(parameters):
    changed = dict(parameters)
    for group in range(3):
        prefix = f"plastic.group.{group}."
        changed[prefix + "norm"] = mx.ones((768,), dtype=mx.float32)
        changed[prefix + "A"] = changed[prefix + "A"].at[0, 0].add(.75)
        changed[prefix + "B"] = changed[prefix + "B"].at[0, 0].add(.5)
    return changed


def _manual_adapter(hidden, parameters, group):
    prefix = f"plastic.group.{group}."
    values = np.asarray(hidden)
    scale = np.asarray(parameters[prefix + "norm"])
    normalized = values / np.sqrt(
        np.mean(values * values, axis=-1, keepdims=True)
        + ModelTopologySpecV2.rms_norm_epsilon
    )
    normalized *= scale
    projected = normalized @ np.asarray(parameters[prefix + "A"]).T
    activated = projected / (1.0 + np.exp(-projected))
    return values + (
        activated @ np.asarray(parameters[prefix + "B"]).T
    ) / ModelTopologySpecV2.adapter_rank


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class SourceBackboneAdapterTests(SourceBackboneTestBase):
    def test_nonzero_adapters_are_the_actual_g2_and_g3_inputs(self):
        parameters = _nonzero_adapters(self.parameters)
        producer = self.producer(parameters)
        producer.advance()

        view1 = depth_parameter_view(
            parameters, spec=ModelTopologySpecV2(), extents=self.compiled.extents,
            boundary_group=1)
        selected1 = source_depth_select(producer, view1)
        expected1 = _manual_adapter(selected1, parameters, 0)
        self.assertFalse(np.array_equal(np.asarray(selected1), expected1))
        g2 = producer.advance(depth_parameters=view1)
        self.assertEqual(g2.input_digest, _content_digest(mx.array(expected1)))

        view2 = depth_parameter_view(
            parameters, spec=ModelTopologySpecV2(), extents=self.compiled.extents,
            boundary_group=2)
        selected2 = source_depth_select(producer, view2)
        expected2 = _manual_adapter(selected2, parameters, 1)
        self.assertFalse(np.array_equal(np.asarray(selected2), expected2))
        g3 = producer.advance(depth_parameters=view2)
        self.assertEqual(g3.input_digest, _content_digest(mx.array(expected2)))
        self.assertEqual(tuple(item.source_id for item in producer.receipts),
                         ("h0", "g1", "g2", "g3"))

    def test_boundary_three_returns_adapted_output_without_a_fourth_group(self):
        parameters = _nonzero_adapters(self.parameters)
        producer = self.producer(parameters)
        complete_source_backbone_producer(producer)
        view3 = depth_parameter_view(
            parameters, spec=ModelTopologySpecV2(), extents=self.compiled.extents,
            boundary_group=3)
        selected3 = source_depth_select(producer, view3)
        expected3 = _manual_adapter(selected3, parameters, 2)

        actual = finalize_source_backbone_hidden(producer)

        np.testing.assert_allclose(np.asarray(actual), expected3, rtol=2e-6, atol=2e-6)
        self.assertFalse(np.array_equal(np.asarray(selected3), np.asarray(actual)))
        self.assertEqual(len(producer._session.results), 3)
        self.assertEqual(tuple(item.source_id for item in producer.receipts),
                         ("h0", "g1", "g2", "g3"))

    def test_adapter_gradients_are_finite_and_reach_all_three_groups(self):
        parameters = _nonzero_adapters(self.parameters)

        def objective(values):
            return mx.sum(finalize_source_backbone_hidden(self.producer(values))[..., 0])

        gradients = mx.grad(objective)(parameters)
        for group in range(3):
            for name in ("A", "B"):
                gradient = gradients[f"plastic.group.{group}.{name}"]
                with self.subTest(group=group, parameter=name):
                    self.assertTrue(bool(mx.all(mx.isfinite(gradient))))
                    self.assertGreater(float(mx.abs(gradient).sum()), 0.0)

    def test_zero_init_parity_and_boundary_or_tree_substitution_reject(self):
        producer = self.producer()
        producer.advance()
        view1 = depth_parameter_view(
            self.parameters, spec=ModelTopologySpecV2(), extents=self.compiled.extents,
            boundary_group=1)
        selected = source_depth_select(producer, view1)
        g2 = producer.advance(depth_parameters=view1)
        self.assertEqual(g2.input_digest, _content_digest(selected))

        stale = depth_parameter_view(
            self.parameters, spec=ModelTopologySpecV2(), extents=self.compiled.extents,
            boundary_group=1)
        with self.assertRaises(BilqisError):
            producer.advance(depth_parameters=stale)

        producer._parameters = dict(producer._parameters)
        producer._parameters["foreign.tree.member"] = mx.zeros((1,), dtype=mx.float32)
        view2 = depth_parameter_view(
            self.parameters, spec=ModelTopologySpecV2(), extents=self.compiled.extents,
            boundary_group=2)
        with self.assertRaises(BilqisError):
            producer.advance(depth_parameters=view2)
        self.assertEqual(len(producer._session.results), 2)


if __name__ == "__main__":
    import unittest
    unittest.main()
