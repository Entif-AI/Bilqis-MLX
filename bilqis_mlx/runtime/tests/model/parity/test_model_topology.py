"""Disposable structural topology contract tests."""
from __future__ import annotations

import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology import (
    CURRENT_DEFAULT_TOPOLOGY, ModelTopologySpec, create_student,
    expected_parameter_shapes, resolve_topology, topology_from_config,
    validate_parameter_shapes,
)


class ModelTopologyTests(unittest.TestCase):
    def test_pinned_default_and_config_resolution(self):
        config = {"layers": 6, "heads": 24, "width": 384, "expansion": 4, "context": 96}
        self.assertEqual(topology_from_config(config), CURRENT_DEFAULT_TOPOLOGY)
        self.assertEqual(resolve_topology(config), CURRENT_DEFAULT_TOPOLOGY)

    def test_record_is_digest_bound_and_round_trips(self):
        topology = ModelTopologySpec(2, 4, 32, 96, 48)
        self.assertEqual(ModelTopologySpec.from_record(topology.to_record()), topology)
        bad = {**topology.to_record(), "width": 64}
        with self.assertRaises(BilqisError) as error:
            ModelTopologySpec.from_record(bad)
        self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID")

    def test_invalid_dimensions_fail_before_allocation(self):
        invalid = [(2, 3, 32, 64, 48), (2, 4, True, 64, 48)]
        for index in range(5):
            for value in (0, -1):
                args = [2, 4, 32, 64, 48]
                args[index] = value
                invalid.append(tuple(args))
        for args in invalid:
            with self.assertRaises(BilqisError) as error:
                ModelTopologySpec(*args)
            self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.INVALID")

    def test_resume_rejects_requested_or_persisted_structure_drift(self):
        config = {"layers": 2, "heads": 4, "width": 32, "expansion": 3, "context": 48}
        stored = ModelTopologySpec(2, 4, 32, 96, 48).to_record()
        self.assertEqual(resolve_topology(config, record=stored), ModelTopologySpec.from_record(stored))
        with self.assertRaises(BilqisError) as error:
            resolve_topology(config, record=stored, requested=ModelTopologySpec(3, 4, 32, 96, 48))
        self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.MISMATCH")
        with self.assertRaises(BilqisError) as error:
            resolve_topology(config, requested=ModelTopologySpec(3, 4, 32, 96, 48))
        self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.MISMATCH")

    def test_disposable_topologies_construct_full_shapes(self):
        try:
            import mlx.core as mx
            from bilqis_mlx.runtime.mlx_parity import forward_arrays
        except ImportError:
            self.skipTest("MLX unavailable")
        mx.set_default_device(mx.cpu)
        for topology in (ModelTopologySpec(1, 2, 16, 24, 12),
                         ModelTopologySpec(2, 4, 32, 80, 18)):
            parameters, optimizer = create_student(topology, 31, seed=17)
            self.assertEqual({key: tuple(value.shape) for key, value in parameters.items()},
                             expected_parameter_shapes(topology, 31))
            self.assertEqual(set(optimizer.state) - {"step", "learning_rate"}, set(parameters))
            validate_parameter_shapes(parameters, topology, 31)
            logits = forward_arrays(mx, parameters, [[1, 2]], [2],
                                    heads=topology.heads, layers=topology.layers,
                                    answer_ids=[1, 2])
            mx.eval(logits)
            self.assertEqual(tuple(logits.shape), (1, 2))

    def test_shape_drift_is_rejected(self):
        try:
            import mlx.core as mx
        except ImportError:
            self.skipTest("MLX unavailable")
        topology = ModelTopologySpec(1, 2, 16, 24, 12)
        parameters, _ = create_student(topology, 9, seed=1)
        parameters["position.weight"] = mx.zeros((11, 16), dtype=mx.float32)
        with self.assertRaises(BilqisError) as error:
            validate_parameter_shapes(parameters, topology, 9)
        self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID")


if __name__ == "__main__":
    unittest.main()
