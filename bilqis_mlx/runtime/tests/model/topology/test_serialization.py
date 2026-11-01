"""B01 serialization conformance and compatibility."""
from bilqis_mlx.runtime.tests.model.topology.helpers import (
    BAMF_ARCHITECTURE_ID,
    BilqisError,
    GenerationExtents,
    ModelTopologySpecV2,
    Path,
    TemporaryDirectory,
    TopologyFixture,
    bamf_deserialize_arrays,
    bamf_parameter_census,
    bamf_serialization_arrays,
    bamf_storage_key,
    construct_unbound_model,
    expected_bamf_shapes,
    math,
    os,
    unittest,
    validate_bamf_parameters,
)


class TopologySerializationTests(TopologyFixture):
    def test_storage_keys_are_stable_across_independent_extent_growth(self):
        import mlx.core as mx
        spec = ModelTopologySpecV2()
        def serialized(extents):
            declared = expected_bamf_shapes(spec, extents)
            parameters = {item.name: mx.zeros(item.shape, dtype=mx.float32) for item in declared}
            state = {"step": mx.array(0, dtype=mx.uint64), "learning_rate": mx.array(0.01),
                     **{item.name: {"m": mx.zeros(item.shape, dtype=mx.float32),
                                    "v": mx.zeros(item.shape, dtype=mx.float32)} for item in declared}}
            return set(bamf_serialization_arrays(spec, extents, parameters, state))
        original = {item.name for item in expected_bamf_shapes(spec, self.extents())}
        keys = {(name, part): bamf_storage_key(name, part)
                for name in original for part in ("weight", "m", "v")}
        self.assertEqual(len(set(keys.values())), len(keys))
        base_keys = serialized(self.extents())
        self.assertEqual(set(keys.values()), base_keys - {"adamw_global_step", "adamw_learning_rate"})
        for banks, pages in ((2, 1), (1, 2), (2, 2)):
            grown = {item.name for item in expected_bamf_shapes(spec, self.extents(banks, pages))}
            self.assertTrue(original <= grown)
            self.assertTrue(base_keys <= serialized(self.extents(banks, pages)))
        with self.assertRaises(BilqisError):
            bamf_storage_key("blocks.0.query", "unknown")
        self.assertNotEqual(bamf_storage_key("plastic.group.0.A", "weight"),
                            bamf_storage_key("plastic.group.0.a", "weight"))
        self.assertNotEqual(bamf_storage_key("x_m", "weight"), bamf_storage_key("x", "m"))

    def test_serialization_and_readback_reject_malformed_trees(self):
        import mlx.core as mx
        spec, extents = ModelTopologySpecV2(), self.extents()
        declared = expected_bamf_shapes(spec, extents)
        parameters = {item.name: mx.zeros(item.shape, dtype=mx.float32) for item in declared}
        state = {"step": mx.array(0, dtype=mx.uint64), "learning_rate": mx.array(0.01),
                 **{item.name: {"m": mx.zeros(item.shape, dtype=mx.float32),
                                "v": mx.zeros(item.shape, dtype=mx.float32)} for item in declared}}
        name = "blocks.0.query"
        bad_parameters = [
            {key: value for key, value in parameters.items() if key != name},
            {**parameters, "extra": mx.zeros((1,), dtype=mx.float32)},
            {**parameters, name: mx.zeros((1, 1), dtype=mx.float32)},
            {**parameters, name: mx.zeros((384, 768), dtype=mx.float16)},
        ]
        for bad in bad_parameters:
            with self.assertRaises(BilqisError):
                bamf_serialization_arrays(spec, extents, bad, state)
        with self.assertRaises(BilqisError):
            bamf_serialization_arrays(spec, extents, parameters, {**state, name: {"m": state[name]["m"]}})
        arrays = bamf_serialization_arrays(spec, extents, parameters, state)
        key = bamf_storage_key(name, "m")
        bad_arrays = [
            {k: v for k, v in arrays.items() if k != key},
            {**arrays, "unexpected": mx.zeros((1,), dtype=mx.float32)},
            {**arrays, key: mx.zeros((1, 1), dtype=mx.float32)},
            {**arrays, key: mx.zeros((384, 768), dtype=mx.float16)},
            {**arrays, "adamw_global_step": mx.array(0, dtype=mx.float32)},
        ]
        for bad in bad_arrays:
            with self.assertRaises(BilqisError):
                bamf_deserialize_arrays(spec, extents, bad)
