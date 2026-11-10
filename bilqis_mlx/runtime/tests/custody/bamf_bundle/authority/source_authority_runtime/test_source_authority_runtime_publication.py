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
    accept_and_publish, bind_accepted_execution_cache, derive_successor_bundle,
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
    retention_decision,
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

    def publish(self, run_dir=None, *, generation=0, parent=None, state=None):
        run_dir = self.run if run_dir is None else Path(run_dir)
        source = candidate(parent_state())
        if state is not None or generation or parent is not None:
            source = candidate(
                parent_state() if state is None else state,
                generation=generation,
                parent=parent,
            )
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

    def test_host_genesis_publishes_ordinary_successor_without_run_local_registry(self):
        _source, pointer = self.publish()
        self.assertFalse((self.run / "source-authority-registry.json").exists())
        with shape_patch():
            parent = load_accepted_generation(self.run)
        retained = accepted_state(
            parent.retained_state, parent.extents, parent.topology)
        successor = derive_successor_bundle(
            parent, retained,
            parent_manifest_sha256=pointer["manifest_sha256"],
            delivery_events=({"event": "FIXTURE_ORDINARY_SUCCESSOR"},),
        )
        decision = retention_decision(
            parent=parent.retained_state, retained=retained)

        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            published = accept_and_publish(
                self.run, successor, retained,
                decision=decision,
                feature_sha256=successor.extents.factor_map_digest,
                reserve_gib=0.,
            )

        self.assertEqual(published["generation"], 1)
        self.assertFalse((self.run / "source-authority-registry.json").exists())
        with shape_patch():
            accepted = load_accepted_generation(self.run)
        self.assertEqual(
            accepted.correction_frontier["source_authority_registry_origin"],
            "HOST_SYSTEM_V1",
        )

    def test_direct_publication_cannot_bypass_host_source_authority_root(self):
        _source, pointer = self.publish()
        with shape_patch():
            parent = load_accepted_generation(self.run)
        retained = accepted_state(
            parent.retained_state, parent.extents, parent.topology)
        successor = derive_successor_bundle(
            parent, retained,
            parent_manifest_sha256=pointer["manifest_sha256"],
            delivery_events=({"event": "FIXTURE_DIRECT_PUBLICATION"},),
        )
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="source:drift"),))
        successor = replace(successor, correction_frontier={
            **successor.correction_frontier,
            "source_authority_registry_sha256": drift.digest,
            "source_authority_registry": self.registry_record(drift),
        })
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            with self.assertRaises(BilqisError) as caught:
                publish_bamf_generation(
                    self.run, successor,
                    acceptance=acceptance(
                        successor, parent=parent.retained_state),
                    reserve_gib=0.,
                )
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID",
        )

    def test_host_provisioned_registry_drift_rejects_existing_accepted_generation(self):
        self.publish()
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="source:drift"),))
        from bilqis_mlx.runtime.bamf_bundle import source_authority_custody as custody
        with shape_patch(), patch.object(
                custody, "read_host_system_source_authority_registry",
                return_value=drift), self.assertRaises(BilqisError) as caught:
            bind_accepted_execution_cache(self.run)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_MISMATCH",
        )

    def test_genesis_candidate_cannot_replace_host_provisioned_source_authority_root(self):
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="source:drift"),))
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
            "BAMF_INITIAL_GENERATION_BOOTSTRAP_REQUIRED",
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
