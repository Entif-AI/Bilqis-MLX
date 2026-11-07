"""B13.5 accepted-generation acceptance-provenance witnesses.

Publication is not acceptance. A generation may only be published, and may only
mint accepted-generation authority, when the retention owner has accepted the
exact candidate state.
"""
from __future__ import annotations

import os
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    LEGACY_ACCEPTANCE_SCHEMA, PREVIOUS_ACCEPTANCE_SCHEMA,
    AcceptedCandidateBinding, mint_acceptance_binding,
)
from bilqis_mlx.learning.atlas_retention_decision import (
    LEGACY_DECISION_SCHEMA, CandidateRetentionDecision, decide_candidate_retention,
)
from bilqis_mlx.runtime.bamf_bundle import (
    publish_bamf_generation, load_bamf_generation, load_bamf_generation_authority,
    read_accepted_generation_feature_receipt,
)
from bilqis_mlx.runtime.bamf_bundle import admission
from bilqis_mlx.runtime.bamf_bundle.records import (
    LEGACY_BAMF_POINTER_SCHEMA,
)

from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, accepted_state, candidate, parent_state, retention_decision,
    shape_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.test_feature_authority import (
    RELEASE, source_features, feature_bound,
)
from bilqis_mlx.runtime.bamf_bundle.records import canonical


class GenerationAcceptanceProvenanceTests(unittest.TestCase):
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

    def publish(self, source, **kwargs):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_bamf_generation(self.run, source, **kwargs)

    def test_publication_without_retention_acceptance_is_refused(self):
        with self.assertRaises(BilqisError) as failure:
            self.publish(candidate(parent_state()))
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_GENERATION_ACCEPTANCE_REQUIRED")
        self.assertFalse((self.run / "bamf-state.json").exists())

    def test_acceptance_for_another_candidate_state_is_refused(self):
        source = candidate(parent_state())
        other = acceptance(candidate(accepted_state(parent_state())))
        with self.assertRaises(BilqisError) as failure:
            self.publish(source, acceptance=other)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_GENERATION_ACCEPTANCE_DRIFT")

    def test_acceptance_with_another_feature_identity_is_refused(self):
        source = candidate(parent_state())
        binding = mint_acceptance_binding(
            retention_decision(retained=source.retained_state), source.retained_state, run_id=source.run_id,
            generation=source.generation, feature_sha256="a" * 64)
        with self.assertRaises(BilqisError) as failure:
            self.publish(source, acceptance=binding)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_GENERATION_ACCEPTANCE_DRIFT")

    def test_publication_refuses_binding_with_foreign_step_proof(self):
        source = candidate(accepted_state(parent_state()))
        forged = acceptance(source)
        object.__setattr__(forged, "step_proof_sha256", ("0" * 64,))
        with self.assertRaises(BilqisError) as failure:
            self.publish(source, acceptance=forged)
        self.assertEqual(failure.exception.context["reason"],
                         "BAMF_GENERATION_ACCEPTANCE_DRIFT")

    def test_historical_binding_with_matching_identity_cannot_authorize_publication(self):
        source = candidate(accepted_state(parent_state()))
        parsed = AcceptedCandidateBinding.from_record(acceptance(source).to_record())
        self.assertNotEqual(type(parsed), AcceptedCandidateBinding)
        self.assertEqual(parsed.digest, acceptance(source).digest)
        with self.assertRaises(BilqisError) as failure:
            self.publish(source, acceptance=parsed)
        self.assertEqual(failure.exception.context["reason"],
                         "BAMF_GENERATION_ACCEPTANCE_REQUIRED")

    def test_v1_acceptance_record_remains_readable_but_not_authoritative(self):
        source = candidate(parent_state())
        issued = acceptance(source)
        fields = (
            "run_id", "generation", "candidate_identity_sha256",
            "feature_sha256", "optimizer_step", "retention_reason",
            "step_proof_sha256", "decision_sha256",
        )
        legacy = {name: getattr(issued, name) for name in fields}
        legacy["schema_version"] = LEGACY_ACCEPTANCE_SCHEMA
        legacy["binding_sha256"] = hashlib.sha256(canonical(legacy)).hexdigest()
        parsed = AcceptedCandidateBinding.from_record(legacy)
        self.assertEqual(parsed.to_record(), legacy)
        with self.assertRaises(BilqisError):
            self.publish(source, acceptance=parsed)

    def test_legacy_parent_acceptance_cannot_authorize_fresh_successor(self):
        parent = candidate(parent_state())
        published = self.publish(parent, acceptance=acceptance(parent))
        acceptance_path = (
            self.run / "bamf-acceptance" / f"{published['manifest_sha256']}.json")
        record = json.loads(acceptance_path.read_text())
        record.pop("source_anchors")
        record["schema_version"] = PREVIOUS_ACCEPTANCE_SCHEMA
        record["binding_sha256"] = hashlib.sha256(canonical({
            key: value for key, value in record.items()
            if key != "binding_sha256"
        })).hexdigest()
        acceptance_path.write_text(json.dumps(record))

        pointer_path = self.run / "bamf-state.json"
        pointer = json.loads(pointer_path.read_text())
        pointer["acceptance_sha256"] = record["binding_sha256"]
        pointer_path.write_text(json.dumps(pointer))

        successor = candidate(
            accepted_state(parent_state()), 1, published["manifest_sha256"])
        with self.assertRaises(BilqisError):
            self.publish(successor, acceptance=acceptance(successor))

    def test_replay_cannot_replace_immutable_acceptance_evidence(self):
        source = candidate(parent_state())
        first = self.publish(source, acceptance=acceptance(source))
        altered = acceptance(source)
        object.__setattr__(altered, "policy_sha256", "0" * 64)
        with self.assertRaises(BilqisError) as failure:
            self.publish(source, acceptance=altered)
        self.assertEqual(failure.exception.context["reason"],
                         "DATA_PLANE_BUNDLE_IDENTITY_CONFLICT")
        self.assertEqual(json.loads((self.run / "bamf-state.json").read_text()), first)

    def test_cold_readback_refuses_resigned_foreign_step_proof(self):
        features = source_features()
        source = feature_bound(candidate(accepted_state(parent_state())), features)
        self.publish(source, acceptance=acceptance(source))
        path = self.run / "bamf-acceptance" / f"{json_manifest_sha(self.run)}.json"
        record = json.loads(path.read_text())
        record["step_proof_sha256"] = ["0" * 64]
        record["binding_sha256"] = hashlib.sha256(canonical({
            key: value for key, value in record.items()
            if key != "binding_sha256"
        })).hexdigest()
        path.write_text(json.dumps(record))
        with shape_patch(), \
                patch("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                      "build_feature_manifest", return_value=features), \
                patch("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                      "load_pinned_atlas_snapshot", side_effect=lambda selection: selection):
            with self.assertRaises(BilqisError) as failure:
                read_accepted_generation_feature_receipt(
                    self.run / "bamf-state.json", "/artifact")
        self.assertEqual(failure.exception.context["reason"],
                         "BAMF_GENERATION_ACCEPTANCE_DRIFT")

    def test_cold_readback_refuses_rehashed_retention_policy(self):
        features = source_features()
        source = feature_bound(candidate(parent_state()), features)
        self.publish(source, acceptance=acceptance(source))
        path = self.run / "bamf-acceptance" / f"{json_manifest_sha(self.run)}.json"
        record = json.loads(path.read_text())
        record["policy_sha256"] = "0" * 64
        record["binding_sha256"] = hashlib.sha256(canonical({
            key: value for key, value in record.items()
            if key != "binding_sha256"
        })).hexdigest()
        path.write_text(json.dumps(record))
        with shape_patch(), \
                patch("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                      "build_feature_manifest", return_value=features), \
                patch("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                      "load_pinned_atlas_snapshot", side_effect=lambda selection: selection):
            with self.assertRaises(BilqisError) as failure:
                read_accepted_generation_feature_receipt(
                    self.run / "bamf-state.json", "/artifact")
        self.assertEqual(failure.exception.context["reason"],
                         "BAMF_GENERATION_ACCEPTANCE_DRIFT")

    def test_historical_pointer_can_cold_load_without_minting_new_authority(self):
        features = source_features()
        source = feature_bound(candidate(parent_state()), features)
        self.publish(source, acceptance=acceptance(source))
        pointer_path = self.run / "bamf-state.json"
        pointer = json.loads(pointer_path.read_text())
        pointer["schema"] = LEGACY_BAMF_POINTER_SCHEMA
        pointer.pop("acceptance_sha256")
        pointer_path.write_text(json.dumps(pointer))
        with shape_patch():
            self.assertEqual(
                load_bamf_generation(pointer_path).run_id, source.run_id)
        with shape_patch(), \
                patch("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                      "build_feature_manifest", return_value=features), \
                patch("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                      "load_pinned_atlas_snapshot", side_effect=lambda selection: selection):
            with self.assertRaises(BilqisError):
                read_accepted_generation_feature_receipt(pointer_path, "/artifact")

    def test_caller_cannot_construct_an_acceptance_binding(self):
        source = candidate(parent_state())
        binding = acceptance(source)
        with self.assertRaises(BilqisError):
            AcceptedCandidateBinding(**binding._public_record())

    def test_accepted_c05_decision_cannot_transfer_to_different_optimizer(self):
        source = candidate(parent_state())
        decision = retention_decision(retained=source.retained_state)
        another = accepted_state(parent_state())
        with self.assertRaises(BilqisError):
            mint_acceptance_binding(
                decision, another, run_id=source.run_id,
                generation=source.generation,
                feature_sha256=source.extents.factor_map_digest)

    def test_parent_custody_rejects_a_screen_for_another_parent(self):
        initial = parent_state()
        first = self.publish(candidate(initial), acceptance=acceptance(candidate(initial)))
        successor = candidate(accepted_state(initial), 1, first["manifest_sha256"])
        wrong_parent = accepted_state(initial)
        binding = mint_acceptance_binding(
            retention_decision(parent=wrong_parent, retained=successor.retained_state),
            successor.retained_state, run_id=successor.run_id,
            generation=successor.generation,
            feature_sha256=successor.extents.factor_map_digest)
        with self.assertRaises(BilqisError) as failure:
            self.publish(successor, acceptance=binding)
        self.assertEqual(failure.exception.context["reason"],
                         "BAMF_GENERATION_ACCEPTANCE_DRIFT")

    def test_caller_cannot_mint_acceptance_without_a_retention_decision(self):
        source = candidate(parent_state())
        with self.assertRaises(BilqisError):
            mint_acceptance_binding(
                "FIXTURE_RETENTION_ACCEPTED", source.retained_state,
                run_id=source.run_id, generation=source.generation,
                feature_sha256=source.extents.factor_map_digest)

    def test_historical_decision_cannot_mint_live_acceptance(self):
        source = candidate(parent_state())
        parsed = CandidateRetentionDecision.from_record(retention_decision().to_record())
        self.assertNotEqual(type(parsed), CandidateRetentionDecision)
        self.assertTrue(parsed.accepted)
        with self.assertRaises(BilqisError):
            mint_acceptance_binding(
                parsed, source.retained_state, run_id=source.run_id,
                generation=source.generation,
                feature_sha256=source.extents.factor_map_digest)

    def test_v1_decision_record_remains_readable_without_issuance(self):
        source = candidate(parent_state())
        legacy = {
            "decision": "PROVISIONAL",
            "reason": "PAIRED_SCREEN_WITHIN_BUDGET",
            "target_gain": True,
            "protected_net_gain": 1,
            "schema_version": LEGACY_DECISION_SCHEMA,
        }
        legacy["decision_sha256"] = hashlib.sha256(canonical(legacy)).hexdigest()
        parsed = CandidateRetentionDecision.from_record(legacy)
        self.assertEqual(parsed.to_record(), legacy)
        with self.assertRaises(BilqisError):
            mint_acceptance_binding(
                parsed, source.retained_state,
                run_id=source.run_id, generation=source.generation,
                feature_sha256=source.extents.factor_map_digest)

    def test_a_rejected_retention_decision_cannot_mint_acceptance(self):
        source = candidate(parent_state())
        rejected = retention_decision(
            accepted=False, retained=source.retained_state)
        self.assertFalse(rejected.accepted)
        with self.assertRaises(BilqisError):
            mint_acceptance_binding(
                rejected, source.retained_state, run_id=source.run_id,
                generation=source.generation,
                feature_sha256=source.extents.factor_map_digest)

    def test_receipt_refuses_a_generation_without_acceptance_custody(self):
        features = source_features()
        source = feature_bound(candidate(parent_state()), features)
        self.publish(source, acceptance=acceptance(source))
        binding_path = (self.run / "bamf-acceptance"
                        / f"{json_manifest_sha(self.run)}.json")
        binding_path.unlink()
        with shape_patch(), \
                patch("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                      "build_feature_manifest", return_value=features), \
                patch("bilqis_mlx.runtime.bamf_bundle.feature_authority."
                      "load_pinned_atlas_snapshot", side_effect=lambda selection: selection):
            with self.assertRaises(BilqisError) as failure:
                read_accepted_generation_feature_receipt(
                    self.run / "bamf-state.json", "/artifact")
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_GENERATION_ACCEPTANCE_MISSING")

    def test_accepted_authority_loaders_require_acceptance_custody(self):
        source = candidate(parent_state())
        self.publish(source, acceptance=acceptance(source))
        binding_path = (self.run / "bamf-acceptance"
                        / f"{json_manifest_sha(self.run)}.json")
        binding_path.unlink()
        pointer_path = self.run / "bamf-state.json"
        with shape_patch():
            for name, loader in (
                    ("publication authority", lambda: load_bamf_generation_authority(pointer_path)),
                    ("admission authority", lambda: admission.load_accepted_generation(self.run))):
                with self.subTest(loader=name):
                    with self.assertRaises(BilqisError) as failure:
                        loader()
                    self.assertEqual(
                        failure.exception.context["reason"],
                        "BAMF_GENERATION_ACCEPTANCE_MISSING")

    def test_accepted_authority_loaders_reject_rehashed_acceptance_drift(self):
        source = candidate(parent_state())
        self.publish(source, acceptance=acceptance(source))
        binding_path = (self.run / "bamf-acceptance"
                        / f"{json_manifest_sha(self.run)}.json")
        record = json.loads(binding_path.read_text())
        record["optimizer_step"] += 1
        record["binding_sha256"] = hashlib.sha256(canonical({
            key: value for key, value in record.items()
            if key != "binding_sha256"
        })).hexdigest()
        binding_path.write_text(json.dumps(record))
        pointer_path = self.run / "bamf-state.json"
        with shape_patch():
            for name, loader in (
                    ("publication authority", lambda: load_bamf_generation_authority(pointer_path)),
                    ("admission authority", lambda: admission.load_accepted_generation(self.run))):
                with self.subTest(loader=name):
                    with self.assertRaises(BilqisError) as failure:
                        loader()
                    self.assertEqual(
                        failure.exception.context["reason"],
                        "BAMF_GENERATION_ACCEPTANCE_DRIFT")


def json_manifest_sha(run_dir: Path) -> str:
    import json
    return json.loads((run_dir / "bamf-state.json").read_text())["manifest_sha256"]


if __name__ == "__main__":
    unittest.main()
