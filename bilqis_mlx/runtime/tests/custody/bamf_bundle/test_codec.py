"""B13.1 durable bundle, corruption, pointer and historical-v1 witnesses."""
from __future__ import annotations

import json
import os
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import mlx.core as mx
import mlx.optimizers as optim
import numpy as np

import bilqis_mlx.runtime.bamf_bundle.codec as codec
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.runtime.bamf_bundle import (
    BamfBundleCandidate, load_bamf_bundle, load_bamf_generation,
    publish_bamf_generation, save_bamf_bundle,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, GenerationProvenance, Initializer, ModelTopologySpecV2,
    ParameterGroup, ParameterSpec,
)


class BamfBundleCodecTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()
        self.declared = (ParameterSpec(
            "fixture.matrix", (2, 2), Initializer.MATRIX, ParameterGroup.FAST, True),)

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def candidate(self, generation=0, parent=None):
        digests = ("a" * 64, "b" * 64, "c" * 64)
        extents = GenerationExtents(1, 1, *digests)
        parameters = {"fixture.matrix": mx.array([[1., 2.], [3., 4.]], dtype=mx.float32)}
        state = AdamWStateTree(
            parameters, {"fixture.matrix": mx.full((2, 2), .1, dtype=mx.float32)},
            {"fixture.matrix": mx.full((2, 2), .2, dtype=mx.float32)},
            {"fixture.matrix": mx.array(7, dtype=mx.uint64)})
        return BamfBundleCandidate(
            generation, parent, ModelTopologySpecV2(), extents, state,
            AdamWHyperparameters(.00013, (.9, .95), 1e-8, .01), 11,
            GenerationProvenance("fixture-source", "d" * 64, "fixture-teacher", 3),
            {"schema": "fixture/abi", "active_set_sha256": digests[0],
             "semantic_bank_count": 1, "entries": ["semantic:a"]},
            {"schema": "fixture/motif", "motif_key_map_sha256": digests[1],
             "motif_page_count": 1, "slots": ["slot:a"]},
            PlasticityPolicy(),
            {"schema": "fixture/compiler", "factor_map_sha256": digests[2],
             "compiler_sha256": "e" * 64, "rights_epoch": 2,
             "correction_generation": 4},
            {"schema": "fixture/correction", "rights_epoch": 2,
             "correction_generation": 4, "frontier": []},
            {"schema": "fixture/teacher", "teacher_epoch": 3, "next_seed": 42,
             "cursor": "lesson:7"},
            {"schema": "fixture/evaluation", "contract_sha256": "f" * 64},
            ({"event": "FIXTURE_ACCEPTED", "event_id": "1" * 64},))

    def shape_patch(self):
        return patch("bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
                     return_value=self.declared)

    def test_round_trip_preserves_numerical_and_sidecar_state_with_100gib_default(self):
        candidate = self.candidate()
        with self.shape_patch(), patch.object(mlx_checkpoint, "assert_headroom") as reserve:
            manifest = save_bamf_bundle(candidate, self.root / "bundle")
            loaded = load_bamf_bundle(
                self.root / "bundle", expected_manifest_sha256=manifest["manifest_sha256"])
        self.assertEqual(loaded.generation, 0)
        self.assertEqual(loaded.optimizer_step, 11)
        self.assertEqual(loaded.teacher_state["next_seed"], 42)
        self.assertEqual(loaded.correction_frontier["correction_generation"], 4)
        self.assertEqual(loaded.outbox, candidate.outbox)
        np.testing.assert_array_equal(
            np.asarray(loaded.optimizer.parameters["fixture.matrix"]),
            np.asarray(candidate.optimizer.parameters["fixture.matrix"]))
        np.testing.assert_array_equal(
            np.asarray(loaded.optimizer.update_counts["fixture.matrix"]),
            np.asarray(candidate.optimizer.update_counts["fixture.matrix"]))
        self.assertEqual(reserve.call_args.kwargs["reserve_gib"], 100.0)

    def test_corrupt_or_inconsistent_sidecar_fails_before_tensor_load(self):
        with self.shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            save_bamf_bundle(self.candidate(), self.root / "bundle")
        sidecar = self.root / "bundle" / "correction-frontier.json"
        sidecar.write_text(sidecar.read_text().replace('"correction_generation":4',
                                                       '"correction_generation":5'))
        with patch.object(codec._mlx_checkpoint, "load_bamf_state_payload") as tensor_load:
            with self.assertRaisesRegex(ValueError, "DATA_PLANE_BUNDLE_PAYLOAD_DRIFT"):
                load_bamf_bundle(self.root / "bundle")
        tensor_load.assert_not_called()
        wrong = replace(self.candidate(), correction_frontier={
            "schema": "fixture/correction", "rights_epoch": 2,
            "correction_generation": 5, "frontier": []})
        with patch.object(codec._mlx_checkpoint, "save_bamf_state_payload") as tensor_save:
            with self.assertRaisesRegex(ValueError, "DATA_PLANE_BUNDLE_MANIFEST_INVALID"):
                save_bamf_bundle(wrong, self.root / "rejected")
        tensor_save.assert_not_called()

    def test_pointer_switch_is_atomic_boundary_and_unpublished_bundle_does_not_advance(self):
        with self.shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            first = publish_bamf_generation(self.root / "run", self.candidate(0))
            child = self.candidate(1, first["manifest_sha256"])
            save_bamf_bundle(child, self.root / "orphan")
            still_first = load_bamf_generation(self.root / "run" / "bamf-state.json")
            self.assertEqual(still_first.generation, 0)
            second = publish_bamf_generation(self.root / "run", child)
            loaded = load_bamf_generation(self.root / "run" / "bamf-state.json")
        self.assertNotEqual(first["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(loaded.generation, 1)
        self.assertEqual(loaded.parent_manifest_sha256, first["manifest_sha256"])
        self.assertTrue((self.root / "run" / first["bundle"]).is_dir())
        with self.assertRaisesRegex(ValueError, "DATA_PLANE_BUNDLE_IDENTITY_CONFLICT"):
            with self.shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
                publish_bamf_generation(
                    self.root / "run", self.candidate(3, second["manifest_sha256"]))

    def test_historical_v1_remains_readable_and_is_not_coerced_to_v2(self):
        parameters = {"p": mx.array([1., 2.], dtype=mx.float32)}
        optimizer = optim.AdamW(learning_rate=.001, bias_correction=True)
        optimizer.apply_gradients({"p": mx.ones((2,), dtype=mx.float32)}, parameters)
        legacy = self.root / "legacy"
        mlx_checkpoint.save_new_bundle(
            legacy, parameters, optimizer, source_digest="a" * 64, reserve_gib=0.0)
        restored, _, manifest = mlx_checkpoint.load_bundle(legacy)
        self.assertEqual(list(restored), ["p"])
        self.assertEqual(manifest["schema"], mlx_checkpoint.SCHEMA)
        with patch.object(codec._mlx_checkpoint, "load_bamf_state_payload") as tensor_load:
            with self.assertRaisesRegex(ValueError, "DATA_PLANE_BUNDLE_MANIFEST_INVALID"):
                load_bamf_bundle(legacy)
        tensor_load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
