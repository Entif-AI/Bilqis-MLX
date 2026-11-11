"""DETACHED_ONLY real-source C05 proof for BAMF-native fixed-school custody."""
from __future__ import annotations

BILQIS_LEAF_GATE_POLICY = "DETACHED_ONLY"

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.accepted_teacher_custody import (
    derive_c03_successor_bundle,
)
from bilqis_mlx.runtime.admission import _executable_factory_admission
from bilqis_mlx.runtime.atlas_visit_provenance import BamfVisitProvenance
from bilqis_mlx.runtime.bamf_bundle import (
    authenticate_bamf_execution_feature_context, record_bamf_rejection,
)
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
    _reset_execution_cache_owner_for_tests,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, bind_accepted_execution_cache, load_accepted_generation,
)
from bilqis_mlx.runtime.bamf_first_student import BamfFoundationConfig, preflight_bamf_foundation
from bilqis_mlx.runtime.factory_candidate_training import FactoryDeliveryObservation
from bilqis_mlx.runtime.factory_retention_owner import evaluate_factory_retention_candidate
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture, store_sidecar
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
from bilqis_mlx.learning.student_ops import train_bamf_factory_step
from .bamf_c16_2c_witness_support import (
    C03_FIXTURE_SEED_OFFSET, CAPABILITY, cold_probe, launch_witness_receipt,
    next_update_receipt, real_candidate_step,
)


class BamfNativeC05LiveTests(unittest.TestCase):
    def setUp(self):
        raw = os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
        if not raw or not Path(raw).is_dir():
            self.skipTest("BILQIS_A01_ATLAS_BUNDLE fixture is not mounted")
        self.artifact = Path(raw).resolve()
        self.repo = Path.cwd()
        self.source = (self.repo / "vendor/legacy-v16").resolve()
        self.context, _ = live_factory_context(self.repo, self.source)
        atlas = json.loads((self.artifact / "atlas.json").read_text())
        self.identity = AtlasArtifactIdentity(
            self.artifact.name, atlas["release_sha256"], atlas["source_bundle_id"])
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
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

    def _visit(self, parent, target, capability):
        cache = bind_accepted_execution_cache(target)
        payload = {
            "run_identity_sha256": parent.run_identity.digest,
            "run_seed": parent.run_identity.run_seed,
            "generation": parent.generation,
            "accepted_manifest_sha256": cache.accepted_manifest_sha256,
            "teacher_identity": parent.teacher_state["teacher_identity"],
            "teacher_epoch": parent.teacher_state["teacher_epoch"],
            "student_sha256": candidate_identity_digest(parent.retained_state),
            "selection_seed": 993,
            "cursor": "c05-live",
            "capability_id": capability,
            "policy_key": "c05-live-source-qualified",
            "schema": "bilqis.bamf.c03-teacher-visit-identity/v1",
        }
        wire = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return BamfVisitProvenance.from_c03_record({
            **payload, "visit_id": hashlib.sha256(wire.encode()).hexdigest()})

    def test_real_candidate_reaches_public_c05_without_legacy_state(self):
        # The accepted runtime deliberately resolves C09 host authority on every
        # rebind. Keep that host fixture active for the complete detached
        # scenario rather than only for generation-zero publication.
        with host_source_authority_patch():
            target, parent, context, feature_path = self._foundation()
            capability = "B.IDBOOLOPS"
            rows = tuple(context.draw_rows(seed=37116, capability=capability, each=1))
            execution = context.release.execution_plan.capability_map[capability]
            delivery = describe_delivered_teaching(
                context.release, capability, execution.teaching_option_ids[0], rows)
            capture = ObservationCapture(target, {})
            capture.attempt_id = "c05-bamf-native-live"
            capture.proposal_id = store_sidecar(
                target, {"attempt_id": capture.attempt_id})["sha256"]
            capture.select_option(capability, None)
            observation = FactoryDeliveryObservation(capture, 1, rows, 37116)
            teacher_hp = type(HP)(
                C05_TRAINING_LEARNING_RATE, HP.betas, HP.eps, HP.weight_decay)
            step = train_bamf_factory_step(
                target, context, parent, str(self.artifact), feature_path, rows,
                capability=capability, delivery=delivery, requested_count=2,
                source_seed=37116, source_each=1, optimizer_step_seed=17,
                visit_provenance=self._visit(parent, target, capability),
                teacher_strategy={"policy": "c05-bamf-native-live"},
                teacher_hparams=teacher_hp, max_norm=1.0, observation=observation)
            self.assertEqual(step.transaction.update_steps, 1)
            self.assertFalse((target / "state.json").exists())
            evaluation = evaluate_factory_retention_candidate(
                context, step.transaction, str(self.artifact), capability, run_dir=target)
            self.assertIsNotNone(evaluation.decision)
            self.assertFalse((target / "state.json").exists())
            self.assertFalse((target / ".c05-fixed-school.anchor.json").exists())
            self.assertTrue((
                target / "c05-fixed-school" / f"{parent.run_identity.digest}.json"
            ).is_file())

    def test_c16_2c_real_rejection_records_rollback_without_parent_mutation(self):
        with host_source_authority_patch():
            target, parent, context, feature_path = self._foundation()
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

    def test_c16_2c_accepts_generation_one_and_cold_next_update_matches(self):
        with host_source_authority_patch():
            target, parent, context, feature_path = self._foundation()
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

        env = dict(os.environ)
        command = [
            sys.executable, "-m",
            "bilqis_mlx.runtime.tests.capability.factory.owner."
            "test_factory_retention_bamf_native_live",
            "--cold-probe", str(target), str(feature_path), str(self.artifact),
        ]
        process = subprocess.run(
            command, cwd=str(self.repo), env=env, capture_output=True,
            text=True, timeout=900)
        self.assertEqual(process.returncode, 0, process.stderr)
        cold = json.loads(process.stdout.strip().splitlines()[-1])
        self.assertEqual(cold, uninterrupted)
        receipt = launch_witness_receipt(
            parent, successor, published, decision, context, bound,
            uninterrupted, cold)
        self.assertTrue(receipt["cold_next_update_equivalent"])
        self.assertEqual((
            receipt["parent_generation"], receipt["retained_generation"],
            receipt["parent_optimizer_step"], receipt["retained_optimizer_step"],
        ), (0, 1, 0, 1))
        self.assertEqual(
            receipt["factory_release_sha256"], context.release.release_sha256)
        self.assertFalse(
            receipt["c03_successor_fixture_authority"]["production_trajectory_authority"])
        receipt_path = target / "c16.2c-launch-witness.json"
        receipt_path.write_text(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")),
            encoding="utf-8")
        self.assertEqual(json.loads(receipt_path.read_text()), receipt)
        self.assertFalse((target / "state.json").exists())

    def test_c16_2c_non_admitted_future_capability_is_source_blocked(self):
        with host_source_authority_patch():
            target, _parent, context, _feature_path = self._foundation()
            with self.assertRaisesRegex(Exception, "FACTORY_EXECUTABLE_GENERATION_UNKNOWN_CAPABILITY"):
                tuple(context.draw_rows(seed=1, capability="FUTURE.X", each=1))
            self.assertFalse((target / "state.json").exists())

    def test_c16_2c_two_admitted_families_use_the_same_source_c03_c05_chain(self):
        for capability in ("A.IDENTITY", "B.IDBOOLOPS"):
            with self.subTest(capability=capability), host_source_authority_patch():
                target, parent, context, feature_path = self._foundation(
                    capability.lower().replace(".", "-"))
                bound, rows, step, evaluation, decision = real_candidate_step(
                    target, parent, context, feature_path, self.artifact,
                    learning_rate=C05_TRAINING_LEARNING_RATE,
                    capability=capability)
                self.assertEqual(bound.identity.capability_id, capability)
                self.assertEqual(
                    step.transaction.training_authorities[0].delivery_capability,
                    capability)
                self.assertTrue(rows)
                self.assertEqual(len(decision.evidence_sha256), 64)
                self.assertEqual(len(decision.policy_sha256), 64)
                self.assertIsNotNone(evaluation.decision)
                self.assertFalse((target / "state.json").exists())


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--cold-probe":
        if mx.metal.is_available():
            mx.set_default_device(mx.gpu)
        print(json.dumps(cold_probe(
            Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])),
            sort_keys=True))
    else:
        unittest.main()
