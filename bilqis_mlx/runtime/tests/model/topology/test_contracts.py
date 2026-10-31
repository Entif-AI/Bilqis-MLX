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


from bilqis_mlx.runtime.tests.model.topology.helpers import ModelTopologyFixture, PROJECT_ROOT

class ModelTopologyV2Tests(ModelTopologyFixture):
    def test_frozen_geometry_and_config_record(self):
        spec = ModelTopologySpecV2()
        self.assertEqual((spec.layers, spec.width, spec.ffn_dimension), (12, 768, 3072))
        self.assertEqual((spec.query_heads, spec.kv_heads, spec.head_dimension), (16, 8, 24))
        self.assertEqual((spec.rope_dimensions, spec.context), (24, 1024))
        self.assertEqual((spec.semantic_bank_rows, spec.motif_page_rows), (8192, 16384))
        self.assertEqual(spec.ffn_activation, "squared-relu")
        self.assertEqual(spec.initializer, "sha256-pcg64-v2")
        config = PROJECT_ROOT / "configs/models/bamf-0.2.json"
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

    def test_parameter_census_rejects_invalid_identity_and_duplicate_rows(self):
        spec, extents = ModelTopologySpecV2(), self.extents()
        row = expected_bamf_shapes(spec, extents)[0]
        for bad_spec, bad_extents in ((None, extents), (spec, None)):
            with self.assertRaises(BilqisError):
                bamf_parameter_census(bad_spec, bad_extents)
        for topology_digest, parameters in (("bad", (row,)), (spec.digest, (row, row))):
            with self.assertRaises(BilqisError):
                ParameterCensus(topology_digest, extents.digest, parameters)
