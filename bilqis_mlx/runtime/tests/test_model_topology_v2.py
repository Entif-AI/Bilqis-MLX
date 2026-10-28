"""BAMF architecture identity and historical isolation."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology import ModelTopologySpec
from bilqis_mlx.runtime.model_topology_v2 import (
    BAMF_ARCHITECTURE_ID, LEGACY_ARCHITECTURE_ID, ModelTopologySpecV2,
    deserialize_topology, initializer_seed,
)
from bilqis_mlx.runtime.topology_lifecycle import (
    dispatch_model_factory, operator_topology, topology_from_file,
)


class ModelTopologyV2Tests(unittest.TestCase):
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

    @unittest.skipUnless(os.environ.get("BILQIS_V1_BUNDLE_WITNESS"),
                         "set BILQIS_V1_BUNDLE_WITNESS to a frozen historical bundle")
    def test_real_legacy_bundle_is_rejected_and_remains_readable(self):
        from bilqis_mlx.runtime.mlx_checkpoint import load_semantically_bound_bundle

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
        with self.assertRaises(BilqisError) as error:
            dispatch_model_factory(BAMF_ARCHITECTURE_ID, ModelTopologySpecV2().to_record(),
                legacy_factory=forbid_allocation, bamf_factory=forbid_allocation,
                checkpoint_path=bundle)
        self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.MISMATCH")
        with TemporaryDirectory() as temporary:
            clone = Path(temporary)
            for path in files:
                if path.name != "manifest.json":
                    (clone / path.name).symlink_to(path)
            altered = {**manifest, "schema": "bilqis.mlx.fp32-adamw-bundle/v2",
                       "architecture_id": BAMF_ARCHITECTURE_ID,
                       "parameter_shapes": {"blocks.0.query": [384, 768]}}
            (clone / "manifest.json").write_text(json.dumps(altered))
            with self.assertRaises(BilqisError) as error:
                dispatch_model_factory(BAMF_ARCHITECTURE_ID, ModelTopologySpecV2().to_record(),
                    legacy_factory=forbid_allocation, bamf_factory=forbid_allocation,
                    checkpoint_path=clone)
            self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.MISMATCH")
        parameters, optimizer, saved, _ = load_semantically_bound_bundle(bundle)
        self.assertEqual(tuple(parameters["position.weight"].shape), (96, 384))
        self.assertEqual(len([name for name in parameters if name.endswith(".qkv.weight")]), 6)
        self.assertEqual(int(optimizer.state["step"].item()), saved["optimizer_step"])
        self.assertEqual(hashes(), before)


if __name__ == "__main__":
    unittest.main()
