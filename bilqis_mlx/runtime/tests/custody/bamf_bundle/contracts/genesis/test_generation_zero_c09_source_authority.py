"""C16.1c binds independently provisioned C09 trust into generation zero."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.data_plane import close_data_planes
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityRegistry, require_source_authority_runtime,
)
from bilqis_mlx.runtime.bamf_bundle import publish_initial_generation
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
    _reset_execution_cache_owner_for_tests,
)
from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
from bilqis_mlx.runtime.bamf_bundle import source_authority_custody as custody
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    genesis_preparation, provision_source_authority_registry, shape_patch,
)
from bilqis_mlx.semantics.tests.core.test_atlas_export_clearance import REGISTRY


class GenerationZeroC09SourceAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        _reset_execution_cache_owner_for_tests()
        close_data_planes()
        self.environment.stop()
        self.temporary.cleanup()

    def _prepared(self):
        with shape_patch():
            return genesis_preparation(run_seed=950)

    def _publish(self, prepared, *, host_registry=REGISTRY):
        with shape_patch(), patch.object(
                custody, "read_host_system_source_authority_registry",
                return_value=host_registry), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_initial_generation(self.run, prepared, reserve_gib=0.)

    def test_host_registry_binds_genesis_and_cold_host_issues_opaque_runtime(self):
        prepared = self._prepared()
        correction = prepared.candidate.correction_frontier
        self.assertEqual(correction["source_authority_registry_origin"], "HOST_SYSTEM_V1")
        self.assertEqual(correction["source_authority_registry_sha256"], REGISTRY.digest)
        self.assertEqual(
            SourceAuthorityRegistry.from_record(
                correction["source_authority_registry"]),
            REGISTRY,
        )
        self._publish(prepared)
        self.assertFalse((self.run / "source-authority-registry.json").exists())

        _reset_execution_cache_owner_for_tests()
        close_data_planes()
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
            authority = AcceptedRuntimeHost(self.run).source_authority()
            rebound = AcceptedRuntimeHost(self.run).source_authority()
            self.assertEqual(cache.source_authority_registry_sha256, REGISTRY.digest)
            self.assertIs(require_source_authority_runtime(authority, cache), authority)
            self.assertIs(rebound, authority)

    def test_generation_zero_cannot_be_prepared_without_host_binding(self):
        prepared = self._prepared()
        correction = prepared.candidate.correction_frontier
        self.assertEqual(set((
            "source_authority_registry_origin",
            "source_authority_registry",
            "source_authority_registry_sha256",
        )) - set(correction), set())

    def test_host_registry_drift_rejects_before_generation_zero_pointer(self):
        prepared = self._prepared()
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="fixture:drift-owner"),))
        with self.assertRaises(BilqisError) as failure:
            self._publish(prepared, host_registry=drift)

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_MISMATCH",
        )
        self.assertFalse((self.run / "bamf-state.json").exists())
        self.assertFalse((self.run / "bamf-bundles").exists())

    def test_attacker_preplaced_run_local_registry_cannot_select_genesis_authority(self):
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="fixture:attacker-owner"),))
        provision_source_authority_registry(self.run, drift)
        prepared = self._prepared()
        correction = prepared.candidate.correction_frontier
        self.assertEqual(
            SourceAuthorityRegistry.from_record(correction["source_authority_registry"]),
            REGISTRY,
        )
        self._publish(prepared)
        _reset_execution_cache_owner_for_tests()
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
        self.assertEqual(cache.source_authority_registry_sha256, REGISTRY.digest)


if __name__ == "__main__":
    unittest.main()
