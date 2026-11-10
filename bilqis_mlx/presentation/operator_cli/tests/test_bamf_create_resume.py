"""#751 production BAMF create/resume operator contract."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from contextlib import contextmanager
from dataclasses import asdict
import io
import json
from pathlib import Path
from unittest.mock import patch

from bilqis_mlx.cli import main
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
    genesis_feature_source_patch, source_features,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch
from bilqis_mlx.runtime.tests._bamf_first_student_support import BamfFirstStudentCase
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _lease
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactIdentity


ROOT = Path(__file__).resolve().parents[4]
TOPOLOGY = ROOT / "configs/models/bamf-0.2.json"


def _tree_snapshot(root: Path):
    return tuple(
        (str(path.relative_to(root)), path.is_dir(), path.stat().st_mtime_ns,
         None if path.is_dir() else path.read_bytes())
        for path in (root, *sorted(root.rglob("*")))
    )


class BamfCreateResumeTests(BamfFirstStudentCase):
    FOUNDATION_ARGS = (
        "--run-id", "operator-first-student",
        "--run-seed", "543",
        "--learning-rate", "0.0007",
        "--adam-beta1", "0.88",
        "--adam-beta2", "0.97",
        "--adam-eps", "1e-7",
        "--weight-decay", "0.03",
    )

    def invoke(self, argv):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = main(["train", *argv])
        return code, output.getvalue(), errors.getvalue()

    @contextmanager
    def accepted_read_context(self):
        with shape_patch(), patch(
            "bilqis_mlx.runtime.bamf_bundle.feature_authority._authenticate_features",
            return_value=source_features(),
        ):
            yield

    @contextmanager
    def foundation_create_context(self):
        with patch(
                "bilqis_mlx.presentation.operator_cli.bamf_lifecycle.source_foundation",
                return_value=(self.source, self.release, self.graph)), patch(
                "bilqis_mlx.presentation.operator_cli.bamf_lifecycle.atlas_manifest_identity",
                return_value=self.identity), shape_patch(), genesis_feature_source_patch(), patch(
                "bilqis_mlx.semantics.atlas.snapshot.resolve_atlas_artifact_selection",
                return_value=self.selection), patch(
                "bilqis_mlx.runtime.bamf_first_student.resolve_atlas_artifact_selection",
                return_value=self.selection), patch.object(
                mlx_checkpoint, "assert_headroom"):
            yield

    def test_fresh_bamf_dry_run_is_ready_and_does_not_create_run(self):
        target = self.root / "new-bamf"
        manifest = self.root / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        with self.foundation_create_context():
            code, output, errors = self.invoke([
                "--dry-run", "--model-topology", str(TOPOLOGY),
                "--atlas-release-manifest", str(manifest),
                "--run-dir", str(target), "--source-prefetch-workers", "0",
                *self.FOUNDATION_ARGS,
            ])

        self.assertEqual((code, errors), (0, ""))
        report = json.loads(output)
        self.assertEqual(report["schema"], "bilqis.bamf.operator-lifecycle/v1")
        self.assertEqual(report["result"], "READY_TO_CREATE")
        self.assertEqual(report["admission_policy"], "staged")
        self.assertEqual(report["run_id"], "operator-first-student")
        self.assertEqual(report["run_seed"], 543)
        self.assertEqual(report["optimizer_hyperparameters"], {
            "learning_rate": 0.0007,
            "betas": [0.88, 0.97],
            "eps": 1e-7,
            "weight_decay": 0.03,
        })
        self.assertEqual(report["source_prefetch_workers"], 0)
        self.assertEqual(report["neural_updates"], 0)
        self.assertFalse(target.exists())

    def test_fresh_bamf_atlas_release_requires_scope_before_any_run_write(self):
        target = self.root / "new-bamf"
        manifest = self.root / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        code, output, errors = self.invoke([
            "--human-run", "--model-topology", str(TOPOLOGY),
            "--admission-policy", "atlas-release",
            "--atlas-release-manifest", str(manifest),
            "--run-dir", str(target), *self.FOUNDATION_ARGS,
        ])

        self.assertEqual((code, output), (2, ""))
        self.assertIn("BAMF_ATLAS_EXPLICIT_SCOPE_FILE_REQUIRED", errors)
        self.assertFalse(target.exists())

    def test_fresh_bamf_dry_run_rejects_invalid_optimizer_before_writes(self):
        target = self.root / "new-bamf"
        manifest = self.root / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        code, output, errors = self.invoke([
            "--dry-run", "--model-topology", str(TOPOLOGY),
            "--atlas-release-manifest", str(manifest),
            "--run-dir", str(target),
            "--run-id", "operator-first-student", "--run-seed", "543",
            "--learning-rate", "-0.1", "--adam-beta1", "0.88",
            "--adam-beta2", "0.97", "--adam-eps", "1e-7",
            "--weight-decay", "0.03",
        ])

        self.assertEqual((code, output), (2, ""))
        self.assertIn("BAMF_OPERATOR_FOUNDATION_OPTIMIZER_INVALID", errors)
        self.assertFalse(target.exists())

    def test_human_create_publishes_generation_zero_without_optimizer_update(self):
        target = self.root / "created-bamf"
        manifest = self.root / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        with self.foundation_create_context():
            code, output, errors = self.invoke([
                "--human-run", "--model-topology", str(TOPOLOGY),
                "--atlas-release-manifest", str(manifest),
                "--run-dir", str(target), *self.FOUNDATION_ARGS,
            ])

        self.assertEqual((code, errors), (0, ""))
        self.assertIn('"result": "CREATED"', output)
        self.assertTrue((target / "bamf-state.json").is_file())
        self.assertFalse((target / "autonomy/atlas-admission/current.json").exists())
        with self.accepted_read_context():
            from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority
            student, _manifest_sha = load_bamf_generation_authority(
                target / "bamf-state.json")
        self.assertEqual(student.run_id, "operator-first-student")
        self.assertEqual(student.run_identity.run_seed, 543)
        self.assertEqual(student.retained_state.optimizer_step, 0)
        self.assertEqual(student.optimizer_hyperparameters, self.hp)

    def test_resume_without_overrides_reads_saved_b13_identity_without_writes(self):
        target = self.root / "accepted-bamf"
        receipt = self.preflight(target)
        before = _tree_snapshot(target)

        with self.accepted_read_context():
            code, output, errors = self.invoke([
                "--dry-run", "--resume", "--run-dir", str(target),
            ])

        self.assertEqual((code, errors), (0, ""))
        report = json.loads(output)
        self.assertEqual(report["result"], "READY_TO_RESUME")
        self.assertEqual(report["admission_policy"], "staged")
        self.assertEqual(report["run_seed"], receipt.run_identity.run_seed)
        self.assertEqual(
            report["model_topology"]["digest"],
            receipt.run_identity.initial_topology_digest,
        )
        self.assertEqual(
            report["atlas_release_manifest"]["sha256"],
            receipt.atlas_artifact.bundle_id,
        )
        self.assertEqual(_tree_snapshot(target), before)

    def test_resume_explicit_atlas_release_conflict_rejects_before_writes(self):
        target = self.root / "accepted-bamf"
        self.preflight(target)
        before = _tree_snapshot(target)

        for policy_args in (("--admission-policy", "atlas-release"),
                            ("--admission-policy=atlas-release",)):
            with self.subTest(policy_args=policy_args), self.accepted_read_context():
                code, output, errors = self.invoke([
                    "--dry-run", "--resume", "--run-dir", str(target),
                    *policy_args,
                ])

            self.assertEqual((code, output), (2, ""))
            self.assertIn("BAMF_OPERATOR_RESUME_ADMISSION_POLICY_CONFLICT", errors)
            self.assertEqual(_tree_snapshot(target), before)

    def test_resume_rejects_atlas_scope_override_before_writes(self):
        target = self.root / "accepted-bamf"
        self.preflight(target)
        before = _tree_snapshot(target)
        scope = self.root / "scope.json"
        scope.write_text("{}", encoding="utf-8")

        with self.accepted_read_context():
            code, output, errors = self.invoke([
                "--dry-run", "--resume", "--run-dir", str(target),
                "--atlas-admission-scope", str(scope),
            ])

        self.assertEqual((code, output), (2, ""))
        self.assertIn("BAMF_OPERATOR_RESUME_ATLAS_SCOPE_OVERRIDE_FORBIDDEN", errors)
        self.assertEqual(_tree_snapshot(target), before)

    def test_human_resume_is_cold_validation_only_and_neural_inert(self):
        target = self.root / "accepted-bamf"
        self.preflight(target)
        before = _tree_snapshot(target)

        with self.accepted_read_context(), patch(
                "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                side_effect=AssertionError("C16.2 owns later neural execution")):
            code, output, errors = self.invoke([
                "--human-run", "--resume", "--run-dir", str(target),
            ])

        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(json.loads(output)["result"], "READY_TO_RESUME")
        self.assertEqual(_tree_snapshot(target), before)

    def test_resume_conflicting_seed_and_optimizer_reject_before_writes(self):
        target = self.root / "accepted-bamf"
        self.preflight(target)
        before = _tree_snapshot(target)
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
            self.assertEqual(_tree_snapshot(target), before)

    def test_resume_conflicting_atlas_manifest_rejects_before_writes(self):
        target = self.root / "accepted-bamf"
        self.preflight(target)
        before = _tree_snapshot(target)
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
        self.assertEqual(_tree_snapshot(target), before)

    def test_resume_conflicting_topology_rejects_before_writes(self):
        target = self.root / "accepted-bamf"
        self.preflight(target)
        before = _tree_snapshot(target)
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
        self.assertEqual(_tree_snapshot(target), before)


if __name__ == "__main__":
    import unittest
    unittest.main()
