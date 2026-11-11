"""Persisted-source byte preservation for C16.1a dry-run/create."""
from dataclasses import asdict
import json
import os
from pathlib import Path
from unittest.mock import patch

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
    genesis_feature_source_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch
from bilqis_mlx.state_dag import persist
from bilqis_mlx.vocabulary_growth import digest

from .create_resume_support import BamfCreateResumeCase, TOPOLOGY


class BamfPersistedSourceTests(BamfCreateResumeCase):
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
