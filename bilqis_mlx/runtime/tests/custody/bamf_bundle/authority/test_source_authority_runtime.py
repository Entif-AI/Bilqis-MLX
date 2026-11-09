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
from bilqis_mlx.runtime.bamf_bundle import load_bamf_bundle
from bilqis_mlx.runtime.bamf_bundle.admission import (
    bind_accepted_correction_authority,
    bind_accepted_execution_cache,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state,
    candidate,
    parent_state,
    publish_candidate,
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
                state=None):
        run_dir = self.run if run_dir is None else Path(run_dir)
        source = candidate(parent_state())
        if state is not None or generation or parent is not None:
            source = candidate(
                parent_state() if state is None else state,
                generation=generation,
                parent=parent,
            )
        if anchored:
            source = replace(source, correction_frontier={
                **source.correction_frontier,
                "source_authority_registry_sha256": REGISTRY.digest,
            })
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            pointer = publish_candidate(run_dir, source)
        return source, pointer

    def test_accepted_host_issues_and_reuses_opaque_source_authority(self):
        self.publish()
        with shape_patch():
            cache = bind_accepted_correction_authority(self.run, REGISTRY)
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

    def test_source_authority_anchor_enters_after_authenticated_genesis(self):
        _source, pointer = self.publish()
        self.assertEqual(pointer["generation"], 1)
        parent_sha = pointer["parent_manifest_sha256"]
        self.assertIsNotNone(parent_sha)
        with shape_patch():
            parent = load_bamf_bundle(
                self.run / "bamf-bundles" / parent_sha,
                expected_manifest_sha256=parent_sha)
            current = load_bamf_bundle(
                self.run / pointer["bundle"],
                expected_manifest_sha256=pointer["manifest_sha256"])
        self.assertEqual(parent.generation, 0)
        self.assertIsNone(parent.parent_manifest_sha256)
        self.assertNotIn(
            "source_authority_registry_sha256", parent.correction_frontier)
        self.assertEqual(current.generation, 1)
        self.assertEqual(
            current.correction_frontier["source_authority_registry_sha256"],
            REGISTRY.digest)
        self.assertEqual(current.run_identity, parent.run_identity)

    def test_attacker_first_registry_cannot_poison_the_accepted_cache(self):
        self.publish()
        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="source:drift"),))
        with shape_patch():
            with self.assertRaises(BilqisError):
                bind_accepted_correction_authority(self.run, drift)
            cache = bind_accepted_execution_cache(self.run)
            self.assertIsNone(cache._correction_registry)
            bind_accepted_correction_authority(self.run, REGISTRY)
            self.assertIs(AcceptedRuntimeHost(self.run).registry, REGISTRY)

    def test_legacy_sidecar_is_readable_but_cannot_mint_source_authority(self):
        self.publish(anchored=False)
        with shape_patch():
            cache = bind_accepted_execution_cache(self.run)
            self.assertIsNone(cache.source_authority_registry_sha256)
            with self.assertRaises(BilqisError):
                bind_accepted_correction_authority(self.run, REGISTRY)

    def test_foreign_same_registry_capability_rejects_against_other_run_cache(self):
        other = self.root / "other-run"
        self.publish()
        self.publish(other)
        with shape_patch():
            cache = bind_accepted_correction_authority(self.run, REGISTRY)
            foreign_cache = bind_accepted_correction_authority(other, REGISTRY)
            authority = AcceptedRuntimeHost(self.run).source_authority()
            with self.assertRaises(BilqisError):
                require_source_authority_runtime(authority, foreign_cache)
        self.assertIs(require_source_authority_runtime(authority, cache), authority)

    def test_stale_generation_capability_rejects_after_accepted_advance(self):
        _source, pointer = self.publish()
        with shape_patch():
            old_cache = bind_accepted_correction_authority(self.run, REGISTRY)
            authority = AcceptedRuntimeHost(self.run).source_authority()
        successor_state = accepted_state(parent_state())
        self.publish(
            generation=1, parent=pointer["manifest_sha256"], state=successor_state)
        with shape_patch():
            current_cache = bind_accepted_correction_authority(self.run, REGISTRY)
            with self.assertRaises(BilqisError):
                require_source_authority_runtime(authority, current_cache)
        self.assertIs(require_source_authority_runtime(authority, old_cache), authority)

    def test_caller_cannot_construct_or_forge_source_authority_runtime(self):
        self.publish()
        with shape_patch():
            cache = bind_accepted_correction_authority(self.run, REGISTRY)
        with self.assertRaises(BilqisError):
            require_source_authority_runtime(REGISTRY, cache)
        with self.assertRaises(BilqisError):
            SourceAuthorityRuntime()
        forged = object.__new__(SourceAuthorityRuntime)
        with self.assertRaises(BilqisError):
            require_source_authority_runtime(forged, cache)


if __name__ == "__main__":
    unittest.main()
