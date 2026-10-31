"""BAMF architecture identity and historical isolation."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology import ModelTopologySpec
from bilqis_mlx.runtime.model_topology_v2 import BAMF_ARCHITECTURE_ID, LEGACY_ARCHITECTURE_ID, ModelTopologySpecV2, GenerationExtents
from bilqis_mlx.runtime.topology_lifecycle import (
    construct_unbound_model, dispatch_model_factory, operator_topology, topology_from_file,
)


class CompatibilityTests(unittest.TestCase):
    @staticmethod
    def extents(banks=1, pages=1):
        return GenerationExtents(banks, pages, "a" * 64, "b" * 64, "c" * 64)

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

    def test_facade_preserves_legacy_topology_and_optimizer_exports(self):
        from bilqis_mlx.runtime import model_topology, model_topology_v2
        self.assertIs(model_topology_v2.ModelTopologySpec, model_topology.ModelTopologySpec)
        self.assertIs(model_topology_v2.DEFAULT_OPTIMIZER, model_topology.DEFAULT_OPTIMIZER)
        self.assertEqual(model_topology_v2.LEGACY_SCHEMA, model_topology.SCHEMA)
