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
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.admission import (
    bind_accepted_execution_cache,
)
from bilqis_mlx.runtime.bamf_bundle.records import canonical
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state,
    acceptance,
    candidate,
    parent_state,
    provision_source_authority_registry,
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
            source = replace(source, correction_frontier={
                **source.correction_frontier,
                "source_authority_registry_sha256": registry.digest,
                "source_authority_registry": self.registry_record(registry),
            })
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            pointer = publish_bamf_generation(
                run_dir, source, acceptance=acceptance(source))
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

    def test_successor_cannot_replace_accepted_source_authority_root(self):
        _source, pointer = self.publish()
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="source:drift"),))
        successor = candidate(
            accepted_state(parent_state()),
            generation=1,
            parent=pointer["manifest_sha256"],
        )
        successor = replace(successor, correction_frontier={
            **successor.correction_frontier,
            "source_authority_registry_sha256": drift.digest,
            "source_authority_registry": self.registry_record(drift),
        })
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            with self.assertRaises(BilqisError):
                publish_bamf_generation(
                    self.run, successor, acceptance=acceptance(successor))

    def test_host_provisioned_registry_drift_rejects_existing_accepted_generation(self):
        self.publish()
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="source:drift"),))
        with self.assertRaises(BilqisError) as caught:
            provision_source_authority_registry(self.run, drift)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_IMMUTABLE",
        )

    def test_genesis_candidate_cannot_replace_host_provisioned_source_authority_root(self):
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="source:drift"),))
        provision_source_authority_registry(self.run, REGISTRY)
        source = candidate(parent_state())
        source = replace(source, correction_frontier={
            **source.correction_frontier,
            "source_authority_registry_sha256": drift.digest,
            "source_authority_registry": self.registry_record(drift),
        })
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            with self.assertRaises(BilqisError) as caught:
                publish_bamf_generation(
                    self.run, source, acceptance=acceptance(source))
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_MISMATCH",
        )
        self.assertFalse((self.run / "bamf-state.json").exists())

    def test_attacker_first_registry_cannot_poison_the_accepted_cache(self):
        self.publish()
        from bilqis_mlx.runtime.bamf_bundle import admission
        with shape_patch():
            self.assertFalse(hasattr(admission, "bind_accepted_correction_authority"))
            cache = bind_accepted_execution_cache(self.run)
            self.assertEqual(cache._correction_registry, REGISTRY)
            authority = AcceptedRuntimeHost(self.run).source_authority()
            self.assertIs(require_source_authority_runtime(authority, cache), authority)

    def test_owned_cache_cannot_replace_registry_and_digest_after_binding(self):
        self.publish()
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="source:drift"),))
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
            object.__setattr__(cache, "_correction_registry", drift)
            object.__setattr__(
                cache, "source_authority_registry_sha256", drift.digest)
            from bilqis_mlx.runtime.atlas_source_authority import (
                _provision_source_authority_runtime,
            )
            with self.assertRaises(BilqisError):
                _provision_source_authority_runtime(cache)

    def test_bound_cache_rechecks_current_host_registry_before_authority_use(self):
        self.publish()
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="source:drift"),))
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
            authority = AcceptedRuntimeHost(self.run).source_authority()
            from bilqis_mlx.runtime.bamf_bundle.source_authority_custody import (
                SOURCE_AUTHORITY_REGISTRY_FILE,
            )
            (self.run / SOURCE_AUTHORITY_REGISTRY_FILE).write_bytes(
                canonical(drift.to_record()))
            with self.assertRaises(BilqisError):
                require_source_authority_runtime(authority, cache)

    def test_legacy_sidecar_is_readable_but_cannot_mint_source_authority(self):
        self.publish(anchored=False)
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
            self.assertIsNone(cache.source_authority_registry_sha256)
            with self.assertRaises(BilqisError):
                AcceptedRuntimeHost(self.run)

    def test_foreign_same_registry_capability_rejects_against_other_run_cache(self):
        other = self.root / "other-run"
        self.publish()
        self.publish(other)
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
            foreign_cache = bind_accepted_execution_cache(other)
            authority = AcceptedRuntimeHost(self.run).source_authority()
            with self.assertRaises(BilqisError):
                require_source_authority_runtime(authority, foreign_cache)
        self.assertIs(require_source_authority_runtime(authority, cache), authority)

    def test_stale_generation_capability_rejects_after_accepted_advance(self):
        _source, pointer = self.publish()
        with shape_patch():
            old_cache = bind_accepted_execution_cache(self.run)
            authority = AcceptedRuntimeHost(self.run).source_authority()
        successor_state = accepted_state(parent_state())
        self.publish(
            generation=1, parent=pointer["manifest_sha256"], state=successor_state)
        with shape_patch():
            with self.assertRaises(BilqisError):
                require_source_authority_runtime(authority, old_cache)
            current_cache = bind_accepted_execution_cache(self.run)
            with self.assertRaises(BilqisError):
                require_source_authority_runtime(authority, current_cache)

    def test_cache_install_cannot_race_past_accepted_pointer_advance(self):
        from bilqis_mlx.runtime.bamf_bundle import accepted_runtime

        _source, pointer = self.publish()
        successor = candidate(
            accepted_state(parent_state()), generation=1,
            parent=pointer["manifest_sha256"])
        successor = replace(successor, correction_frontier={
            **successor.correction_frontier,
            "source_authority_registry_sha256": REGISTRY.digest,
            "source_authority_registry": self.registry_record(REGISTRY),
        })
        successor_acceptance = acceptance(successor)
        entered = Event()
        release = Event()
        original = accepted_runtime._accepted_source_authority_registry

        def paused_registry(run_dir, student):
            registry = original(run_dir, student)
            entered.set()
            self.assertTrue(release.wait(5))
            return registry

        with shape_patch(), patch.object(
                mlx_checkpoint, "assert_headroom"), patch.object(
                accepted_runtime, "_accepted_source_authority_registry",
                side_effect=paused_registry), ThreadPoolExecutor(max_workers=2) as pool:
            bind_future = pool.submit(bind_accepted_execution_cache, self.run)
            self.assertTrue(entered.wait(5))
            publish_future = pool.submit(
                publish_bamf_generation, self.run, successor,
                acceptance=successor_acceptance)
            self.assertFalse(publish_future.done())
            release.set()
            old_cache = bind_future.result(timeout=5)
            publish_future.result(timeout=5)

        with shape_patch(), self.assertRaises(BilqisError) as caught:
            from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
                require_accepted_execution_cache,
            )
            require_accepted_execution_cache(old_cache)
        self.assertEqual(caught.exception.context["reason"], "B13_EXECUTION_CACHE_STALE")

    def test_caller_cannot_construct_or_forge_source_authority_runtime(self):
        self.publish()
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
        with self.assertRaises(BilqisError):
            require_source_authority_runtime(REGISTRY, cache)
        with self.assertRaises(BilqisError):
            SourceAuthorityRuntime()
        forged = object.__new__(SourceAuthorityRuntime)
        with self.assertRaises(BilqisError):
            require_source_authority_runtime(forged, cache)


if __name__ == "__main__":
    unittest.main()
