"""BAMF architecture identity and historical isolation."""
from __future__ import annotations

import json
import hashlib
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
    GenerationExtents, ParameterGroup, ParameterSpec, Initializer,
    bamf_deserialize_arrays, bamf_serialization_arrays, bamf_storage_key,
    deserialize_topology,
    expected_bamf_shapes, initialize_bamf_parameter, initialize_bamf_row, initializer_seed,
    validate_bamf_parameters,
)
from bilqis_mlx.runtime.topology_lifecycle import (
    construct_unbound_model, dispatch_model_factory, operator_topology, topology_from_file,
)


class ModelTopologyV2Tests(unittest.TestCase):
    @staticmethod
    def extents(banks=1, pages=1):
        return GenerationExtents(banks, pages, "a" * 64, "b" * 64, "c" * 64)

    def test_frozen_geometry_and_config_record(self):
        spec = ModelTopologySpecV2()
        self.assertEqual((spec.layers, spec.width, spec.ffn_dimension), (12, 768, 3072))
        self.assertEqual((spec.query_heads, spec.kv_heads, spec.head_dimension), (16, 8, 24))
        self.assertEqual((spec.rope_dimensions, spec.context), (24, 1024))
        self.assertEqual((spec.semantic_bank_rows, spec.motif_page_rows), (8192, 16384))
        self.assertEqual(spec.ffn_activation, "squared-relu")
        self.assertEqual(spec.initializer, "sha256-pcg64-v2")
        config = Path(__file__).resolve().parents[3] / "configs/models/bamf-0.2.json"
        self.assertEqual(json.loads(config.read_text()), spec.to_record())
        self.assertEqual(deserialize_topology(spec.to_record()), spec)

    def test_explicit_v1_and_v2_record_boundaries(self):
        legacy = ModelTopologySpec(6, 24, 384, 1536, 96)
        self.assertEqual(deserialize_topology(legacy.to_record()), legacy)
        record = ModelTopologySpecV2().to_record()
        for changed in ({**record, "kv_heads": 7}, {**record, "rope_dimensions": 23},
                        {**record, "ffn_activation": "gelu"},
                        {**record, "width": True}, {**record, "extra": 1}):
            with self.subTest(changed=changed), self.assertRaises(BilqisError):
                deserialize_topology(changed)
        with self.assertRaises(BilqisError):
            deserialize_topology({**legacy.to_record(), "architecture_id": BAMF_ARCHITECTURE_ID})

    def test_stable_initializer_seed(self):
        self.assertEqual(initializer_seed(0, "plastic.group.0.A"), 4633198684720072030)
        self.assertEqual(initializer_seed(0, "plastic.group.0.A"),
                         initializer_seed(0, "plastic.group.0.A", ""))
        self.assertNotEqual(initializer_seed(0, "identity.bank.0", "first"),
                            initializer_seed(0, "identity.bank.0", "second"))
        for seed in (True, 1.5):
            with self.assertRaises(BilqisError):
                initializer_seed(seed, "plastic.group.0.A")

    def test_literal_tensor_ledger_and_extents(self):
        spec = ModelTopologySpecV2()
        rows = expected_bamf_shapes(spec, self.extents())
        by_name = {row.name: row for row in rows}
        self.assertEqual(len(by_name), len(rows))
        literal_shapes = {
            "blocks.0.query": (384, 768), "blocks.0.key": (192, 768),
            "blocks.0.value": (192, 768), "blocks.0.output": (768, 384),
            "blocks.0.ffn_in": (3072, 768), "blocks.0.ffn_out": (768, 3072),
            "identity.bank.0": (8192, 768), "motif.page.0": (16384, 128),
            "plastic.group.0.A": (8, 768), "plastic.group.0.B": (768, 8),
        }
        for name, shape in literal_shapes.items():
            self.assertEqual(by_name[name].shape, shape)
            self.assertEqual(by_name[name].dtype, "float32")
        self.assertEqual(sum(math.prod(by_name[f"blocks.{i}.{part}"].shape)
            for i in range(12) for part in ("query", "key", "value", "output", "ffn_in", "ffn_out")),
            67239936)
        grown = {row.name: row for row in expected_bamf_shapes(spec, self.extents(banks=2))}
        self.assertEqual(grown["identity.bank.0"], by_name["identity.bank.0"])
        self.assertEqual(grown["identity.bank.1"].shape, (8192, 768))
        self.assertEqual(spec.digest, ModelTopologySpecV2().digest)

    def test_independent_initializer_golden_and_linear_orientation(self):
        import numpy as np
        rows = {row.name: row for row in expected_bamf_shapes(ModelTopologySpecV2(), self.extents())}
        adapter = initialize_bamf_parameter(rows["plastic.group.0.A"], run_seed=0)
        self.assertEqual(hashlib.sha256(adapter.tobytes()).hexdigest(),
                         "8cd9500504ae983012b5463f193683f97eb62bec9a532b95e35dc51544a7c571")
        self.assertTrue(np.all(initialize_bamf_parameter(rows["plastic.group.0.B"], run_seed=0) == 0))
        convolution = initialize_bamf_parameter(rows["blocks.0.conv_q"], run_seed=0)
        np.testing.assert_array_equal(convolution[0], [0.0, 0.0, 1.0])
        self.assertTrue(np.all(initialize_bamf_parameter(rows["identity.bank.0"], run_seed=0) == 0))
        expected = {"blocks.0.query": 0.06222047284245491,
                    "blocks.0.key": 0.013152116909623146,
                    "blocks.0.value": 0.03874354809522629,
                    "blocks.0.output": -0.019073694944381714,
                    "blocks.0.ffn_in": -0.06427312642335892,
                    "blocks.0.ffn_out": 0.020128803327679634}
        for name, literal in expected.items():
            weight = initialize_bamf_parameter(rows[name], run_seed=0)
            basis = np.zeros(weight.shape[1], dtype=np.float32)
            basis[5] = 1.0
            self.assertEqual(float((basis @ weight.T)[3]), literal, name)

    def test_invalid_extents_and_parameter_records_fail_closed(self):
        for args in ((0, 1, "a" * 64, "b" * 64, "c" * 64),
                     (1, 5, "a" * 64, "b" * 64, "c" * 64),
                     (True, 1, "a" * 64, "b" * 64, "c" * 64),
                     (1, 1, "bad", "b" * 64, "c" * 64)):
            with self.subTest(args=args), self.assertRaises(BilqisError):
                GenerationExtents(*args)
        for shape, initializer in (((0, 3), Initializer.MATRIX), ((3, 2), Initializer.CONV_IDENTITY),
                                   ((3, 4), "unknown"), ((1, 768), Initializer.IDENTITY_BANK),
                                   ((16384, 127), Initializer.MOTIF_PAGE)):
            with self.subTest(shape=shape, initializer=initializer), self.assertRaises(BilqisError):
                ParameterSpec("fixture", shape, initializer, ParameterGroup.SLOW, True)

    def test_row_initializers_are_stable_across_bank_growth(self):
        import numpy as np
        spec = ModelTopologySpecV2()
        first = {item.name: item for item in expected_bamf_shapes(spec, self.extents())}
        grown = {item.name: item for item in expected_bamf_shapes(spec, self.extents(banks=2, pages=2))}
        factors = np.ones(768, dtype=np.float32)
        identity = initialize_bamf_row(first["identity.bank.0"], run_seed=0,
                                       row_id="fixture:identity", factor=factors)
        self.assertEqual(hashlib.sha256(identity.tobytes()).hexdigest(),
                         "1c8fd2c39a4fac159fcdd9d54660bb0ee8b8dd256a77469b36763749ee8d2a79")
        np.testing.assert_array_equal(identity, initialize_bamf_row(grown["identity.bank.0"], run_seed=0,
                                                                    row_id="fixture:identity", factor=factors))
        motif = initialize_bamf_row(first["motif.page.0"], run_seed=0, row_id="fixture:motif")
        self.assertEqual(hashlib.sha256(motif.tobytes()).hexdigest(),
                         "2362325203db3fbd9d2a064cb6eec7aa6feff834ec8e16cad7aadc0a6b9e69fe")
        np.testing.assert_array_equal(motif, initialize_bamf_row(grown["motif.page.0"], run_seed=0,
                                                                 row_id="fixture:motif"))
        with self.assertRaises(BilqisError):
            initialize_bamf_row(first["identity.bank.0"], run_seed=0, row_id="fixture:identity")

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
        self.assertEqual(manifest["parameter_count"], sum(math.prod(x.shape) for x in declared))
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
            grown_extents = self.extents(banks=2, pages=2)
            grown_parameters, grown_state = dict(parameters), dict(state)
            for item in expected_bamf_shapes(spec, grown_extents):
                if item.name not in grown_parameters:
                    grown_parameters[item.name] = mx.zeros(item.shape, dtype=mx.float32)
                    grown_state[item.name] = {"m": mx.zeros(item.shape, dtype=mx.float32),
                                              "v": mx.zeros(item.shape, dtype=mx.float32)}
            grown_arrays = bamf_serialization_arrays(spec, grown_extents, grown_parameters, grown_state)
            self.assertTrue(set(arrays) <= set(grown_arrays))
            grown_path = Path(temporary) / "grown.safetensors"
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
        config = Path(__file__).resolve().parents[3] / "configs/models/bamf-0.2.json"
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

    @unittest.skipUnless(os.environ.get("BILQIS_V1_BUNDLE_WITNESS"),
                         "set BILQIS_V1_BUNDLE_WITNESS to a frozen historical bundle")
    def test_real_legacy_bundle_is_rejected_and_remains_readable(self):
        import mlx.core as mx
        from bilqis_mlx.runtime.disk import assert_headroom

        bundle = Path(os.environ["BILQIS_V1_BUNDLE_WITNESS"])
        files = sorted(path for path in bundle.iterdir() if path.is_file())

        def hashes():
            result = {}
            for path in files:
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                result[path.name] = digest.hexdigest()
            return result

        before = hashes()
        manifest = json.loads((bundle / "manifest.json").read_text())
        self.assertEqual(manifest["schema"], "bilqis.mlx.fp32-adamw-bundle/v1")
        def forbid_allocation(_):
            self.fail("allocated before rejecting legacy checkpoint")
        with patch("bilqis_mlx.runtime.model_topology_v2.create_unbound_bamf_state",
                   side_effect=forbid_allocation), self.assertRaises(BilqisError) as error:
            construct_unbound_model(BAMF_ARCHITECTURE_ID, ModelTopologySpecV2().to_record(),
                                    run_seed=0, extents=self.extents(), checkpoint_path=bundle)
        self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.MISMATCH")
        with TemporaryDirectory() as temporary:
            clone = Path(temporary)
            for path in files:
                if path.name not in ("manifest.json", "model-and-own-adamw.safetensors"):
                    (clone / path.name).symlink_to(path)
            altered = {**manifest, "schema": "bilqis.mlx.fp32-adamw-bundle/v2",
                       "architecture_id": BAMF_ARCHITECTURE_ID,
                       "parameter_shapes": {"blocks.0.query": [384, 768]}}
            (clone / "manifest.json").write_text(json.dumps(altered))
            tensor_file = bundle / "model-and-own-adamw.safetensors"
            tensor_copy = clone / tensor_file.name
            assert_headroom(clone, required_bytes=tensor_file.stat().st_size)
            tensors = mx.load(str(tensor_file))
            qkv_index = manifest["parameter_names"].index("blocks.0.qkv.weight")
            key = f"p{qkv_index:04d}_weight"
            self.assertEqual(tuple(tensors[key].shape), (1152, 384))
            tensors[key] = mx.zeros((384, 768), dtype=mx.float32)
            mx.save_safetensors(str(tensor_copy), tensors)
            self.assertEqual(tuple(mx.load(str(tensor_copy))[key].shape), (384, 768))
            with patch("bilqis_mlx.runtime.model_topology_v2.create_unbound_bamf_state",
                       side_effect=forbid_allocation), self.assertRaises(BilqisError) as error:
                construct_unbound_model(BAMF_ARCHITECTURE_ID, ModelTopologySpecV2().to_record(),
                                        run_seed=0, extents=self.extents(), checkpoint_path=clone)
            self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.MISMATCH")
        legacy = ModelTopologySpec(6, 24, 384, 1536, 96)
        parameters, state, saved = construct_unbound_model(
            LEGACY_ARCHITECTURE_ID, legacy.to_record(), run_seed=0, checkpoint_path=bundle)
        self.assertEqual(tuple(parameters["position.weight"].shape), (96, 384))
        self.assertEqual(len([name for name in parameters if name.endswith(".qkv.weight")]), 6)
        self.assertEqual(int(state["step"].item()), saved["optimizer_step"])
        self.assertEqual(hashes(), before)


if __name__ == "__main__":
    unittest.main()
