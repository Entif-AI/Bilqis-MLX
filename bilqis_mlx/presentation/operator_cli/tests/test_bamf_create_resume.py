"""#542 production BAMF create/resume operator contract."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from contextlib import contextmanager
from dataclasses import asdict
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

from bilqis_mlx.cli import main
from bilqis_mlx.factory.answers import (
    AnswerModality, AnswerModalityRegistry, RegisteredAnswerModality, fixed_domain,
)
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_course, _synthetic_registry
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.admission import _executable_factory_admission
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
    genesis_feature_source_patch, source_features,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch
from bilqis_mlx.runtime.tests._bamf_first_student_support import BamfFirstStudentCase
from bilqis_mlx.state_dag import persist, read_current
from bilqis_mlx.vocabulary_growth import digest


ROOT = Path(__file__).resolve().parents[4]
TOPOLOGY = ROOT / "configs/models/bamf-0.2.json"


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

    @staticmethod
    def output_records(output: str):
        decoder = json.JSONDecoder()
        records = []
        offset = 0
        while offset < len(output):
            while offset < len(output) and output[offset].isspace():
                offset += 1
            if offset == len(output):
                break
            record, offset = decoder.raw_decode(output, offset)
            records.append(record)
        return tuple(records)

    @staticmethod
    def tree_snapshot(root: Path):
        return tuple(
            (str(path.relative_to(root)), path.is_dir(),
             None if path.is_dir() else path.read_bytes())
            for path in (root, *sorted(root.rglob('*')))
        )

    def persisted_source_root(self):
        storage = self.root / "isolated-storage"
        source = storage / "school-mlx-v1"
        source.mkdir(parents=True)
        tokens = ["fixture.padding", "cogal.value.false", "cogal.value.true"]
        nodes = [{
            "id": token, "family": "fixture", "subtype": "literal",
            "signature": "SemanticSymbol", "arity": 0, "stage": "fixture",
        } for token in tokens]
        graph = {
            "tokens": tokens,
            "nodes": nodes,
            "row_contract_sha256": {node["id"]: digest(node) for node in nodes},
            "allocation_source_graph_sha256": {},
        }
        course = _synthetic_course(6)
        registry = _synthetic_registry()
        curriculum, bindings = from_legacy_course(course)
        answers = AnswerModalityRegistry((
            RegisteredAnswerModality(
                AnswerModality("binary", "answer.binary/v1", "a" * 64),
                fixed_domain(("FALSE", "TRUE")),
                lambda value: {
                    "FALSE": "cogal.value.false", "TRUE": "cogal.value.true",
                }[value],
            ),
        ))
        release = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(), registry, answers,
            source_root=None, graph=graph, verification_seed=17)
        origin = Checkpoint("7" * 64, "bundles/foundation-origin", 0, True)
        _, release_file, admission = _executable_factory_admission(
            source, release, origin, _fingerprint(graph), graph)
        bundle = source / "bundles/source-fixture"
        bundle.mkdir(parents=True)
        catalog = bundle / "semantic-catalog.json"
        catalog.write_text(
            json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        from bilqis_mlx.runtime.mlx_checkpoint import digest_file
        binding = {
            "filename": "semantic-catalog.json",
            "digest": digest(graph),
            "token_count": len(graph["tokens"]),
            "file_sha256": digest_file(catalog),
        }
        (bundle / "manifest.json").write_text(
            json.dumps({"semantic_catalog": binding}), encoding="utf-8")
        state = {
            "generation": 1,
            "factory_release_sha256": release.release_sha256,
            "factory_release_file": release_file,
            "factory_admission_v2": asdict(admission),
            "semantic_graph_sha256": _fingerprint(graph),
            "model_bundle": "bundles/source-fixture",
            "school": {
                "current_student": asdict(origin),
                "active_grades": [grade.id for grade in course.grades],
                "grade_index": 0,
                "visits": 0,
                "stage": "FOUNDATION",
            },
            "result": "READY_FOR_HUMAN_START",
        }
        persist(source, state)
        return storage, source

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
                "bilqis_mlx.presentation.operator_cli.bamf_lifecycle_inputs.active_run_dir",
                return_value=self.source), patch(
                "bilqis_mlx.presentation.operator_cli.bamf_lifecycle.atlas_manifest_identity",
                return_value=self.identity), shape_patch(), genesis_feature_source_patch(), patch(
                "bilqis_mlx.semantics.atlas.snapshot.resolve_atlas_artifact_selection",
                return_value=self.selection), patch(
                "bilqis_mlx.runtime.bamf_first_student.resolve_atlas_artifact_selection",
                return_value=self.selection), patch.object(
                mlx_checkpoint, "assert_headroom"), patch(
                "bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom"):
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
        self.assertFalse(report["ready_for_training"])
        self.assertEqual(report["run_identity"]["run_id"], report["run_id"])
        self.assertFalse(target.exists())

    def test_dry_run_uses_persisted_source_foundation_owner_without_lifecycle_stub(self):
        target = self.root / "real-source-dry-run"
        manifest = self.root / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        source_bundle = self.source / "bundles/source-fixture"
        source_bundle.mkdir(parents=True)
        (source_bundle / "manifest.json").write_text(
            json.dumps({"semantic_catalog": {}}), encoding="utf-8")
        source_state = read_current(self.source)
        source_state["generation"] += 1
        source_state["model_bundle"] = "bundles/source-fixture"
        persist(self.source, source_state)
        with patch(
                "bilqis_mlx.presentation.operator_cli.bamf_lifecycle_inputs.active_run_dir",
                return_value=self.source), patch(
                "bilqis_mlx.runtime.mlx_checkpoint._read_catalog",
                return_value=self.graph), patch(
                "bilqis_mlx.presentation.operator_cli.bamf_lifecycle.atlas_manifest_identity",
                return_value=self.identity), shape_patch(), genesis_feature_source_patch(), patch(
                "bilqis_mlx.semantics.atlas.snapshot.resolve_atlas_artifact_selection",
                return_value=self.selection), patch(
                "bilqis_mlx.runtime.bamf_first_student.resolve_atlas_artifact_selection",
                return_value=self.selection):
            code, output, errors = self.invoke([
                "--dry-run", "--model-topology", str(TOPOLOGY),
                "--atlas-release-manifest", str(manifest),
                "--run-dir", str(target), *self.FOUNDATION_ARGS,
            ])
        self.assertEqual((code, errors), (0, ""))
        report = json.loads(output)
        self.assertEqual(report["result"], "READY_TO_CREATE")
        self.assertEqual(report["run_id"], "operator-first-student")
        self.assertFalse(report["ready_for_training"])
        self.assertFalse(target.exists())

    def test_fresh_bamf_atlas_release_requires_scope_before_any_run_write(self):
        target = self.root / "new-bamf"
        manifest = self.root / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        with self.foundation_create_context():
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

    def test_persisted_source_dry_run_and_create_preserve_source_and_share_identity(self):
        storage, source = self.persisted_source_root()
        target = self.root / "persisted-source-bamf"
        manifest = self.root / "persisted-source-atlas.json"
        manifest.write_text("{}", encoding="utf-8")
        before = self.tree_snapshot(source)
        base = [
            "--model-topology", str(TOPOLOGY),
            "--atlas-release-manifest", str(manifest),
            "--run-dir", str(target), *self.FOUNDATION_ARGS,
        ]
        context = (
            patch.dict(os.environ, {"BILQIS_STORAGE_ROOT": str(storage)}),
            patch("bilqis_mlx.presentation.operator_cli.bamf_lifecycle.atlas_manifest_identity",
                  return_value=self.identity),
            shape_patch(), genesis_feature_source_patch(),
            patch("bilqis_mlx.semantics.atlas.snapshot.resolve_atlas_artifact_selection",
                  return_value=self.selection),
            patch("bilqis_mlx.runtime.bamf_first_student.resolve_atlas_artifact_selection",
                  return_value=self.selection),
            patch.object(mlx_checkpoint, "assert_headroom"),
            patch("bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom"),
            patch("bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                  side_effect=AssertionError("C16.1a must not dispatch learner")),
        )
        with context[0], context[1], context[2], context[3], context[4], \
                context[5], context[6], context[7], context[8]:
            dry_code, dry_output, dry_errors = self.invoke(["--dry-run", *base])
            create_code, create_output, create_errors = self.invoke(["--human-run", *base])
        self.assertEqual((dry_code, dry_errors, create_code, create_errors), (0, "", 0, ""))
        dry = json.loads(dry_output)
        created = self.output_records(create_output)[-1]
        self.assertEqual(dry["run_identity"], created["run_identity"])
        self.assertEqual(dry["neural_updates"], created["neural_updates"])
        self.assertEqual((dry["ready_for_training"], created["ready_for_training"]),
                         (False, False))
        self.assertEqual(self.tree_snapshot(source), before)
        self.assertTrue((target / "bamf-state.json").is_file())

if __name__ == "__main__":
    import unittest
    unittest.main()
