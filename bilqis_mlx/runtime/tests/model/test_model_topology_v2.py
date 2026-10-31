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
