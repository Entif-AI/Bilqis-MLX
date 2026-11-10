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
from bilqis_mlx.runtime.bamf_bundle.records import canonical
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

    def _prepared(self, *, run_dir=None):
        with shape_patch():
            return genesis_preparation(
                run_seed=950,
                source_authority_run_dir=(self.run if run_dir is None else run_dir),
            )

    def _publish(self, prepared):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_initial_generation(self.run, prepared, reserve_gib=0.)

    def test_host_registry_binds_genesis_and_cold_host_issues_opaque_runtime(self):
        provision_source_authority_registry(self.run, REGISTRY)
        prepared = self._prepared()
        correction = prepared.candidate.correction_frontier
        self.assertEqual(correction["source_authority_registry_sha256"], REGISTRY.digest)
        self.assertEqual(
            SourceAuthorityRegistry.from_record(
                correction["source_authority_registry"]),
            REGISTRY,
        )
        self._publish(prepared)

        _reset_execution_cache_owner_for_tests()
        close_data_planes()
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
            authority = AcceptedRuntimeHost(self.run).source_authority()
            rebound = AcceptedRuntimeHost(self.run).source_authority()

        self.assertEqual(cache.source_authority_registry_sha256, REGISTRY.digest)
        self.assertIs(require_source_authority_runtime(authority, cache), authority)
        self.assertIs(rebound, authority)

    def test_host_file_without_generation_zero_binding_cannot_mint_runtime(self):
        provision_source_authority_registry(self.run, REGISTRY)
        with shape_patch():
            unbound = genesis_preparation(run_seed=951)
        self._publish(unbound)

        _reset_execution_cache_owner_for_tests()
        with shape_patch(), self.assertRaises(BilqisError) as failure:
            AcceptedRuntimeHost(self.run)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_BINDING_REQUIRED",
        )

    def test_host_registry_drift_rejects_before_generation_zero_pointer(self):
        provision_source_authority_registry(self.run, REGISTRY)
        prepared = self._prepared()
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="fixture:drift-owner"),))
        registry_path = self.run / "source-authority-registry.json"
        registry_path.write_bytes(canonical(drift.to_record()))

        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                self.assertRaises(BilqisError) as failure:
            publish_initial_generation(self.run, prepared, reserve_gib=0.)

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT",
        )
        self.assertFalse((self.run / "bamf-state.json").exists())
        self.assertFalse((self.run / "bamf-bundles").exists())

    def test_prepared_host_root_cannot_be_replayed_into_another_run(self):
        provision_source_authority_registry(self.run, REGISTRY)
        prepared = self._prepared()
        other = self.root / "other"
        provision_source_authority_registry(other, REGISTRY)

        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                self.assertRaises(BilqisError) as failure:
            publish_initial_generation(other, prepared, reserve_gib=0.)

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_RUN_IDENTITY_DRIFT",
        )
        self.assertFalse((other / "bamf-state.json").exists())


if __name__ == "__main__":
    unittest.main()
