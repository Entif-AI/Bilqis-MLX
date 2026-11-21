import hashlib
import json
from types import SimpleNamespace

from .base import DataPlaneCase
from bilqis_mlx.data_plane import data_plane
from bilqis_mlx._data_plane.cli import _maintenance
from bilqis_mlx._data_plane.file_retention import file_gc_report
from bilqis_mlx._data_plane.maintenance import (
    maintenance_roots, register_maintenance_root,
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class DataPlaneStorageLifecycleTests(DataPlaneCase):
    def _file_object(self, payload: bytes) -> tuple[str, object]:
        plane = data_plane()
        digest = _sha(payload)
        path = plane.file_object_destination(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return digest, path

    def test_accepted_ancestry_does_not_pin_every_historical_tensor(self):
        plane = data_plane()
        tensors = [self._file_object(f"tensor-{index}".encode()) for index in range(16)]
        active_role_sha = tensors[4][0]
        parent = None

        for generation, (tensor_sha, _path) in enumerate(tensors):
            sidecars = {}
            if generation == 15:
                role_raw = _canonical({
                    "active_roles": {
                        "A.ROLE": {"checkpoint": {"sha256": active_role_sha}}
                    }
                })
                role_name = "championship-state.json"
                role_sha = _sha(role_raw)
                sidecars["championship_state"] = {
                    "filename": role_name,
                    "sha256": role_sha,
                    "object_sha256": role_sha,
                }
            manifest = _canonical({
                "schema": "bilqis.mlx.bamf-generation-bundle/v5",
                "generation": generation,
                "parent_manifest_sha256": parent,
                "tensors": {"object_sha256": tensor_sha},
                "sidecars": sidecars,
            })
            digest = _sha(manifest)
            bundle = self.root / "bamf-bundles" / digest
            bundle.mkdir(parents=True)
            (bundle / "manifest.json").write_bytes(manifest)
            if generation == 15:
                (bundle / role_name).write_bytes(role_raw)
            parent = digest

        (self.root / "bamf-state.json").write_text(json.dumps({
            "schema": "bilqis.mlx.bamf-generation-pointer/v2",
            "manifest_sha256": parent,
            "bundle": f"bamf-bundles/{parent}",
        }))

        report = file_gc_report(plane, (self.root,))

        self.assertEqual(report["reachable_file_objects"], 2)
        self.assertEqual(report["unreachable_file_objects"], 14)
        self.assertEqual(report["root_tiers"]["bamf_current"], 1)
        self.assertEqual(report["root_tiers"]["bamf_ancestry"], 15)

    def test_registered_shared_store_roots_are_all_preserved_for_maintenance(self):
        plane = data_plane()
        first = self.root / "first"
        second = self.root / "second"
        for root in (first, second):
            root.mkdir()
            (root / "bamf-state.json").write_text("{}")

        register_maintenance_root(plane, first)
        register_maintenance_root(plane, second)

        self.assertEqual(maintenance_roots(plane, first), (first.resolve(), second.resolve()))

    def test_explicit_rollback_root_keeps_its_current_tensor_only(self):
        plane = data_plane()
        tensors = [self._file_object(f"rollback-{index}".encode()) for index in range(3)]
        roots = []
        parent = None
        for generation, (tensor_sha, _path) in enumerate(tensors):
            manifest = _canonical({
                "schema": "bilqis.mlx.bamf-generation-bundle/v5",
                "generation": generation,
                "parent_manifest_sha256": parent,
                "tensors": {"object_sha256": tensor_sha},
                "sidecars": {},
            })
            digest = _sha(manifest)
            bundle = self.root / "bamf-bundles" / digest
            bundle.mkdir(parents=True)
            (bundle / "manifest.json").write_bytes(manifest)
            run = self.root / f"run-{generation}"
            run.mkdir()
            (run / "bamf-bundles").symlink_to(self.root / "bamf-bundles")
            (run / "bamf-state.json").write_text(json.dumps({
                "schema": "bilqis.mlx.bamf-generation-pointer/v2",
                "manifest_sha256": digest,
                "bundle": f"bamf-bundles/{digest}",
            }))
            roots.append(run)
            parent = digest

        report = file_gc_report(plane, (roots[2], roots[0]))

        self.assertEqual(report["reachable_file_objects"], 2)
        self.assertEqual(report["unreachable_file_objects"], 1)

    def test_transient_event_history_is_not_promoted_to_retention_root(self):
        plane = data_plane()
        primary = self.root / "runs" / "primary"
        transient = self.root / "transient"
        for root in (primary, transient):
            root.mkdir(parents=True)
            (root / "bamf-state.json").write_text("{}")
        (transient / "events.jsonl").write_text("")
        plane.sync_event_ledger(transient)

        self.assertEqual(maintenance_roots(plane, primary), (primary.resolve(),))

    def test_applied_maintenance_reclaims_then_converges(self):
        plane = data_plane()
        current_sha, current_path = self._file_object(b"current tensor")
        dead_sha, dead_path = self._file_object(b"dead tensor")
        manifest = _canonical({
            "schema": "bilqis.mlx.bamf-generation-bundle/v5",
            "generation": 0,
            "parent_manifest_sha256": None,
            "tensors": {"object_sha256": current_sha},
            "sidecars": {},
        })
        manifest_sha = _sha(manifest)
        bundle = self.root / "bamf-bundles" / manifest_sha
        bundle.mkdir(parents=True)
        (bundle / "manifest.json").write_bytes(manifest)
        plane.put_node(manifest_sha, manifest, 0, None)
        dead_object = b'{"dead":"archive"}'
        plane.put_object(_sha(dead_object), dead_object)
        (self.root / "bamf-state.json").write_text(json.dumps({
            "schema": "bilqis.mlx.bamf-generation-pointer/v2",
            "manifest_sha256": manifest_sha,
            "bundle": f"bamf-bundles/{manifest_sha}",
        }))
        args = SimpleNamespace(
            scan_root=[self.root], apply=True, scope="all",
            max_records=0, vacuum=False,
        )

        first = _maintenance(args)
        second = _maintenance(args)

        self.assertTrue(current_path.exists())
        self.assertFalse(dead_path.exists())
        self.assertEqual(first["gc"]["unreachable_objects"], 1)
        self.assertEqual(first["file_gc"]["unreachable_file_objects"], 1)
        self.assertIn("objects", first["compaction"])
        self.assertEqual(second["gc"]["unreachable_objects"], 0)
        self.assertEqual(second["file_gc"]["unreachable_file_objects"], 0)
        self.assertNotIn("compaction", second)


if __name__ == "__main__":
    import unittest
    unittest.main()
