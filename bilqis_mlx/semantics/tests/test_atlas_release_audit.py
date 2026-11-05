"""A12 export clearance is source-owner signed and live-frontier bound."""
from dataclasses import replace
import json
from pathlib import Path
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_release_audit import (
    ExportClearanceReceipt, validate_export_clearance_context,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.context_eligibility import SourceFrontier
from bilqis_mlx.semantics.domains import contract_digest


PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("29" * 32))
PUBLIC = PRIVATE.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
OWNER = "fixture:a12-source-owner"
REGISTRY = SourceAuthorityRegistry((SourceAuthorityKey(
    OWNER, PUBLIC, (SourceAuthorityScope(DependencyKind.ARTIFACT, "a12-export:"),)),))


def _selection():
    path = Path(__file__).resolve().parents[1] / "atlas_source_pins_v1.json"
    entry = json.loads(path.read_text())["entries"][0]
    return AtlasArtifactSelection(
        "fixture-atlas", entry["bundle_id"], entry["release_sha256"],
        entry["source_bundle_id"])


def _receipt(selection, frontier, exported, *, private=(), revoked=(), lineage=()):
    receipt = ExportClearanceReceipt(
        OWNER, selection.bundle_id, selection.release_sha256,
        selection.source_bundle_id, contract_digest(frontier),
        frontier.rights_epoch, frontier.correction_generation,
        exported, private, revoked, lineage, "0" * 128)
    return replace(receipt, signature_hex=PRIVATE.sign(receipt.signing_bytes()).hex())


def _verify(receipt, selection, frontier, artifacts):
    REGISTRY.verify_detached(
        receipt.source_owner, receipt.dependency(),
        receipt.signature_hex, receipt.signing_bytes())
    return validate_export_clearance_context(receipt, selection, frontier, artifacts)


class AtlasExportClearanceTests(unittest.TestCase):
    def setUp(self):
        self.selection = _selection()
        self.frontier = SourceFrontier(7, 3, ())
        self.public = ("1" * 64, "2" * 64)
        self.receipt = _receipt(
            self.selection, self.frontier, self.public,
            private=("3" * 64,), revoked=("4" * 64,), lineage=("5" * 64,))

    def test_owner_signed_exact_export_is_accepted(self):
        self.assertEqual(
            _verify(self.receipt, self.selection, self.frontier, self.public),
            self.receipt.clearance_sha256)

    def test_caller_minted_matching_fields_do_not_gain_authority(self):
        forged = replace(self.receipt, signature_hex="0" * 128)
        with self.assertRaises(BilqisError):
            _verify(forged, self.selection, self.frontier, self.public)

    def test_stale_or_foreign_release_clearance_fails_closed(self):
        newer = SourceFrontier(8, 3, ())
        with self.assertRaises(BilqisError):
            _verify(self.receipt, self.selection, newer, self.public)
        foreign = replace(self.receipt, source_bundle_id="6" * 64)
        foreign = replace(
            foreign, signature_hex=PRIVATE.sign(foreign.signing_bytes()).hex())
        with self.assertRaises(BilqisError):
            _verify(foreign, self.selection, self.frontier, self.public)

    def test_private_revoked_or_mismatched_export_set_is_rejected(self):
        for artifacts in (("3" * 64,), ("4" * 64,), ("1" * 64,)):
            with self.subTest(artifacts=artifacts), self.assertRaises(BilqisError):
                _verify(self.receipt, self.selection, self.frontier, artifacts)

    def test_revocation_lineage_and_frontier_are_signature_bound(self):
        changed = replace(self.receipt, revocation_lineage=("6" * 64,))
        with self.assertRaises(BilqisError):
            _verify(changed, self.selection, self.frontier, self.public)


if __name__ == "__main__":
    unittest.main()
