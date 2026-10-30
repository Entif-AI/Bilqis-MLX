"""BAMF architecture identity and historical isolation."""
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

    def test_frozen_geometry_and_config_record(self):
        spec = ModelTopologySpecV2()
        self.assertEqual((spec.layers, spec.width, spec.ffn_dimension), (12, 768, 3072))
        self.assertEqual((spec.query_heads, spec.kv_heads, spec.head_dimension), (16, 8, 24))
        self.assertEqual((spec.rope_dimensions, spec.context), (24, 1024))
        self.assertEqual((spec.semantic_bank_rows, spec.motif_page_rows), (8192, 16384))
        self.assertEqual(spec.ffn_activation, "squared-relu")
        self.assertEqual(spec.initializer, "sha256-pcg64-v2")
        config = Path(__file__).resolve().parents[4] / "configs/models/bamf-0.2.json"
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

    def test_generation_extents_versioned_roundtrip(self):
        original = self.extents()
        record = original.to_record()
        self.assertEqual(record, {
            "schema": "bilqis.mlx.generation-extents/v1",
            "semantic_bank_count": 1, "motif_page_count": 1,
            "active_semantic_digest": "a" * 64,
            "motif_key_map_digest": "b" * 64, "factor_map_digest": "c" * 64,
            "digest": original.digest,
        })
        self.assertEqual(GenerationExtents.from_record(json.loads(json.dumps(record))), original)
        topology = ModelTopologySpecV2().to_record()
        for banks, pages in ((2, 1), (1, 2), (2, 2)):
            grown = self.extents(banks, pages)
            self.assertEqual(GenerationExtents.from_record(grown.to_record()), grown)
            self.assertNotEqual(grown.digest, original.digest)
            self.assertEqual(ModelTopologySpecV2().to_record(), topology)
        for changed in ({**record, "schema": "future"}, {**record, "digest": "0" * 64},
                        {**record, "semantic_bank_count": 2}, {**record, "extra": 1},
                        {key: value for key, value in record.items() if key != "motif_page_count"},
                        None, []):
            with self.subTest(record=changed), self.assertRaises(BilqisError):
                GenerationExtents.from_record(changed)

    def test_provenance_is_separate_from_dense_and_extent_identity(self):
        spec, extents = ModelTopologySpecV2(), self.extents()
        original_topology, original_extents = spec.to_record(), extents.to_record()
        provenance = GenerationProvenance("fixture-source", "d" * 64, "fixture-teacher", 0)
        record = provenance.to_record()
        self.assertEqual(record["schema"], "bilqis.mlx.generation-provenance/v1")
        self.assertEqual(GenerationProvenance.from_record(json.loads(json.dumps(record))), provenance)
        for field, value in (("source_identity", "other-source"), ("release_digest", "e" * 64),
                             ("teacher_identity", "other-teacher"), ("teacher_epoch", 1)):
            other = GenerationProvenance(**{**{key: record[key] for key in (
                "source_identity", "release_digest", "teacher_identity", "teacher_epoch")}, field: value})
            self.assertNotEqual(other.digest, provenance.digest)
            self.assertEqual(spec.to_record(), original_topology)
            self.assertEqual(extents.to_record(), original_extents)
        for field, value in (("source_identity", ""), ("teacher_identity", " "),
                             ("release_digest", "invalid"), ("teacher_epoch", -1),
                             ("teacher_epoch", True)):
            with self.subTest(field=field), self.assertRaises(BilqisError):
                GenerationProvenance.from_record({**record, field: value})
        for bad in (None, [], {**record, "extra": 1}, {**record, "digest": "0" * 64},
                    {**record, "schema": "future"}):
            with self.assertRaises(BilqisError):
                GenerationProvenance.from_record(bad)

    def test_invalid_config_rejects_before_allocator(self):
        record = ModelTopologySpecV2().to_record()
        for field, value in (("kv_heads", 7), ("head_dimension", 0), ("query_heads", 0),
                             ("rope_dimensions", 23), ("dtype", "float16"),
                             ("semantic_bank_rows", 0), ("context", 0),
                             ("ffn_activation", "gelu")):
            allocations = []
            def allocate(topology):
                allocations.append(topology)
                self.fail("invalid config reached allocation")
            with self.subTest(field=field), self.assertRaises(BilqisError):
                dispatch_model_factory(BAMF_ARCHITECTURE_ID, {**record, field: value},
                                       legacy_factory=allocate, bamf_factory=allocate)
            self.assertEqual(allocations, [])

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
        self.assertNotEqual(self.extents().digest, self.extents(banks=2).digest)
        self.assertNotEqual(self.extents().digest, self.extents(pages=2).digest)
        self.assertEqual(spec.digest, ModelTopologySpecV2().digest)

    def test_parameter_census_reconciles_literal_counts_and_capacities(self):
        spec = ModelTopologySpecV2()
        census = bamf_parameter_census(spec, self.extents())
        self.assertEqual(census.total, 79469798)
        self.assertEqual(census.subtotals, {
            ParameterCategory.DENSE_MATRICES: 67239936,
            ParameterCategory.SEMANTIC_TABLES: 6291456,
            ParameterCategory.MOTIF_TABLES: 2097152,
            ParameterCategory.ADAPTER_MATRICES: 36864,
            ParameterCategory.AUXILIARY: 3804390,
        })
        self.assertEqual(sum(census.subtotals.values()), census.total)
        rows = {item.name: item for item in census.parameters}
        self.assertEqual(len(rows), 214)
        for kind in ("type", "role", "schema"):
            self.assertEqual(rows[f"features.{kind}"].shape, (512, 128))
            self.assertEqual(rows[f"features.{kind}"].parameter_count, 65536)
        self.assertEqual(rows["features.local_slot"].shape, (16, 768))
        output = StringIO()
        with redirect_stdout(output):
            print_bamf_parameter_census(spec, self.extents())
        self.assertIn("TOTAL_PARAMETERS 79469798", output.getvalue())
        for item in census.parameters:
            self.assertIn("TENSOR " + item.name + " ", output.getvalue())
        self.assertEqual(census.to_record()["total_parameters"], 79469798)

    def test_parameter_census_tracks_each_independent_table_extent(self):
        spec = ModelTopologySpecV2()
        original = bamf_parameter_census(spec, self.extents())
        for banks, pages, growth in ((2, 1, 6291456), (1, 2, 2097152), (2, 2, 8388608)):
            with self.subTest(banks=banks, pages=pages):
                grown = bamf_parameter_census(spec, self.extents(banks, pages))
                self.assertEqual(grown.total, original.total + growth)
                self.assertEqual(grown.subtotals[ParameterCategory.DENSE_MATRICES], 67239936)
                self.assertEqual(grown.subtotals[ParameterCategory.ADAPTER_MATRICES], 36864)
                self.assertEqual(grown.topology_digest, original.topology_digest)
                self.assertNotEqual(grown.extents_digest, original.extents_digest)

    def test_parameter_census_rejects_invalid_identity_and_duplicate_rows(self):
        spec, extents = ModelTopologySpecV2(), self.extents()
        row = expected_bamf_shapes(spec, extents)[0]
        for bad_spec, bad_extents in ((None, extents), (spec, None)):
            with self.assertRaises(BilqisError):
                bamf_parameter_census(bad_spec, bad_extents)
        for topology_digest, parameters in (("bad", (row,)), (spec.digest, (row, row))):
            with self.assertRaises(BilqisError):
                ParameterCensus(topology_digest, extents.digest, parameters)

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

    def test_source_bound_identity_factor_projection_is_b02_independent(self):
        import mlx.core as mx
        import numpy as np

        type_table = mx.zeros((512, 128), dtype=mx.float32)
        type_table = type_table.at[2].add(mx.ones((128,), dtype=mx.float32))
        parameters = {
            "features.type": type_table,
            "features.project_type": mx.ones((768, 128), dtype=mx.float32) / 128.0,
            "features.project_graph": mx.concatenate((
                mx.full((768, 1), 2.0, dtype=mx.float32),
                mx.zeros((768, 63), dtype=mx.float32)), axis=1),
            "features.gates": mx.zeros((4,), dtype=mx.float32),
        }
        factor = project_identity_source_factor(
            parameters, type_rows=(2,), type_overflow=(None,),
            graph64=(1.0,) + (0.0,) * 63,
            extents=self.extents(), predecessor_feature_digest="c" * 64)
        self.assertEqual(factor.shape, (768,))
        self.assertEqual(factor.dtype, np.float32)
        np.testing.assert_allclose(factor, np.full((768,), 1.5, dtype=np.float32))
        with self.assertRaises(BilqisError):
            project_identity_source_factor(
                parameters, type_rows=(2,), type_overflow=(None,),
                graph64=(1.0,) + (0.0,) * 63,
                extents=self.extents(), predecessor_feature_digest="d" * 64)

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
