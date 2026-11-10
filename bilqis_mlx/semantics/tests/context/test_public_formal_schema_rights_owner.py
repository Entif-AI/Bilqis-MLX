"""A13 owner continuity for PUBLIC_FORMAL motif-schema rights."""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import inspect
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, TaskScope,
)
from bilqis_mlx.semantics.frame_adapters.common import (
    BOOLEAN_CONNECTIVE_ADAPTER,
)
from bilqis_mlx.semantics.frame_adapters.public_formal import public_formal_context
import bilqis_mlx.semantics.frame_adapters.public_formal_schema_rights as rights
import bilqis_mlx.semantics.frame_adapters.public_formal_schema_rights_registry as registry
from bilqis_mlx.semantics.frame_schema import FrameInstance
from bilqis_mlx.source_adapters.school import A_ORACLE, live_source_registry


REAL_BUNDLE = "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"
REAL_RELEASE = "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306"
REAL_SOURCE_BUNDLE = "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec"


@unittest.skipUnless(
    os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
    "real repo-pinned A01 artifact supplied at source turn-in",
)
class PublicFormalSchemaRightsOwnerTests(unittest.TestCase):
    def setUp(self):
        self.selection = AtlasArtifactSelection(
            os.environ["BILQIS_ATLAS_REAL_ARTIFACT"],
            REAL_BUNDLE, REAL_RELEASE, REAL_SOURCE_BUNDLE)
        self.source_root = Path(__file__).resolve().parents[4] / "vendor/legacy-v16"
        self.graph = read_sources(self.source_root)[2]
        self.adapter = live_source_registry().require(
            "bilqis_mlx.grade_a_probe.make_record", A_ORACLE)
        self.row = self.adapter.draw(
            source_root=self.source_root, graph=self.graph, course=None,
            capability="A.IDENTITY", seed=31, each=2)[0]
        self.task = TaskScope(
            "synthetic:principal", "synthetic:tenant", "TRAINING", REAL_RELEASE,
            "synthetic:region", "synthetic:public", 3, 5, 30)
        self.policy = ContextPolicy(
            "synthetic:policy", 1, 1, ("TRAINING",), (PUBLIC_FORMAL,),
            ("synthetic:region",), ("synthetic:public",), (PUBLIC_FORMAL,),
            ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
            tuple((PUBLIC_FORMAL,) * count for count in range(3, 25)))
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.registry_dir = Path(self.temporary.name)
        root = registry._REGISTRY_DIR / (registry._ROOT_REGISTRY_SHA256 + ".json")
        (self.registry_dir / root.name).write_bytes(root.read_bytes())
        self.original_registry_dir = registry._REGISTRY_DIR
        self.original_registry_sha = registry._REGISTRY_SHA256
        self.addCleanup(setattr, registry, "_REGISTRY_DIR", self.original_registry_dir)
        self.addCleanup(setattr, registry, "_REGISTRY_SHA256", self.original_registry_sha)
        registry._REGISTRY_DIR = self.registry_dir
        registry._REGISTRY_SHA256 = registry._ROOT_REGISTRY_SHA256

    def _payload(self, digest):
        return json.loads((self.registry_dir / (digest + ".json")).read_text())

    def _append(self, parent_digest, mutate):
        payload = copy.deepcopy(self._payload(parent_digest))
        payload["predecessor_registry_sha256"] = parent_digest
        mutate(payload)
        raw = (json.dumps(
            payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
        digest = hashlib.sha256(raw).hexdigest()
        (self.registry_dir / (digest + ".json")).write_bytes(raw)
        registry._REGISTRY_SHA256 = digest
        return digest

    def _projection(self, authority):
        policy = replace(self.policy, rights_epoch=authority.rights_epoch)
        result = public_formal_context(
            self.adapter, self.row, load_pinned_atlas_snapshot(self.selection),
            source_root=self.source_root, graph=self.graph,
            task_scope=self.task,
            source_frontier=rights.source_schema_rights_frontier(authority),
            policy=policy, source_seed=31, source_each=2)
        self.assertIsInstance(result, tuple)
        projection, _frontier = result
        frame = next(
            envelope.frame for envelope in projection.envelopes
            if isinstance(envelope.frame, FrameInstance))
        return projection, frame

    def _target(self):
        authority = rights.issue_source_schema_rights_authority(self.selection)
        projection, frame = self._projection(authority)
        grant = rights.current_source_schema_grant(
            authority, self.adapter.descriptor.adapter_id, projection, frame)
        return frame, grant.source_handle

    @staticmethod
    def _entry(payload, schema_id):
        return next(entry for entry in payload["entries"]
                    if entry["schema_id"] == schema_id)

    def _revoke(self, parent_digest, frame):
        def mutate(payload):
            self._entry(payload, frame.frame_schema_id)["decisions"].append({
                "action": "REVOKE", "rights_epoch": payload["rights_epoch"],
            })
        return self._append(parent_digest, mutate)

    def test_same_epoch_revocation_survives_fresh_and_cold_owner_reissue(self):
        frame, _handle = self._target()
        revoked_digest = self._revoke(registry._REGISTRY_SHA256, frame)
        first = rights.issue_source_schema_rights_authority(self.selection)
        projection, current_frame = self._projection(first)
        first_grant = rights.current_source_schema_grant(
            first, self.adapter.descriptor.adapter_id, projection, current_frame)
        self.assertEqual(first.registry_sha256, revoked_digest)
        self.assertTrue(first_grant.revoked)

        identity = rights.source_schema_rights_identity(first)
        cold = rights.validate_source_schema_rights_identity(identity, self.selection)
        cold_projection, cold_frame = self._projection(cold)
        cold_grant = rights.current_source_schema_grant(
            cold, self.adapter.descriptor.adapter_id, cold_projection, cold_frame)
        self.assertEqual(cold_grant, first_grant)
        self.assertTrue(cold_grant.revoked)

    def test_same_epoch_and_correction_only_unrevoke_fail_closed(self):
        frame, _handle = self._target()
        revoked = self._revoke(registry._REGISTRY_SHA256, frame)

        def same_epoch_unrevoke(payload):
            self._entry(payload, frame.frame_schema_id)["decisions"].append({
                "action": "ISSUE", "rights_epoch": 1,
            })
        self._append(revoked, same_epoch_unrevoke)
        with self.assertRaises(BilqisError):
            rights.issue_source_schema_rights_authority(self.selection)

        registry._REGISTRY_SHA256 = revoked
        def erased_revoke(payload):
            payload["correction_generation"] = 2
            entry = self._entry(payload, frame.frame_schema_id)
            entry["decisions"] = entry["decisions"][:-1]
        self._append(revoked, erased_revoke)
        with self.assertRaises(BilqisError):
            rights.issue_source_schema_rights_authority(self.selection)

    def test_correction_advance_stays_revoked_and_later_owner_epoch_can_restore(self):
        frame, _handle = self._target()
        revoked = self._revoke(registry._REGISTRY_SHA256, frame)
        correction = self._append(
            revoked, lambda payload: payload.__setitem__("correction_generation", 2))
        authority = rights.issue_source_schema_rights_authority(self.selection)
        projection, current_frame = self._projection(authority)
        grant = rights.current_source_schema_grant(
            authority, self.adapter.descriptor.adapter_id, projection, current_frame)
        self.assertEqual(authority.registry_sha256, correction)
        self.assertEqual(grant.correction_generation, 2)
        self.assertTrue(grant.revoked)

        def restore(payload):
            payload["rights_epoch"] = 2
            self._entry(payload, frame.frame_schema_id)["decisions"].append({
                "action": "ISSUE", "rights_epoch": 2,
            })
        restored_digest = self._append(correction, restore)
        restored = rights.issue_source_schema_rights_authority(self.selection)
        restored_projection, restored_frame = self._projection(restored)
        restored_grant = rights.current_source_schema_grant(
            restored, self.adapter.descriptor.adapter_id,
            restored_projection, restored_frame)
        self.assertEqual(restored.registry_sha256, restored_digest)
        self.assertEqual(restored_grant.rights_epoch, 2)
        self.assertEqual(restored_grant.correction_generation, 2)
        self.assertFalse(restored_grant.revoked)

    def test_grant_materialization_requires_actual_approved_source_frame(self):
        authority = rights.issue_source_schema_rights_authority(self.selection)
        projection, frame = self._projection(authority)
        parameters = inspect.signature(rights.current_source_schema_grant).parameters
        self.assertNotIn("task_scope", parameters)
        self.assertNotIn("policy", parameters)
        self.assertNotIn("schema_id", parameters)
        self.assertNotIn("revision", parameters)
        with self.assertRaises(BilqisError):
            rights.SourceSchemaRightsAuthority()
        with self.assertRaises(BilqisError):
            rights.current_source_schema_grant(
                authority, BOOLEAN_CONNECTIVE_ADAPTER, projection, frame)

    def test_registry_evidence_cannot_drift_from_a03(self):
        frame, _handle = self._target()
        def forge(payload):
            self._entry(payload, frame.frame_schema_id)["evidence_sha256"] = "f" * 64
        self._append(registry._REGISTRY_SHA256, forge)
        with self.assertRaises(BilqisError):
            rights.issue_source_schema_rights_authority(self.selection)


if __name__ == "__main__":
    unittest.main()
