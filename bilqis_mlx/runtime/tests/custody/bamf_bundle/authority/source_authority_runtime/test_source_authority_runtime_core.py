"""Accepted-run custody for opaque C09 source authority."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
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
from bilqis_mlx.runtime.bamf_bundle.admission import (
    bind_accepted_execution_cache, derive_successor_bundle,
    load_accepted_generation,
)
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.records import canonical
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state,
    acceptance,
    candidate,
    parent_state,
    publish_candidate,
    provision_source_authority_registry,
    shape_patch,
    with_source_authority_registry,
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

    def publish(self, run_dir=None, *, anchored=True, generation=0, parent=None,
                state=None, registry=REGISTRY):
        run_dir = self.run if run_dir is None else Path(run_dir)
        source = candidate(parent_state())
        if state is not None or generation or parent is not None:
            source = candidate(
                parent_state() if state is None else state,
                generation=generation,
                parent=parent,
            )
        if anchored:
            provision_source_authority_registry(run_dir, registry)
            source = with_source_authority_registry(source, registry)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            pointer = publish_candidate(run_dir, source)
        return source, pointer

    @staticmethod
    def registry_record(registry):
        return {
            "schema_version": registry.schema_version,
            "keys": [
                {
                    "owner_id": key.owner_id,
                    "public_key_hex": key.public_key_hex,
                    "schema_version": key.schema_version,
                    "allowed_scopes": [
                        {
                            "kind": scope.kind.value,
                            "key_prefix": scope.key_prefix,
                            "schema_version": scope.schema_version,
                        }
                        for scope in key.allowed_scopes
                    ],
                }
                for key in registry.keys
            ],
        }

    def test_accepted_host_issues_and_reuses_opaque_source_authority(self):
        self.publish()
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
            authority = AcceptedRuntimeHost(self.run).source_authority()
            rebound = AcceptedRuntimeHost(self.run).source_authority()
        self.assertIs(require_source_authority_runtime(authority, cache), authority)
        self.assertIs(rebound, authority)
        selection = _selection()
        frontier = SourceFrontier(7, 3, ())
        artifacts = ("1" * 64, "2" * 64)
        receipt = _receipt(selection, frontier, artifacts)
        self.assertEqual(
            authority._validate_export_clearance_context(
                cache, receipt, selection, frontier, artifacts),
            receipt.clearance_sha256,
        )
        with self.assertRaises(BilqisError):
            authority._validate_export_clearance_context(
                cache, receipt, selection, SourceFrontier(8, 3, ()), artifacts)

    def test_concurrent_accepted_hosts_reuse_one_source_authority(self):
        self.publish()
        from bilqis_mlx.runtime.atlas_source_authority import (
            _provision_source_authority_runtime,
        )
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
        with ThreadPoolExecutor(max_workers=8) as pool:
            authorities = tuple(pool.map(
                lambda _index: _provision_source_authority_runtime(cache),
                range(16),
            ))
        self.assertTrue(all(authority is authorities[0] for authority in authorities))

    def test_execution_cache_has_no_importable_credential_issuer(self):
        from bilqis_mlx.runtime.bamf_bundle import accepted_runtime
        from bilqis_mlx.runtime.bamf_bundle import execution_cache
        self.assertFalse(hasattr(execution_cache, "_issue_accepted_execution_cache"))
        self.assertFalse(hasattr(accepted_runtime, "_EXECUTION_CACHE_OWNER"))
        self.assertFalse(hasattr(accepted_runtime, "_ExecutionCacheOwner"))

    def test_source_authority_trust_root_has_no_runtime_provisioner(self):
        from bilqis_mlx.runtime.bamf_bundle import source_authority_custody
        self.assertFalse(
            hasattr(source_authority_custody, "provision_source_authority_registry"))

    def test_c09_runtime_exposes_no_retained_registry_owner(self):
        from bilqis_mlx.runtime import accepted_corrections
        from bilqis_mlx.runtime import accepted_correction_runtime
        self.assertFalse(hasattr(accepted_corrections, "_RUNTIME_OWNER"))
        self.assertFalse(hasattr(accepted_correction_runtime, "_RUNTIME_OWNER"))

    def test_c09_does_not_manufacture_b14_cache_authority(self):
        from bilqis_mlx.runtime import accepted_corrections
        from bilqis_mlx.runtime.bamf_bundle import accepted_runtime, admission, execution_cache
        self.assertFalse(hasattr(accepted_runtime, "bind_accepted_cache_authority"))
        self.assertFalse(hasattr(accepted_runtime, "interactive_accepted_cache_inference"))
        self.assertFalse(hasattr(admission, "bind_accepted_cache_authority"))
        self.assertFalse(hasattr(admission, "interactive_accepted_cache_inference"))
        self.assertFalse(hasattr(execution_cache, "bind_cache_authority"))
        self.assertFalse(hasattr(accepted_corrections.AcceptedRuntimeHost, "cache_inference"))

    def test_public_c09_facade_exposes_no_raw_registry_mutation_helpers(self):
        from bilqis_mlx.runtime import atlas_revalidation
        for name in (
            "apply_capability_support_correction",
            "apply_compiled_batch_correction",
            "apply_motif_correction",
            "apply_solve_context_correction",
        ):
            self.assertFalse(hasattr(atlas_revalidation, name), name)
