"""DETACHED_ONLY real-source C05 proof for BAMF-native fixed-school custody."""
from __future__ import annotations

BILQIS_LEAF_GATE_POLICY = "DETACHED_ONLY"

from dataclasses import asdict
import json
import os
from pathlib import Path
import secrets
import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.accepted_teacher_custody import (
    derive_c03_successor_bundle,
)
from bilqis_mlx.runtime.admission import _executable_factory_admission
from bilqis_mlx.runtime.bamf_bundle import (
    authenticate_bamf_execution_feature_context, record_bamf_rejection,
)
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
    _reset_execution_cache_owner_for_tests,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, load_accepted_generation,
)
from bilqis_mlx.runtime.bamf_first_student import BamfFoundationConfig, preflight_bamf_foundation
from bilqis_mlx.runtime.mlx_memory import training_memory_policy
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import (
    C05_TRAINING_LEARNING_RATE, HP, live_factory_context,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest
from bilqis_mlx.runtime.tests.custody.bamf_bundle.publication.publication_helpers import (
    host_source_authority_patch,
)
from bilqis_mlx.semantics.atlas.feature_io import persist_feature_manifest
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactIdentity, resolve_atlas_artifact_selection
from bilqis_mlx.state_dag import persist
from .bamf_c16_2c_witness_support import (
    C03_FIXTURE_SEED_OFFSET, CAPABILITY, accepted_witness_receipt,
    cold_probe, finalize_witness_receipt, next_update_receipt,
    real_candidate_step,
)
from .c16_2c_resource_preflight import require_mlx_verification_resources

PROCESS_NONCE = secrets.token_hex(16)


class BamfNativeC05LiveTests(unittest.TestCase):
    def setUp(self):
        stage_root = os.environ.get("BILQIS_C16_2C_STAGE_ROOT")
        if not stage_root:
            self.skipTest("BILQIS_C16_2C_STAGE_ROOT is required for staged live proof")
        raw = os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
        if not raw or not Path(raw).is_dir():
            self.fail("BILQIS_A01_ATLAS_BUNDLE fixture is required for staged live proof")
        self.resource_preflight = require_mlx_verification_resources()
        self.memory_policy = training_memory_policy(mx)
        self.memory_policy_receipt = self.memory_policy.__enter__()
        self.addCleanup(self.memory_policy.__exit__, None, None, None)
        self.artifact = Path(raw).resolve()
        self.repo = Path.cwd()
        self.source = (self.repo / "vendor/legacy-v16").resolve()
        self.context, _ = live_factory_context(self.repo, self.source)
        atlas = json.loads((self.artifact / "atlas.json").read_text())
        self.identity = AtlasArtifactIdentity(
            self.artifact.name, atlas["release_sha256"], atlas["source_bundle_id"])
        self.root = Path(stage_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.data_plane = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.data_plane.start()
        self.addCleanup(self.data_plane.stop)

    def _foundation(self, name="target"):
        source_run, target = self.root / f"source-{name}", self.root / name
        origin = Checkpoint("7" * 64, "bundles/foundation-origin", 0, True)
        _, release_file, admission = _executable_factory_admission(
            source_run, self.context.release, origin,
            _fingerprint(self.context.graph), self.context.graph)
        persist(source_run, {
            "generation": 0,
            "factory_release_sha256": self.context.release.release_sha256,
            "factory_release_file": release_file,
            "factory_admission_v2": asdict(admission),
            "semantic_graph_sha256": _fingerprint(self.context.graph),
            "school": {"current_student": asdict(origin)},
            "result": "READY_FOR_HUMAN_START",
        })
        config = BamfFoundationConfig(
            source_run_dir=str(source_run), run_id=f"c05-bamf-native-live-{name}",
            run_seed=993, semantic_graph=self.context.graph,
            atlas_artifact=self.identity, optimizer_hyperparameters=HP)
        with host_source_authority_patch():
            preflight_bamf_foundation(config, self.context.release, target)
        parent = load_accepted_generation(target)
        accepted = AcceptedRuntimeHost(target).source_context(
            graph=self.context.graph, source_root=self.source)
        feature = authenticate_bamf_execution_feature_context(
            parent, str(self.artifact), target)
        feature_root = self.root / "features"
        feature_receipt = persist_feature_manifest(feature.features, feature_root)
        return target, parent, accepted, feature_receipt.path

    def test_c16_2c_stage_real_rejection_records_rollback_without_parent_mutation(self):
        with host_source_authority_patch():
            target, parent, context, feature_path = self._foundation("rejection")
            pointer_before = (target / "bamf-state.json").read_bytes()
            bundle = target / json.loads(pointer_before)["bundle"]
            parent_files_before = tuple(
                (str(path.relative_to(bundle)), path.read_bytes())
                for path in sorted(bundle.rglob("*")) if path.is_file())
            optimizer_before = retained_digest(parent.retained_state)
            _bound, _rows, step, evaluation, decision = real_candidate_step(
                target, parent, context, feature_path, self.artifact,
                learning_rate=1e-5)
            self.assertFalse(decision.accepted)
            self.assertEqual(decision.reason, "PROTECTED_CAPABILITY_REGRESSION")
            self.assertEqual(evaluation.decision.blocking_capability, "B.AND")
            retained = resolve_candidate(step.transaction, accepted=False)
            self.assertIs(retained, step.transaction.parent)
            rejection_sha = record_bamf_rejection(target, parent, {
                "schema": "bilqis.mlx.c16.2c-rejection-evidence/v1",
                "candidate_sha256": evaluation.candidate_candidate_sha256,
                "decision_evidence_sha256": decision.evidence_sha256,
                "decision_policy_sha256": decision.policy_sha256,
                "reason": decision.reason,
                "target_capability": CAPABILITY,
                "blocking_capability": evaluation.decision.blocking_capability,
            })
            self.assertEqual(len(rejection_sha), 64)
            _reset_execution_cache_owner_for_tests()
            cold = load_accepted_generation(target)
            self.assertEqual((target / "bamf-state.json").read_bytes(), pointer_before)
            self.assertEqual(retained_digest(cold.retained_state), optimizer_before)
            self.assertEqual(cold.retained_state.optimizer_step, 0)
            self.assertEqual(tuple(
                (str(path.relative_to(bundle)), path.read_bytes())
                for path in sorted(bundle.rglob("*")) if path.is_file()),
                parent_files_before)

    def test_c16_2c_stage_second_admitted_family_traverses_source_c03_c05_chain(self):
        capability = "A.IDENTITY"
        with host_source_authority_patch():
            target, parent, context, feature_path = self._foundation("second-family")
            bound, rows, step, evaluation, decision = real_candidate_step(
                target, parent, context, feature_path, self.artifact,
                learning_rate=C05_TRAINING_LEARNING_RATE,
                capability=capability)
            self.assertEqual(bound.identity.capability_id, capability)
            self.assertEqual(
                step.transaction.training_authorities[0].delivery_capability,
                capability)
            self.assertEqual(
                step.transaction.training_authorities[0].release_sha256,
                context.release.release_sha256)
            self.assertTrue(rows)
            self.assertIsNotNone(evaluation.decision)
            self.assertEqual(len(decision.evidence_sha256), 64)
            self.assertEqual(len(decision.policy_sha256), 64)
            self.assertFalse((target / "state.json").exists())
            receipt = {
                "schema": "bilqis.mlx.c16.2c-second-family-stage/v1",
                "capability": capability,
                "visit": bound.identity.to_record(),
                "training_authority_sha256":
                    step.transaction.training_authorities[0].digest,
                "factory_release_sha256": context.release.release_sha256,
                "c05_decision": decision.to_record(),
            }
            (self.root / "c16.2c-second-family-stage.json").write_text(
                json.dumps(receipt, sort_keys=True, separators=(",", ":")),
                encoding="utf-8")

    def test_c16_2c_stage_accepts_generation_one_and_records_uninterrupted_next_update(self):
        with host_source_authority_patch():
            target, parent, context, feature_path = self._foundation("accepted")
            bound, rows, step, _evaluation, decision = real_candidate_step(
                target, parent, context, feature_path, self.artifact,
                learning_rate=C05_TRAINING_LEARNING_RATE)
            self.assertTrue(decision.accepted)
            retained = resolve_candidate(step.transaction, accepted=True)
            successor = derive_c03_successor_bundle(
                target, retained, bound,
                next_seed=bound.identity.selection_seed + C03_FIXTURE_SEED_OFFSET,
                cursor=rows[0]["id"],
                delivery_events=({
                    "event": "BAMF_C16_2C_ACCEPTED",
                    "optimizer_step": retained.optimizer_step,
                },),
            )
            published = accept_and_publish(
                target, successor, retained, decision=decision,
                feature_sha256=successor.extents.factor_map_digest,
                training_authorities=step.transaction.training_authorities)
            self.assertEqual(published["generation"], 1)
            self.assertFalse((target / "state.json").exists())
            context = AcceptedRuntimeHost(target).source_context(
                graph=self.context.graph, source_root=self.source)
            uninterrupted = next_update_receipt(
                target, context, feature_path, self.artifact)
            accepted = accepted_witness_receipt(
                parent, successor, published, decision, context, bound,
                uninterrupted, feature_path, process_nonce=PROCESS_NONCE)
            stage_path = self.root / "c16.2c-accepted-stage.json"
            stage_path.write_text(
                json.dumps(accepted, sort_keys=True, separators=(",", ":")),
                encoding="utf-8")
        self.assertEqual(json.loads(stage_path.read_text()), accepted)
        self.assertFalse((target / "state.json").exists())

    def test_c16_2c_stage_cold_next_update_matches_persisted_uninterrupted_stage(self):
        stage_path = self.root / "c16.2c-accepted-stage.json"
        if not stage_path.is_file():
            self.fail("accepted C16.2c stage has not been persisted")
        accepted = json.loads(stage_path.read_text())
        self.assertNotEqual(
            accepted["uninterrupted_process_nonce"], PROCESS_NONCE)
        target = self.root / "accepted"
        feature_path = Path(accepted["feature_artifact_path"])
        cold = cold_probe(target, feature_path, self.artifact)
        receipt = finalize_witness_receipt(accepted, cold)
        receipt["cold_process_nonce"] = PROCESS_NONCE
        self.assertTrue(receipt["cold_next_update_equivalent"])
        self.assertEqual((
            receipt["parent_generation"], receipt["retained_generation"],
            receipt["parent_optimizer_step"], receipt["retained_optimizer_step"],
        ), (0, 1, 0, 1))
        self.assertFalse(
            receipt["c03_successor_fixture_authority"]["production_trajectory_authority"])
        receipt_path = target / "c16.2c-launch-witness.json"
        receipt_path.write_text(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")),
            encoding="utf-8")
        self.assertEqual(json.loads(receipt_path.read_text()), receipt)
if __name__ == "__main__":
    unittest.main()
