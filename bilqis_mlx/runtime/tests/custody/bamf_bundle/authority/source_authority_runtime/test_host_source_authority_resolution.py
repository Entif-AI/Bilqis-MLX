"""Accepted-custody branch resolution for C09 source authority."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import source_authority_custody as custody
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, parent_state, provision_source_authority_registry,
    with_source_authority_registry,
)
from bilqis_mlx.semantics.tests.core.test_atlas_export_clearance import REGISTRY


class SourceAuthorityResolverTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.run = Path(self.temporary.name) / "run"

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def host_frontier():
        return {
            "source_authority_registry_origin": custody.HOST_SYSTEM_SOURCE_AUTHORITY_ORIGIN,
            "source_authority_registry": REGISTRY.to_record(),
            "source_authority_registry_sha256": REGISTRY.digest,
        }

    def test_host_origin_revalidates_only_fixed_host_root(self):
        with patch.object(custody, "read_host_system_source_authority_registry",
                          return_value=REGISTRY):
            self.assertIs(custody.resolve_source_authority_registry(
                self.run, self.host_frontier()), REGISTRY)
        with patch.object(custody, "read_host_system_source_authority_registry",
                          return_value=Mock(digest="f" * 64)), \
                self.assertRaises(BilqisError) as caught:
            custody.resolve_source_authority_registry(self.run, self.host_frontier())
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_MISMATCH")

    def test_legacy_origin_absence_uses_run_local_root(self):
        provision_source_authority_registry(self.run, REGISTRY)
        frontier = with_source_authority_registry(
            candidate(parent_state()), REGISTRY).correction_frontier
        self.assertEqual(custody.resolve_source_authority_registry(self.run, frontier), REGISTRY)

    def test_historical_unanchored_returns_none_and_explicit_null_rejects(self):
        self.assertIsNone(custody.resolve_source_authority_registry(self.run, {}))
        with self.assertRaises(BilqisError) as caught:
            custody.resolve_source_authority_registry(
                self.run, {"source_authority_registry_origin": None})
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID")

    def test_successor_host_is_exact_and_cannot_downgrade(self):
        parent = self.host_frontier()
        with patch.object(custody, "read_host_system_source_authority_registry",
                          return_value=REGISTRY):
            self.assertIs(custody.require_source_authority_successor_inheritance(
                self.run, parent, dict(parent), allow_historical_anchor=False), REGISTRY)
        with self.assertRaises(BilqisError) as caught:
            custody.require_source_authority_successor_inheritance(
                self.run, parent, {}, allow_historical_anchor=False)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID")

    def test_historical_anchor_is_explicitly_permissioned(self):
        provision_source_authority_registry(self.run, REGISTRY)
        candidate_frontier = {
            "source_authority_registry": REGISTRY.to_record(),
            "source_authority_registry_sha256": REGISTRY.digest,
        }
        with self.assertRaises(BilqisError) as caught:
            custody.require_source_authority_successor_inheritance(
                self.run, {}, candidate_frontier, allow_historical_anchor=False)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID")
        self.assertEqual(custody.require_source_authority_successor_inheritance(
            self.run, {}, candidate_frontier, allow_historical_anchor=True), REGISTRY)


if __name__ == "__main__":
    unittest.main()
