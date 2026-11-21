"""BAMF resume conflict and interrupted-custody rejection."""
import json
from pathlib import Path
import shutil
from unittest.mock import patch

from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactIdentity

from .resume_test_support import ResumeCase, TOPOLOGY, tree_snapshot


class BamfResumeTests(ResumeCase):
    def test_human_resume_run_id_conflict_never_reaches_learner(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            before = tree_snapshot(target)
            with self.accepted_read_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("C16.2 owns later neural execution")):
                code, output, errors = self.invoke([
                    "--human-run", "--resume", "--run-dir", str(target),
                    "--run-id", "wrong-run",
                ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BAMF_OPERATOR_RESUME_RUN_ID_CONFLICT", errors)
            self.assertEqual(tree_snapshot(target), before)

    def test_human_resume_optimizer_conflict_never_reaches_learner(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            before = tree_snapshot(target)
            with self.accepted_read_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("C16.2 owns later neural execution")):
                code, output, errors = self.invoke([
                    "--human-run", "--resume", "--run-dir", str(target),
                    "--learning-rate", "0.0008", "--adam-beta1", "0.88",
                    "--adam-beta2", "0.97", "--adam-eps", "1e-7",
                    "--weight-decay", "0.03",
                ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BAMF_OPERATOR_RESUME_OPTIMIZER_CONFLICT", errors)
            self.assertEqual(tree_snapshot(target), before)

    def test_no_pointer_bamf_v2_custody_resume_is_intercepted_before_learner(self):
            target = self.root / "interrupted-bamf"
            (target / "bamf-bundles").mkdir(parents=True)
            before = tree_snapshot(target)
            with patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("legacy learner must not inspect BAMF v2 custody")):
                code, output, errors = self.invoke([
                    "--human-run", "--resume", "--run-dir", str(target),
                ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BAMF_OPERATOR_INTERRUPTED_GENESIS_REQUIRES_CREATE_RETRY", errors)
            self.assertEqual(tree_snapshot(target), before)

    def test_trust_only_pointerless_resume_is_intercepted_before_learner(self):
            target = self.root / "trust-only-bamf"
            receipt = self.preflight(target)
            run_id = receipt.run_identity.run_id
            shutil.rmtree(target)
            with patch(
                    "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                    side_effect=AssertionError("legacy learner must not inspect BAMF v2 trust")):
                code, output, errors = self.invoke([
                    "--human-run", "--resume", "--run-dir", str(target),
                    "--run-id", run_id,
                ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BAMF_OPERATOR_INTERRUPTED_GENESIS_REQUIRES_CREATE_RETRY", errors)
            self.assertFalse(target.exists())

    def test_resume_conflicting_seed_and_optimizer_reject_before_writes(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            before = tree_snapshot(target)
            cases = (
                (["--run-seed", "544"], "BAMF_OPERATOR_RESUME_RUN_SEED_CONFLICT"),
                (["--learning-rate", "0.0008", "--adam-beta1", "0.88",
                  "--adam-beta2", "0.97", "--adam-eps", "1e-7",
                  "--weight-decay", "0.03"], "BAMF_OPERATOR_RESUME_OPTIMIZER_CONFLICT"),
            )
            for override, reason in cases:
                with self.subTest(reason=reason), self.accepted_read_context():
                    code, output, errors = self.invoke([
                        "--dry-run", "--resume", "--run-dir", str(target), *override,
                    ])
                self.assertEqual((code, output), (2, ""))
                self.assertIn(reason, errors)
                self.assertEqual(tree_snapshot(target), before)

    def test_resume_conflicting_atlas_manifest_rejects_before_writes(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            before = tree_snapshot(target)
            manifest = self.root / "other-manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            other = AtlasArtifactIdentity("1" * 64, "2" * 64, "3" * 64)
            with self.accepted_read_context(), patch(
                    "bilqis_mlx.presentation.operator_cli.bamf_lifecycle.atlas_manifest_identity",
                    return_value=other):
                code, output, errors = self.invoke([
                    "--dry-run", "--resume", "--run-dir", str(target),
                    "--atlas-release-manifest", str(manifest),
                ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BAMF_OPERATOR_RESUME_ATLAS_MANIFEST_CONFLICT", errors)
            self.assertEqual(tree_snapshot(target), before)

    def test_resume_conflicting_topology_rejects_before_writes(self):
            target = self.root / "accepted-bamf"
            self.preflight(target)
            before = tree_snapshot(target)
            forged = ModelTopologySpecV2()
            object.__setattr__(forged, "layers", forged.layers + 1)
            with self.accepted_read_context(), patch(
                    "bilqis_mlx.runtime.topology_lifecycle.topology_from_file",
                    return_value=forged):
                code, output, errors = self.invoke([
                    "--dry-run", "--resume", "--run-dir", str(target),
                    "--model-topology", str(TOPOLOGY),
                ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BAMF_OPERATOR_RESUME_TOPOLOGY_CONFLICT", errors)
            self.assertEqual(tree_snapshot(target), before)

    def test_resume_all_equality_assertions_wrong_still_reports_run_id_first(self):
            target = self.root / "accepted-all-wrong"
            self.preflight(target)
            before = tree_snapshot(target)
            forged = ModelTopologySpecV2()
            object.__setattr__(forged, "layers", forged.layers + 1)
            manifest = self.root / "wrong-atlas.json"
            manifest.write_text("{}", encoding="utf-8")
            other = AtlasArtifactIdentity("1" * 64, "2" * 64, "3" * 64)
            with self.accepted_read_context(), patch(
                    "bilqis_mlx.runtime.topology_lifecycle.topology_from_file",
                    return_value=forged), patch(
                    "bilqis_mlx.presentation.operator_cli.bamf_lifecycle.atlas_manifest_identity",
                    return_value=other):
                code, output, errors = self.invoke([
                    "--dry-run", "--resume", "--run-dir", str(target),
                    "--run-id", "wrong-run", "--run-seed", "544",
                    "--model-topology", str(TOPOLOGY),
                    "--learning-rate", "0.8", "--adam-beta1", "0.8",
                    "--adam-beta2", "0.8", "--adam-eps", "1e-5",
                    "--weight-decay", "0.8",
                    "--atlas-release-manifest", str(manifest),
                ])
            self.assertEqual((code, output), (2, ""))
            self.assertIn("BAMF_OPERATOR_RESUME_RUN_ID_CONFLICT", errors)
            self.assertEqual(tree_snapshot(target), before)
