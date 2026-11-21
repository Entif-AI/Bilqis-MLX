"""B13 accepted-authority checkpoint and protected-tip data-plane ownership."""
from __future__ import annotations

import hashlib
import sqlite3

from bilqis_mlx.data_plane import close_data_planes, data_plane
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_checkpoint import (
    compare_and_swap_protected_accepted_authority_tip,
    issue_accepted_authority_checkpoint,
    read_protected_accepted_authority_tip,
    require_accepted_authority_checkpoint,
    store_accepted_authority_checkpoint,
)

from .base import DataPlaneCase


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _checkpoint(
        generation: int, *, parent=None, kind: str | None = None,
        manifest_label: str | None = None, pointer_label: str | None = None):
    parent_fields = {}
    if parent is not None:
        parent_fields = {
            "parent_checkpoint_sha256": parent.digest,
            "parent_manifest_sha256": parent.manifest_sha256,
            "parent_acceptance_sha256": parent.acceptance_sha256,
            "parent_candidate_identity_sha256": parent.candidate_identity_sha256,
        }
    return issue_accepted_authority_checkpoint(
        run_id="run:accepted-authority",
        run_identity_sha256=_sha("run-identity"),
        generation=generation,
        manifest_sha256=_sha(manifest_label or f"manifest:{generation}"),
        acceptance_sha256=_sha(f"acceptance:{generation}"),
        pointer_sha256=_sha(pointer_label or f"pointer:{generation}"),
        acceptance_file_sha256=_sha(f"acceptance-file:{generation}"),
        candidate_identity_sha256=_sha(f"candidate:{generation}"),
        optimizer_step=generation * 10,
        topology_sha256=_sha("topology"),
        extents_sha256=_sha("extents"),
        implementation_sha256=_sha("implementation"),
        feature_receipt_sha256=_sha(f"feature-receipt:{generation}"),
        feature_artifact_sha256=_sha(f"feature-artifact:{generation}"),
        source_authority_registry_sha256=_sha("source-authority"),
        semantic_release_sha256=_sha("semantic-release"),
        atlas_bundle_sha256=_sha("atlas-bundle"),
        factory_release_sha256=_sha("factory-release"),
        genesis_trust_sha256=_sha("genesis-trust"),
        kind=kind or ("GENESIS" if generation == 0 else "INCREMENTAL"),
        **parent_fields,
    )


class AcceptedAuthorityCheckpointTests(DataPlaneCase):
    def test_schema_v2_upgrades_to_v3_with_checkpoint_tables(self):
        close_data_planes()
        path = self.root / "plane.sqlite3"
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL) WITHOUT ROWID")
        db.execute("INSERT INTO meta(key,value) VALUES('schema_version','2')")
        db.commit()
        db.close()

        plane = data_plane()

        self.assertEqual(
            plane._db.execute(
                "SELECT value FROM meta WHERE key='schema_version'").fetchone(),
            ("3",),
        )
        tables = {row[0] for row in plane._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("bamf_accepted_authority_checkpoints", tables)
        self.assertIn("bamf_accepted_authority_tips", tables)

    def test_checkpoint_rows_are_content_addressed_and_immutable(self):
        checkpoint = _checkpoint(0)
        digest = store_accepted_authority_checkpoint(checkpoint)
        plane = data_plane()
        row = plane._db.execute(
            "SELECT checkpoint_sha256,payload FROM bamf_accepted_authority_checkpoints"
        ).fetchone()
        self.assertEqual(row[0], digest)
        self.assertEqual(hashlib.sha256(row[1]).hexdigest(), digest)

        with self.assertRaisesRegex(
                sqlite3.IntegrityError, "BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_IMMUTABLE"):
            plane._db.execute(
                "UPDATE bamf_accepted_authority_checkpoints SET generation=1 "
                "WHERE checkpoint_sha256=?", (digest,))
        with self.assertRaisesRegex(
                sqlite3.IntegrityError, "BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_IMMUTABLE"):
            plane._db.execute(
                "DELETE FROM bamf_accepted_authority_checkpoints "
                "WHERE checkpoint_sha256=?", (digest,))

    def test_protected_tip_cas_advances_exact_parent_and_survives_restart(self):
        genesis = _checkpoint(0)
        store_accepted_authority_checkpoint(genesis)
        self.assertEqual(
            compare_and_swap_protected_accepted_authority_tip(
                genesis, expected_checkpoint_sha256=None),
            genesis.digest,
        )
        self.assertEqual(read_protected_accepted_authority_tip(genesis.run_id), genesis)

        close_data_planes()
        self.assertEqual(read_protected_accepted_authority_tip(genesis.run_id), genesis)

        child = _checkpoint(1, parent=genesis)
        store_accepted_authority_checkpoint(child)
        self.assertEqual(
            compare_and_swap_protected_accepted_authority_tip(
                child, expected_checkpoint_sha256=genesis.digest),
            child.digest,
        )
        self.assertEqual(
            require_accepted_authority_checkpoint(child.run_id, child.manifest_sha256),
            child,
        )
        self.assertEqual(
            compare_and_swap_protected_accepted_authority_tip(
                child, expected_checkpoint_sha256=genesis.digest),
            child.digest,
            "exact retry is idempotent even though its expected parent is now historical",
        )

    def test_stale_or_wrong_parent_checkpoint_cannot_advance_tip(self):
        genesis = _checkpoint(0)
        child = _checkpoint(1, parent=genesis)
        for checkpoint in (genesis, child):
            store_accepted_authority_checkpoint(checkpoint)
        compare_and_swap_protected_accepted_authority_tip(
            genesis, expected_checkpoint_sha256=None)
        compare_and_swap_protected_accepted_authority_tip(
            child, expected_checkpoint_sha256=genesis.digest)

        stale_child = _checkpoint(1, parent=genesis, manifest_label="stale-child")
        store_accepted_authority_checkpoint(stale_child)
        with self.assertRaises(BilqisError):
            compare_and_swap_protected_accepted_authority_tip(
                stale_child, expected_checkpoint_sha256=genesis.digest)
        self.assertEqual(read_protected_accepted_authority_tip(genesis.run_id), child)

        wrong_parent = _checkpoint(2, parent=genesis, manifest_label="wrong-parent")
        store_accepted_authority_checkpoint(wrong_parent)
        with self.assertRaises(BilqisError):
            compare_and_swap_protected_accepted_authority_tip(
                wrong_parent, expected_checkpoint_sha256=child.digest)
        self.assertEqual(read_protected_accepted_authority_tip(genesis.run_id), child)

    def test_generic_object_reference_cannot_forge_or_replace_protected_tip(self):
        genesis = _checkpoint(0)
        store_accepted_authority_checkpoint(genesis)
        compare_and_swap_protected_accepted_authority_tip(
            genesis, expected_checkpoint_sha256=None)
        plane = data_plane()
        forged = b'{"checkpoint_sha256":"forged"}'

        with self.assertRaisesRegex(
                ValueError, "BILQIS_DATA_PLANE_PROTECTED_REFERENCE_FORBIDDEN"):
            plane.put_object_reference(
                f"bamf-accepted-authority-tip-v1:{genesis.run_id}", forged)

        ordinary = plane.put_object_reference("accepted-history:fixture", forged)
        self.assertEqual(plane.get_object_reference("accepted-history:fixture")[0], ordinary)
        self.assertEqual(read_protected_accepted_authority_tip(genesis.run_id), genesis)

        with self.assertRaisesRegex(
                sqlite3.IntegrityError, "BAMF_ACCEPTED_AUTHORITY_TIP_UNOWNED"):
            plane._db.execute(
                "UPDATE bamf_accepted_authority_tips "
                "SET generation=1,checkpoint_sha256=? WHERE run_id=?",
                (_sha("generic-forged-tip"), genesis.run_id),
            )
        self.assertEqual(read_protected_accepted_authority_tip(genesis.run_id), genesis)

    def test_forged_checkpoint_digest_and_conflicting_manifest_are_rejected(self):
        plane = data_plane()
        raw = b'{"schema_version":"forged"}\n'
        with self.assertRaisesRegex(
                ValueError, "BILQIS_DATA_PLANE_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID"):
            plane._store_accepted_authority_checkpoint(
                "0" * 64, "run:forged", 0, "1" * 64, None, raw)

        genesis = _checkpoint(0)
        store_accepted_authority_checkpoint(genesis)
        conflicting = _checkpoint(
            0, manifest_label="manifest:0", pointer_label="different-pointer")
        self.assertEqual(conflicting.manifest_sha256, genesis.manifest_sha256)
        self.assertNotEqual(conflicting.digest, genesis.digest)
        with self.assertRaises(BilqisError):
            store_accepted_authority_checkpoint(conflicting)


if __name__ == "__main__":
    import unittest
    unittest.main()
