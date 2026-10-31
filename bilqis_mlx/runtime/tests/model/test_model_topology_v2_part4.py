"""Structural test shard from test_model_topology_v2.py; assertions preserved."""
from __future__ import annotations
import json
import hashlib
from contextlib import redirect_stdout
from io import StringIO
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology import ModelTopologySpec
from bilqis_mlx.runtime.model_topology_v2 import (
    BAMF_ARCHITECTURE_ID, LEGACY_ARCHITECTURE_ID, ModelTopologySpecV2,
    GenerationExtents, GenerationProvenance, ParameterCategory, ParameterCensus, ParameterGroup, ParameterSpec, Initializer,
    bamf_parameter_census, print_bamf_parameter_census,
    bamf_deserialize_arrays, bamf_serialization_arrays, bamf_storage_key,
    deserialize_topology,
    expected_bamf_shapes, initialize_bamf_parameter, initialize_bamf_row, initializer_seed,
    project_identity_source_factor,
    validate_bamf_parameters,
)
from bilqis_mlx.runtime.topology_lifecycle import (
    construct_unbound_model, dispatch_model_factory, operator_topology, topology_from_file,
)

class ModelTopologyV2Tests(unittest.TestCase):
        @staticmethod
        def extents(banks=1, pages=1):
            return GenerationExtents(banks, pages, "a" * 64, "b" * 64, "c" * 64)

        @unittest.skipUnless(os.environ.get("BILQIS_BAMF_FULL_WITNESS"),
                             "set BILQIS_BAMF_FULL_WITNESS for full disposable MLX allocation")
        def test_full_parameter_optimizer_and_serialization_tree(self):
            import mlx.core as mx
            from bilqis_mlx.runtime.disk import assert_headroom

            mx.set_default_device(mx.cpu)
            spec, extents = ModelTopologySpecV2(), self.extents()
            parameters, state, manifest = construct_unbound_model(
                BAMF_ARCHITECTURE_ID, spec.to_record(), run_seed=0, extents=extents)
            declared = expected_bamf_shapes(spec, extents)
            validate_bamf_parameters(spec, extents, parameters)
            self.assertEqual(manifest["initialization_status"], "UNBOUND")
            self.assertEqual(GenerationExtents.from_record(manifest["generation_extents"]), extents)
            self.assertEqual(manifest["parameter_count"], sum(math.prod(x.shape) for x in declared))
            self.assertEqual(manifest["parameter_count"], sum(value.size for value in parameters.values()))
            self.assertEqual(manifest["parameter_subtotals"],
                             bamf_parameter_census(spec, extents).to_record()["subtotals"])
            self.assertEqual(manifest["identity_row_group_policy"],
                             {"before_age": "FAST", "from_age": "SLOW", "established_at": 8,
                              "age_unit": "accepted-participating-candidates"})
            self.assertEqual(manifest["optimizer"]["betas"], [0.9, 0.95])
            query_shape = (384, 768)
            state["blocks.0.query"] = {"m": mx.full(query_shape, 0.125, dtype=mx.float32),
                                       "v": mx.full(query_shape, 0.25, dtype=mx.float32)}
            arrays = bamf_serialization_arrays(spec, extents, parameters, state)
            self.assertEqual(len(arrays), 3 * len(declared) + 2)
            identity_key = bamf_storage_key("identity.bank.0", "weight")
            self.assertEqual(tuple(arrays[identity_key].shape), (8192, 768))
            self.assertEqual(float(mx.sum(arrays[identity_key]).item()), 0.0)
            with TemporaryDirectory() as temporary:
                path = Path(temporary) / "unbound.safetensors"
                assert_headroom(path.parent, required_bytes=sum(x.nbytes for x in arrays.values()))
                mx.save_safetensors(str(path), arrays)
                restored = mx.load(str(path))
                self.assertEqual(set(restored), set(arrays))
                for name, value in arrays.items():
                    self.assertEqual(tuple(restored[name].shape), tuple(value.shape))
                    self.assertEqual(restored[name].dtype, value.dtype)
                mx.eval(restored)
                restored_parameters, restored_state = bamf_deserialize_arrays(spec, extents, restored)
                self.assertEqual(set(restored_parameters), set(parameters))
                self.assertEqual(set(restored_state), set(state))
                for name, value in arrays.items():
                    self.assertTrue(mx.array_equal(restored[name], value).item(), name)
                for banks, pages in ((2, 1), (1, 2), (2, 2)):
                    with self.subTest(banks=banks, pages=pages):
                        grown_extents = self.extents(banks=banks, pages=pages)
                        self.assertNotEqual(grown_extents.digest, extents.digest)
                        self.assertEqual(manifest["topology_digest"], spec.digest)
                        grown_parameters, grown_state = dict(parameters), dict(state)
                        for item in expected_bamf_shapes(spec, grown_extents):
                            if item.name not in grown_parameters:
                                grown_parameters[item.name] = mx.zeros(item.shape, dtype=mx.float32)
                                grown_state[item.name] = {"m": mx.zeros(item.shape, dtype=mx.float32),
                                                          "v": mx.zeros(item.shape, dtype=mx.float32)}
                        grown_arrays = bamf_serialization_arrays(spec, grown_extents, grown_parameters, grown_state)
                        self.assertTrue(set(arrays) <= set(grown_arrays))
                        grown_path = Path(temporary) / f"grown-{banks}-{pages}.safetensors"
                        assert_headroom(grown_path.parent, required_bytes=sum(x.nbytes for x in grown_arrays.values()))
                        mx.save_safetensors(str(grown_path), grown_arrays)
                        grown_restored = mx.load(str(grown_path))
                        mx.eval(grown_restored)
                        grown_parameters_read, grown_state_read = bamf_deserialize_arrays(spec, grown_extents, grown_restored)
                        self.assertEqual(set(grown_parameters_read), set(grown_parameters))
                        self.assertEqual(set(grown_state_read), set(grown_state))
                        for name in arrays:
                            self.assertTrue(mx.array_equal(grown_restored[name], restored[name]).item(), name)
                        self.assertEqual(float(grown_restored[bamf_storage_key("blocks.0.query", "m")][0, 0].item()), 0.125)
                        self.assertEqual(float(grown_restored[bamf_storage_key("blocks.0.query", "v")][0, 0].item()), 0.25)
                        grown_path.unlink()

        def test_factory_dispatch_and_legacy_checkpoint_rejection(self):
            legacy = ModelTopologySpec(6, 24, 384, 1536, 96)
            bamf = ModelTopologySpecV2()
            legacy_factory = lambda spec: ("legacy", spec.width)
            bamf_factory = lambda spec: ("bamf", spec.width)
            self.assertEqual(dispatch_model_factory(LEGACY_ARCHITECTURE_ID, legacy.to_record(),
                             legacy_factory=legacy_factory, bamf_factory=bamf_factory), ("legacy", 384))
            self.assertEqual(dispatch_model_factory(BAMF_ARCHITECTURE_ID, bamf.to_record(),
                             legacy_factory=legacy_factory, bamf_factory=bamf_factory), ("bamf", 768))
            for manifest in ({"schema": "bilqis.mlx.fp32-adamw-bundle/v1"},
                             {"schema": "bilqis.mlx.fp32-adamw-bundle/v1",
                              "architecture_id": BAMF_ARCHITECTURE_ID,
                              "parameter_shapes": {"blocks.0.query": [384, 768]}}):
                def forbid_allocation(_):
                    self.fail("allocated before rejecting legacy checkpoint")
                with self.assertRaises(BilqisError) as error:
                    dispatch_model_factory(BAMF_ARCHITECTURE_ID, bamf.to_record(),
                        legacy_factory=forbid_allocation, bamf_factory=forbid_allocation,
                        checkpoint_manifest=manifest)
                self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.MISMATCH")
            with self.assertRaises(BilqisError):
                dispatch_model_factory(BAMF_ARCHITECTURE_ID, legacy.to_record(),
                    legacy_factory=legacy_factory, bamf_factory=bamf_factory)

        def test_config_is_read_but_legacy_runtime_cannot_start_v2(self):
            config = Path(__file__).resolve().parents[4] / "configs/models/bamf-0.2.json"
            requested = topology_from_file(config)
            self.assertEqual(requested, ModelTopologySpecV2())
            with self.assertRaises(BilqisError) as error:
                operator_topology(Path("unused"), resume=False, requested=requested)
            self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.MISMATCH")

        def test_real_v1_factory_uses_legacy_topology(self):
            legacy = ModelTopologySpec(1, 2, 16, 24, 12)
            parameters, state, manifest = construct_unbound_model(
                LEGACY_ARCHITECTURE_ID, legacy.to_record(), run_seed=17, vocab_size=9)
            self.assertEqual(tuple(parameters["embedding.weight"].shape), (9, 16))
            self.assertEqual(tuple(parameters["position.weight"].shape), (12, 16))
            self.assertEqual(int(state["step"].item()), 0)
            self.assertEqual(manifest["architecture_id"], LEGACY_ARCHITECTURE_ID)
            self.assertEqual(manifest["initialization_status"], "UNBOUND")
