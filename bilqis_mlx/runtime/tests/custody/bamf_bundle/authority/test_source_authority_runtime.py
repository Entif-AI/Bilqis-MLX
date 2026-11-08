"""Accepted-run custody for opaque C09 source authority."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityRegistry,
    SourceAuthorityRuntime,
    require_source_authority_runtime,
)
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance,
    candidate,
    parent_state,
    shape_patch,
)
from bilqis_mlx.semantics.context_eligibility import SourceFrontier
from bilqis_mlx.semantics.tests.core.test_atlas_export_clearance import (
    REGISTRY,
    _receipt,
    _selection,
)


class SourceAuthorityRuntimeCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self):
        source = candidate(parent_state())
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            publish_bamf_generation(
                self.run, source, acceptance=acceptance(source))

    def test_accepted_host_issues_and_reuses_opaque_source_authority(self):
        self.publish()
        with shape_patch():
            authority = AcceptedRuntimeHost(
                self.run, REGISTRY).source_authority()
            rebound = AcceptedRuntimeHost(
                self.run, REGISTRY).source_authority()
        self.assertIs(require_source_authority_runtime(authority), authority)
        self.assertIs(rebound, authority)
        selection = _selection()
        frontier = SourceFrontier(7, 3, ())
        artifacts = ("1" * 64, "2" * 64)
        receipt = _receipt(selection, frontier, artifacts)
        self.assertEqual(
            authority._validate_export_clearance_context(
                receipt, selection, frontier, artifacts),
            receipt.clearance_sha256,
        )
        with self.assertRaises(BilqisError):
            authority._validate_export_clearance_context(
                receipt, selection, SourceFrontier(8, 3, ()), artifacts)

    def test_registry_drift_rejects_before_a_second_runtime_is_issued(self):
        self.publish()
        with shape_patch():
            AcceptedRuntimeHost(self.run, REGISTRY).source_authority()
            drift = SourceAuthorityRegistry((replace(
                REGISTRY.keys[0], owner_id="source:drift"),))
            with self.assertRaises(BilqisError):
                AcceptedRuntimeHost(self.run, drift).source_authority()

    def test_caller_cannot_construct_or_forge_source_authority_runtime(self):
        with self.assertRaises(BilqisError):
            require_source_authority_runtime(REGISTRY)
        with self.assertRaises(BilqisError):
            SourceAuthorityRuntime()
        forged = object.__new__(SourceAuthorityRuntime)
        with self.assertRaises(BilqisError):
            require_source_authority_runtime(forged)


if __name__ == "__main__":
    unittest.main()
