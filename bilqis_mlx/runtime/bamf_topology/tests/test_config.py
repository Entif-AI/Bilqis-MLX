"""BAMF architecture identity and historical isolation."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology import ModelTopologySpec
from bilqis_mlx.runtime.model_topology_v2 import BAMF_ARCHITECTURE_ID, ModelTopologySpecV2, GenerationExtents, deserialize_topology
from bilqis_mlx.runtime.topology_lifecycle import dispatch_model_factory


class ConfigTests(unittest.TestCase):
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
