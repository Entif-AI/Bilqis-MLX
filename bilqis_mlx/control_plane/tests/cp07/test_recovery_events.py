"""CP04 restart and stale-cursor proof for portable rejection history."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint

from bilqis_mlx.control_plane import ControlPlaneClient, ControlPlaneService, EventFamily
from bilqis_mlx.control_plane.native_source import native_query_catalog
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryMode, QueryRequest
from bilqis_mlx.runtime.atlas_source_authority import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation, record_bamf_rejection
from bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer import HostSourceAuthoritySigner
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    publish_genesis, retention_decision, shape_patch,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

from ..support import start_service
from .native_source_support import NativeSourceFixture


_PRIVATE = "44" * 32


def _registry():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    public = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(_PRIVATE)).public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw).hex()
    scopes = tuple(sorted((SourceAuthorityScope(kind, prefix) for kind, prefix in (
        (DependencyKind.POLICY, "salience-policy:"),
        (DependencyKind.SOURCE, "salience-fact:"),
        (DependencyKind.ARTIFACT, "salience-option:"),
        (DependencyKind.ARTIFACT, "salience-event:"),
    )), key=lambda scope: (scope.kind.value, scope.key_prefix)))
    return SourceAuthorityRegistry((SourceAuthorityKey("owner:c06", public, scopes),))


class PortableRejectionEventRecoveryTests(NativeSourceFixture, unittest.TestCase):
    def test_restart_keeps_signed_rejection_snapshot_and_expires_old_cursor(self):
        registry = _registry()
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            self._parent_pointer = publish_genesis(
                self.run, source_authority_registry=registry)
        with shape_patch():
            self._parent = load_bamf_generation(self.run / "bamf-state.json")
        parent = self._parent
        before = (self.run / "bamf-state.json").read_bytes()
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.accepted_execution_cache."
                "_accepted_source_authority_registry", return_value=registry):
            visit = self.native_visit(parent)
        decision = retention_decision(
            accepted=False, parent=parent.retained_state, retained=parent.retained_state)

        socket = self.root / "portable-rejection.sock"
        service = ControlPlaneService(
            self.run, socket, event_heartbeat_seconds=0.01,
            event_retention_limit=16, event_queue_limit=16)
        thread = start_service(service)
        try:
            with ControlPlaneClient(socket) as client:
                subscription = client.subscribe_events()
                signer = HostSourceAuthoritySigner("owner:c06", _PRIVATE, registry)
                with patch(
                        "bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer."
                        "read_host_system_source_authority_signer", return_value=signer):
                    record_bamf_rejection(self.run, parent, {
                        "schema": "bilqis.bamf.c16.3-rejection/v2",
                        "visit_id": visit.visit_id, "teacher_visit": visit.to_record(),
                        "selected_option_id": "option:portable",
                        "selected_policy_key": visit.policy_key,
                        "candidate_optimizer_step": parent.retained_state.optimizer_step + 1,
                        "retained_optimizer_step": parent.retained_state.optimizer_step,
                        "retention_reason": decision.reason, "capability": visit.capability_id,
                        "decision": decision.to_record(),
                    })
                rejected = None
                for _ in range(4):
                    observed = next(subscription)
                    if observed.event_family == EventFamily.CANDIDATE_REJECTED.value:
                        rejected = observed
                        break
                self.assertIsNotNone(rejected)
                old_cursor = rejected.position.cursor_sha256
        finally:
            service.shutdown()
            thread.join(2)

        restarted = ControlPlaneService(
            self.run, socket, query_source=lambda: native_query_catalog(self.run))
        restart_thread = start_service(restarted)
        try:
            with ControlPlaneClient(socket) as client:
                page = client.query(QueryRequest(
                    QueryFamily.EPISODE, mode=QueryMode.HISTORICAL,
                    run_id=parent.run_id, generation=0))
                self.assertTrue(any(
                    row.get("outcome") == "REJECTED" for row in page["records"]),
                    page["records"])
                replay = client.subscribe_events(after_cursor=old_cursor)
                self.assertEqual(replay.gap["state"], "fresh-snapshot-required")
        finally:
            restarted.shutdown()
            restart_thread.join(2)
        self.assertEqual((self.run / "bamf-state.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
