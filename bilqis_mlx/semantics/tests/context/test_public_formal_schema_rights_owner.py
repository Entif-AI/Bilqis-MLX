"""A13 owner continuity for PUBLIC_FORMAL motif-schema rights."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.context_eligibility import SourceFrontier
from bilqis_mlx.semantics.frame_adapters.common import MICRO_PREDICATE_ADAPTER
from bilqis_mlx.semantics.frame_adapters.public_formal import public_formal_context
import bilqis_mlx.semantics.frame_adapters.public_formal_schema_rights as rights
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE


SCHEMA_ID = "frame:legacy:micro.compare.EQ"


@unittest.skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class PublicFormalSchemaRightsOwnerTests(unittest.TestCase):
    def _context(self):
        from bilqis_mlx.learning._engram.tests.test_atlas_engram_source import (
            SourceQualifiedMotifTests,
        )
        case = SourceQualifiedMotifTests()._case("A")
        (selection, source_root, graph, adapter, row, task, policy,
         seed, each, profile) = case
        args = {
            "source_root": source_root, "source_seed": seed,
            "source_each": each, "source_profile_parameters": profile,
        }
        return selection, task, policy, adapter, row, graph, args

    def _registry(self, *, revoked, rights_epoch=1, correction_generation=1):
        selection, _task, _policy, *_rest = self._context()
        baseline = json.loads(rights._REGISTRY.read_text())
        baseline["rights_epoch"] = rights_epoch
        baseline["correction_generation"] = correction_generation
        for entry in baseline["entries"]:
            if entry["schema_id"] == SCHEMA_ID:
                entry["revoked"] = revoked
        baseline["atlas_bundle_id"] = selection.bundle_id
        baseline["semantic_release"] = selection.release_sha256
        baseline["source_bundle_id"] = selection.source_bundle_id
        return baseline

    def _authority(self, payload):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "schema-rights.json"
        raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
        path.write_bytes(raw)
        selection, _task, _policy, *_rest = self._context()
        patches = (
            patch.object(rights, "_REGISTRY", path),
            patch.object(rights, "_REGISTRY_SHA256", hashlib.sha256(raw).hexdigest()),
        )
        for active in patches:
            active.start()
            self.addCleanup(active.stop)
        return selection, rights.issue_source_schema_rights_authority(selection)

    def test_same_epoch_revocation_survives_fresh_and_cold_owner_reissue(self):
        selection, task, policy, *_rest = self._context()
        payload = self._registry(revoked=True)
        _selection, first = self._authority(payload)
        first_frontier = rights.source_schema_rights_frontier(first)
        first_grant = rights.current_source_schema_grant(
            first, MICRO_PREDICATE_ADAPTER, SCHEMA_ID, 1,
            task_scope=task, policy=policy)
        self.assertEqual(first_frontier, SourceFrontier(1, 1, ()))
        self.assertTrue(first_grant.revoked)

        identity = rights.source_schema_rights_identity(first)
        cold = rights.validate_source_schema_rights_identity(identity, selection)
        cold_grant = rights.current_source_schema_grant(
            cold, MICRO_PREDICATE_ADAPTER, SCHEMA_ID, 1,
            task_scope=task, policy=policy)
        self.assertEqual(cold_grant, first_grant)
        self.assertTrue(cold_grant.revoked)

    def test_correction_advance_preserves_revocation_and_later_rights_epoch_can_restore(self):
        selection, task, policy, adapter, row, graph, args = self._context()
        _selection, correction = self._authority(
            self._registry(revoked=True, correction_generation=2))
        correction_frontier = rights.source_schema_rights_frontier(correction)
        projection, projected_frontier = public_formal_context(
            adapter, row, load_pinned_atlas_snapshot(selection),
            source_root=args["source_root"], graph=graph,
            task_scope=task, source_frontier=correction_frontier,
            policy=policy, source_seed=args["source_seed"],
            source_each=args["source_each"],
            source_profile_parameters=args["source_profile_parameters"],
        )
        correction_grant = rights.current_source_schema_grant(
            correction, MICRO_PREDICATE_ADAPTER, SCHEMA_ID, 1,
            task_scope=task, policy=policy)
        self.assertEqual(correction_frontier.correction_generation, 2)
        self.assertTrue(all(
            envelope.correction_generation == 2
            for envelope in projection.envelopes))
        self.assertEqual(projected_frontier.correction_generation, 2)
        self.assertEqual(correction_grant.correction_generation, 2)
        self.assertTrue(correction_grant.revoked)

        with self.assertRaises(BilqisError):
            rights.current_source_schema_grant(
                correction, MICRO_PREDICATE_ADAPTER, SCHEMA_ID, 1,
                task_scope=task,
                policy=replace(policy, rights_epoch=2),
            )

        _selection, restored = self._authority(
            self._registry(revoked=False, rights_epoch=2, correction_generation=2))
        restored_policy = replace(policy, rights_epoch=2)
        restored_frontier = rights.source_schema_rights_frontier(restored)
        restored_projection, restored_frame_frontier = public_formal_context(
            adapter, row, load_pinned_atlas_snapshot(selection),
            source_root=args["source_root"], graph=graph,
            task_scope=task, source_frontier=restored_frontier,
            policy=restored_policy, source_seed=args["source_seed"],
            source_each=args["source_each"],
            source_profile_parameters=args["source_profile_parameters"],
        )
        restored_grant = rights.current_source_schema_grant(
            restored, MICRO_PREDICATE_ADAPTER, SCHEMA_ID, 1,
            task_scope=task, policy=restored_policy)
        self.assertTrue(all(
            envelope.rights_epoch == 2
            and envelope.correction_generation == 2
            for envelope in restored_projection.envelopes))
        self.assertEqual(restored_frame_frontier.rights_epoch, 2)
        self.assertEqual(restored_grant.rights_epoch, 2)
        self.assertEqual(restored_grant.correction_generation, 2)
        self.assertFalse(restored_grant.revoked)

    def test_caller_construction_and_forged_registry_evidence_fail_closed(self):
        selection, task, policy, *_rest = self._context()
        with self.assertRaises(BilqisError):
            rights.SourceSchemaRightsAuthority()

        payload = self._registry(revoked=False)
        for entry in payload["entries"]:
            if entry["schema_id"] == SCHEMA_ID:
                entry["evidence_sha256"] = "f" * 64
        _selection, authority = self._authority(payload)
        with self.assertRaises(BilqisError):
            rights.current_source_schema_grant(
                authority, MICRO_PREDICATE_ADAPTER, SCHEMA_ID, 1,
                task_scope=task, policy=policy)


if __name__ == "__main__":
    unittest.main()
