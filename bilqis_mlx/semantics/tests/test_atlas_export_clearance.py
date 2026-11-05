"""A12 export-clearance boundary tests."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.context_eligibility import SourceFrontier

from bilqis_mlx.semantics.tests.test_atlas_release_audit import (
    PRIVATE, _receipt, _selection, _verify,
)

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
