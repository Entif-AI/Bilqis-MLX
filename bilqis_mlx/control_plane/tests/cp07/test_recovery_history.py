"""BAMF-0.3 portable history and reconstruction regressions."""
from __future__ import annotations

import json
import importlib
import shutil
from dataclasses import replace
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint

from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.control_plane.native_source import (
    authenticated_history, materialize_native_projection,
)
from bilqis_mlx.control_plane.native_contracts import native_outbox_event_id, sha
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.mission_control import CandidateDecision
from bilqis_mlx.mission_control.projection import MissionControlProjection
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryMode, QueryRequest
from bilqis_mlx.runtime.atlas_source_authority import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation, publish_bamf_generation, record_bamf_rejection,
)
from bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer import (
    HostSourceAuthoritySigner,
)
from bilqis_mlx.runtime.bamf_bundle.codec import save_bamf_bundle
from bilqis_mlx.runtime.bamf_bundle.records import (
    BAMF_POINTER_SCHEMA, OBJECTIVE_ACCEPTANCE_BOUND_BAMF_BUNDLE_SCHEMA,
    OBJECTIVE_BOUND_BAMF_BUNDLE_SCHEMA, canonical,
)
from bilqis_mlx.runtime.bamf_bundle.rejection import portable_rejection_receipt
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, accepted_state, candidate, next_accepted_step, publish_genesis,
    retention_decision, shape_patch,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

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


class MissionControlRecoveryHistoryTests(NativeSourceFixture, unittest.TestCase):
    def _publish_signed_rejection(self):
        registry = _registry()
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            self._parent_pointer = publish_genesis(
                self.run, source_authority_registry=registry)
        with shape_patch():
            self._parent = load_bamf_generation(self.run / "bamf-state.json")
        parent = self._parent
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.accepted_execution_cache."
                "_accepted_source_authority_registry", return_value=registry):
            visit = self.native_visit(parent)
        decision = retention_decision(
            accepted=False, parent=parent.retained_state, retained=parent.retained_state)
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
        return registry, parent, visit

    def _migrated_parent_history(self, *, downgrade_to_v2: bool):
        parent = self.parent()
        generation_one = replace(
            candidate(
                accepted_state(parent.retained_state, parent.extents),
                1, self._parent_pointer["manifest_sha256"]),
            run_identity=parent.run_identity,
            implementation_sha256=parent.implementation_sha256,
            topology=parent.topology,
            extents=parent.extents,
            provenance=parent.provenance,
            semantic_abi=dict(parent.semantic_abi),
            compiler_features=dict(parent.compiler_features),
            correction_frontier=dict(parent.correction_frontier),
            teacher_state=dict(parent.teacher_state),
            evaluation_contract=dict(parent.evaluation_contract),
        )
        successor_state = next_accepted_step(
            generation_one.retained_state, generation_one.extents)
        stage = self.run / "historical-parent-stage"
        with shape_patch(), patch.object(
                mlx_checkpoint, "assert_headroom"), patch(
                "bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom"):
            manifest = save_bamf_bundle(generation_one, stage)
        self.assertEqual(manifest["schema"], OBJECTIVE_BOUND_BAMF_BUNDLE_SCHEMA)
        if downgrade_to_v2:
            record = json.loads((stage / "manifest.json").read_text())
            record["schema"] = "bilqis.mlx.bamf-generation-bundle/v2"
            record.pop("training_objective_ref")
            record.pop("training_objective_digest")
            raw = canonical(record)
            manifest_sha256 = sha(raw)
            (stage / "manifest.json").write_bytes(raw)
            data_plane().put_node(
                manifest_sha256, raw, generation_one.generation,
                generation_one.parent_manifest_sha256)
            manifest = {**record, "manifest_sha256": manifest_sha256}
        target = self.run / "bamf-bundles" / manifest["manifest_sha256"]
        stage.rename(target)
        accepted_one = acceptance(generation_one, parent=parent.retained_state)
        acceptance_dir = self.run / "bamf-acceptance"
        (acceptance_dir / f"{manifest['manifest_sha256']}.json").write_bytes(
            canonical(accepted_one.to_record()))
        pointer = {
            "schema": BAMF_POINTER_SCHEMA,
            "run_id": generation_one.run_id,
            "generation": 1,
            "parent_manifest_sha256": generation_one.parent_manifest_sha256,
            "bundle": f"bamf-bundles/{manifest['manifest_sha256']}",
            "manifest_sha256": manifest["manifest_sha256"],
            "acceptance_sha256": accepted_one.digest,
        }
        (self.run / "bamf-state.json").write_bytes(canonical(pointer))
        with shape_patch():
            historical_parent = load_bamf_generation(self.run / "bamf-state.json")
        generation_two = replace(
            candidate(
                successor_state, 2, manifest["manifest_sha256"]),
            run_identity=historical_parent.run_identity,
            implementation_sha256=historical_parent.implementation_sha256,
            topology=historical_parent.topology,
            extents=historical_parent.extents,
            provenance=historical_parent.provenance,
            semantic_abi=dict(historical_parent.semantic_abi),
            compiler_features=dict(historical_parent.compiler_features),
            correction_frontier=dict(historical_parent.correction_frontier),
            teacher_state=dict(historical_parent.teacher_state),
            evaluation_contract=dict(historical_parent.evaluation_contract),
        )
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            child = publish_bamf_generation(
                self.run, generation_two,
                acceptance=acceptance(
                    generation_two, parent=historical_parent.retained_state),
                reserve_gib=0.)
        child_manifest = json.loads(
            (self.run / child["bundle"] / "manifest.json").read_text())
        self.assertEqual(
            child_manifest["schema"], OBJECTIVE_ACCEPTANCE_BOUND_BAMF_BUNDLE_SCHEMA)
        return authenticated_history(self.run)

    def test_migrated_v2_parent_reconstructs_complete_history(self):
        history = self._migrated_parent_history(downgrade_to_v2=True)
        self.assertEqual([item.manifest["generation"] for item in history], [0, 1, 2])
        self.assertEqual(history[1].manifest["schema"], "bilqis.mlx.bamf-generation-bundle/v2")

    def test_migrated_v4_parent_reconstructs_complete_history(self):
        history = self._migrated_parent_history(downgrade_to_v2=False)
        self.assertEqual([item.manifest["generation"] for item in history], [0, 1, 2])
        self.assertEqual(history[1].manifest["schema"], OBJECTIVE_BOUND_BAMF_BUNDLE_SCHEMA)

    def test_signed_rejection_survives_relocation_without_shared_data_plane(self):
        _registry_value, _parent, visit = self._publish_signed_rejection()
        relocated = self.root / "relocated-run"
        shutil.copytree(self.run, relocated)

        with patch(
                "bilqis_mlx.data_plane.data_plane",
                side_effect=AssertionError("portable reconstruction used shared data plane")):
            material = materialize_native_projection(relocated)
        rejected = [
            row for row in material.records
            if isinstance(row, CandidateDecision) and row.outcome.value == "REJECTED"
        ]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].capability_id, visit.capability_id)

    def test_signed_rejection_on_current_acceptance_binds_c09_registry(self):
        registry = _registry()
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            self._parent_pointer = publish_genesis(
                self.run, source_authority_registry=registry)
        with shape_patch():
            self._parent = load_bamf_generation(self.run / "bamf-state.json")
        custody = importlib.import_module(
            "bilqis_mlx.runtime.bamf_bundle.source_authority_custody")
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.accepted_execution_cache."
                "_accepted_source_authority_registry", return_value=registry), patch.object(
                custody, "resolve_source_authority_registry",
                return_value=registry):
            _source, pointer = self.publish_successor()
        with shape_patch():
            parent = load_bamf_generation(self.run / "bamf-state.json")
        self.assertEqual(pointer["generation"], 1)
        history = authenticated_history(self.run)
        self.assertEqual(
            history[-1].manifest["schema"], OBJECTIVE_ACCEPTANCE_BOUND_BAMF_BUNDLE_SCHEMA)
        self.assertEqual(history[-1].acceptance["source_authority_registry_sha256"], registry.digest)
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.accepted_execution_cache."
                "_accepted_source_authority_registry", return_value=registry):
            visit = self.native_visit(parent)
        decision = retention_decision(
            accepted=False, parent=parent.retained_state, retained=parent.retained_state)
        signer = HostSourceAuthoritySigner("owner:c06", _PRIVATE, registry)
        with patch(
                "bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer."
                "read_host_system_source_authority_signer", return_value=signer):
            record_bamf_rejection(self.run, parent, {
                "schema": "bilqis.bamf.c16.3-rejection/v2", "visit_id": visit.visit_id,
                "teacher_visit": visit.to_record(), "selected_option_id": "option:current",
                "selected_policy_key": visit.policy_key,
                "candidate_optimizer_step": parent.retained_state.optimizer_step + 1,
                "retained_optimizer_step": parent.retained_state.optimizer_step,
                "retention_reason": decision.reason, "capability": visit.capability_id,
                "decision": decision.to_record(),
            })
        with patch("bilqis_mlx.data_plane.data_plane", side_effect=AssertionError):
            material = materialize_native_projection(self.run)
        rejected = [
            row for row in material.records
            if isinstance(row, CandidateDecision) and row.outcome.value == "REJECTED"
        ]
        self.assertEqual([(row.meta.run.generation, row.outcome.value) for row in rejected], [(1, "REJECTED")])

    def test_rehashed_bad_signature_cannot_replace_last_good_cp06_projection(self):
        _registry_value, parent, _visit = self._publish_signed_rejection()
        pointer_before = (self.run / "bamf-state.json").read_bytes()
        index = self.root / "portable-rejection.sqlite3"
        projection = MissionControlProjection.rebuild_from_bamf(index, self.run)
        request = QueryRequest(
            QueryFamily.EPISODE, mode=QueryMode.HISTORICAL,
            run_id=parent.run_id, generation=0)
        before = projection.catalog().query(request)
        rejected = next(row for row in before.records if isinstance(row, CandidateDecision))
        self.assertEqual(rejected.outcome.value, "REJECTED")

        ledger = self.run / "events.jsonl"
        rows = [json.loads(line) for line in ledger.read_text().splitlines()]
        event = next(row for row in rows if row.get("event") == "BAMF_CANDIDATE_REJECTED")
        authority = event["rejection_authority"]
        signature = authority["source_signature_hex"]
        authority["source_signature_hex"] = signature[:-1] + ("0" if signature[-1] != "0" else "1")
        authority_sha = sha(canonical(authority))
        event["rejection_authority_sha256"] = authority_sha
        receipt = portable_rejection_receipt(
            run_id=parent.run_id, generation=0,
            student_manifest_sha256=event["student_manifest_sha256"],
            optimizer_step=event["optimizer_step"], authority_sha256=authority_sha)
        event["rejection_receipt_sha256"] = sha(canonical(receipt))
        payload = {key: value for key, value in event.items() if key != "event_id"}
        event["event_id"] = native_outbox_event_id(parent.run_id, 0, 0, payload)
        ledger.write_bytes(b"".join(canonical(row) for row in rows))

        with self.assertRaises(BilqisError) as caught:
            MissionControlProjection.rebuild_from_bamf(index, self.run)
        self.assertEqual(
            caught.exception.context.get("reason"),
            "CONTROL_PLANE_NATIVE_REJECTION_AUTHORITY_DRIFT")
        self.assertEqual(MissionControlProjection(index).catalog().query(request), before)
        self.assertEqual((self.run / "bamf-state.json").read_bytes(), pointer_before)
