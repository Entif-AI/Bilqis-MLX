"""Immutable AtlasFeatures/v2 local export and readback witnesses."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import socket

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas.feature_io import (
    load_feature_manifest, persist_feature_manifest,
)
from bilqis_mlx.semantics.tests.test_atlas_features import (
    BROADER, _features, _snapshot,
)


class AtlasFeatureIOTests(TestCase):
    def test_source_reordering_keeps_bundle(self):
        snapshot = _snapshot((
            ("urn:concept:B", ("urn:type:B",)),
            ("urn:concept:A", ("urn:type:A",)),
        ))
        reordered = replace(
            snapshot, abi_entries=tuple(reversed(snapshot.abi_entries)),
            concepts=tuple(reversed(snapshot.concepts)))
        original = _features(snapshot)
        permuted = _features(reordered)
        self.assertEqual(original.digest, permuted.digest)
        with TemporaryDirectory() as root:
            first = persist_feature_manifest(original, root)
            second = persist_feature_manifest(permuted, root)
            self.assertEqual(first.bundle_id, second.bundle_id)
            self.assertEqual(first.path, second.path)
            self.assertEqual(load_feature_manifest(second.path), original)
    def test_committed_reference_vectors_are_independent_and_exact(self):
        root = Path(__file__).resolve().parents[4]
        script = root / "bilqis_mlx/semantics/tests/reference_atlas_features.py"
        golden = root / "docs/evidence/bamf/A06.2/golden_vectors.json"
        reference = subprocess.run(
            [sys.executable, "-B", str(script)],
            capture_output=True, check=True, text=True)
        self.assertEqual(reference.stdout.encode("utf-8"), golden.read_bytes())
        fixture = json.loads(golden.read_text(encoding="utf-8"))
        disconnected = _features().features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        self.assertEqual(disconnected.graph64,
                         tuple(fixture["disconnected_graph64"]))
        many = tuple("urn:type:%04d" % index for index in range(512))
        overflow = _features(_snapshot((("urn:concept:A", many),)))
        row = overflow.features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        for identifier, actual in row.type_overflow:
            self.assertEqual(
                actual, tuple(fixture["overflow"][identifier]["f128"]))
        collision = fixture["collision"]
        self.assertEqual(collision["combined_channel"], 47)
        self.assertEqual(collision["combined_value"], 0.0)
        self.assertEqual(
            [item["sign"] for item in collision["signatures"]], [-1, 1])
        collided = _features(_snapshot(
            (("urn:concept:A", ("urn:type:Entity",)),
             ("urn:concept:B", ("urn:type:collision-016",)),
             ("urn:concept:C", ("urn:type:collision-020",))),
            relations=(("urn:concept:A", BROADER, "urn:concept:B"),
                       ("urn:concept:A", BROADER, "urn:concept:C"))))
        collided_row = collided.features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        self.assertEqual(
            collided_row.graph64[collision["combined_channel"]],
            collision["combined_value"])
    def test_immutable_roundtrip_retry_and_network_free_local_lookup(self):
        features = _features()
        with TemporaryDirectory() as root:
            first = persist_feature_manifest(features, root)
            second = persist_feature_manifest(features, root)
            self.assertEqual(first, second)
            with patch.object(socket, "socket",
                              side_effect=AssertionError("network reached")):
                loaded = load_feature_manifest(
                    first.path, expected_bundle_id=first.bundle_id,
                    expected_feature_digest=features.digest,
                    expected_semantic_release=features.semantic_release,
                    expected_source_bundle_id=features.source_bundle_id,
                    expected_atlas_bundle_id=features.atlas_bundle_id)
                row = loaded.features_for(
                    "urn:concept:A", "left",
                    "frame:urn:concept:A", "task:scope")
            self.assertEqual(loaded, features)
            self.assertEqual(row.semantic_id, "urn:concept:A")
            self.assertEqual(row.type_rows, (2,))
            self.assertEqual(
                set(path.name for path in Path(first.path).iterdir()),
                {"features.json", "manifest.json"})

    def test_predecessor_maps_and_held_reasons_survive_local_export(self):
        base = _features(_snapshot(held=("urn:held:source",)))
        successor = _features(
            replace(_snapshot(
                (("urn:concept:A", ("urn:type:!new", "urn:type:Entity")),),
                release="b" * 64, held=("urn:held:source",)),
                prior_abi_sha256=base.atlas_bundle_id),
            predecessor=base)
        with TemporaryDirectory() as root:
            base_receipt = persist_feature_manifest(base, root)
            next_receipt = persist_feature_manifest(
                successor, root, predecessor=base)
            loaded_base = load_feature_manifest(base_receipt.path)
            loaded_next = load_feature_manifest(
                next_receipt.path, predecessor=loaded_base)
            self.assertEqual(loaded_next.predecessor_digest, base.digest)
            self.assertEqual(
                dict(loaded_next.type_map)["urn:type:Entity"],
                dict(loaded_base.type_map)["urn:type:Entity"])
            self.assertEqual(
                loaded_next.held_reasons,
                (("urn:held:source", "SOURCE_UNRESOLVED"),))
            with self.assertRaises(BilqisError):
                load_feature_manifest(next_receipt.path,
                                      predecessor=_features())
            poisoned = replace(
                successor,
                type_map=tuple(
                    (identifier, 3 if identifier == "urn:type:Entity"
                     else 2 if identifier == "urn:type:!new" else row)
                    for identifier, row in successor.type_map))
            with self.assertRaises(BilqisError) as caught:
                persist_feature_manifest(
                    poisoned, root, predecessor=loaded_base)
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_FEATURE_ARTIFACT_PREDECESSOR_MAP_DRIFT")

    def test_content_drift_wrong_pins_and_unexpected_files_fail_closed(self):
        features = _features()
        with TemporaryDirectory() as root:
            receipt = persist_feature_manifest(features, root)
            with self.assertRaises(BilqisError):
                load_feature_manifest(
                    receipt.path, expected_bundle_id="f" * 64)
            target = Path(receipt.path)
            payload = target / "features.json"
            original = payload.read_bytes()
            payload.write_bytes(original + b" ")
            with self.assertRaises(BilqisError):
                load_feature_manifest(target)
            with self.assertRaises(BilqisError):
                persist_feature_manifest(features, root)
            self.assertEqual(payload.read_bytes(), original + b" ")

    def test_extra_file_and_symlink_reject_without_mutation(self):
        features = _features()
        with TemporaryDirectory() as root:
            receipt = persist_feature_manifest(features, root)
            target = Path(receipt.path)
            extra = target / "extra"
            extra.write_text("not in manifest")
            with self.assertRaises(BilqisError):
                load_feature_manifest(target)
            extra.unlink()
            link = Path(root) / "alias"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(BilqisError):
                load_feature_manifest(link)

    def test_malformed_manifest_uses_error_bus_instead_of_raw_json_error(self):
        with TemporaryDirectory() as root:
            receipt = persist_feature_manifest(_features(), root)
            manifest = Path(receipt.path) / "manifest.json"
            manifest.write_bytes(
                b'{"schema":"bilqis.atlas-feature-artifact/v2","files":NaN}')
            with self.assertRaises(BilqisError) as caught:
                load_feature_manifest(receipt.path)
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_FEATURE_ARTIFACT_READ_INVALID")

    def test_publish_io_failure_is_a_catalogued_boundary_error(self):
        with TemporaryDirectory() as root:
            with patch(
                "bilqis_mlx.semantics.atlas.feature_io_storage.tempfile.mkdtemp",
                side_effect=OSError("disk unavailable"),
            ):
                with self.assertRaises(BilqisError) as caught:
                    persist_feature_manifest(_features(), root)
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_FEATURE_ARTIFACT_PUBLISH_FAILED")

    def test_initial_map_rejects_holes_and_early_overflow(self):
        base = _features()
        for invalid_row in (0, 3):
            forged = replace(
                base, type_map=tuple(
                    (identifier, invalid_row if identifier == "urn:type:Entity"
                     else row) for identifier, row in base.type_map))
            with self.subTest(row=invalid_row), TemporaryDirectory() as root:
                with self.assertRaises(BilqisError):
                    persist_feature_manifest(forged, root)

    def test_successor_requires_predecessor_proof_on_write_and_read(self):
        base = _features()
        successor = _features(
            replace(_snapshot((
                ("urn:concept:A", ("urn:type:!new", "urn:type:Entity")),),
                release="b" * 64), prior_abi_sha256=base.atlas_bundle_id),
            predecessor=base)
        with TemporaryDirectory() as root:
            with self.assertRaises(BilqisError):
                persist_feature_manifest(successor, root)
            receipt = persist_feature_manifest(
                successor, root, predecessor=base)
            with self.assertRaises(BilqisError):
                load_feature_manifest(receipt.path)
            self.assertEqual(
                load_feature_manifest(receipt.path, predecessor=base),
                successor)

    def test_cleanup_failure_never_leaks_raw_os_error(self):
        features = _features()
        with TemporaryDirectory() as root:
            with patch(
                "bilqis_mlx.semantics.atlas.feature_io_storage.Path.open",
                side_effect=OSError("write fail"),
            ), patch(
                "bilqis_mlx.semantics.atlas.feature_io_storage.shutil.rmtree",
                side_effect=OSError("cleanup fail"),
            ):
                with self.assertRaises(BilqisError) as caught:
                    persist_feature_manifest(features, root)
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_FEATURE_ARTIFACT_CLEANUP_FAILED")
