"""B01 spec conformance and compatibility."""
from bilqis_mlx.runtime.tests.model.topology.helpers import (
    BAMF_ARCHITECTURE_ID,
    BilqisError,
    ModelTopologySpec,
    ModelTopologySpecV2,
    Path,
    TopologyFixture,
    deserialize_topology,
    initializer_seed,
    json,
)


class TopologySpecTests(TopologyFixture):
    def test_frozen_geometry_and_config_record(self):
        spec = ModelTopologySpecV2()
        self.assertEqual((spec.layers, spec.width, spec.ffn_dimension), (12, 768, 3072))
        self.assertEqual((spec.query_heads, spec.kv_heads, spec.head_dimension), (16, 8, 24))
        self.assertEqual((spec.rope_dimensions, spec.context), (24, 1024))
        self.assertEqual((spec.semantic_bank_rows, spec.motif_page_rows), (8192, 16384))
        self.assertEqual(spec.ffn_activation, "squared-relu")
        self.assertEqual(spec.initializer, "sha256-pcg64-v2")
        config = Path(__file__).resolve().parents[5] / "configs/models/bamf-0.2.json"
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
