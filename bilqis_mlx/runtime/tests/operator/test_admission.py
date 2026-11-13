"""A declarative unknown grade uses the same durable runtime admission gate."""
from dataclasses import asdict, replace
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.factory.answers import (
    AnswerModality, AnswerModalityRegistry, RegisteredAnswerModality,
    fixed_domain,
)
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.tests.test_execution_plan import (
    _synthetic_course, _synthetic_registry,
)
from bilqis_mlx.factory.tests.support import synthetic_release_inputs
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.admission import (
    _executable_factory_admission, _factory_admission,
    _persist_executable_factory_release, _read_executable_factory_release,
    _require_executable_factory_admission, _require_factory_admission,
)


def _executable_fixture(seed=17):
    course = _synthetic_course(6)
    registry = _synthetic_registry()
    curriculum, bindings = from_legacy_course(course)
    graph = {
        "tokens": [
            "fixture.padding",
            "cogal.value.false",
            "cogal.value.true",
        ],
    }
    answers = AnswerModalityRegistry((
        RegisteredAnswerModality(
            AnswerModality("binary", "answer.binary/v1", "a" * 64),
            fixed_domain(("FALSE", "TRUE")),
            lambda value: {
                "FALSE": "cogal.value.false",
                "TRUE": "cogal.value.true",
            }[value]),
    ))
    release = compile_executable_factory_release(
        curriculum, bindings, CurriculumProfile.full(),
        registry, answers, source_root=None, graph=graph,
        verification_seed=seed)
    return release, graph


class ExecutableMigrationTests(unittest.TestCase):
    def test_legacy_live_rubric_rebinds_without_changing_parent_evidence(self):
        from bilqis_mlx.runtime.release_adoption import _migrate_executable_release
        from bilqis_mlx.runtime.state import _fingerprint
        from bilqis_mlx.curriculum.scheduler import start_new
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        release, graph = _executable_fixture()
        program = schedule_program_from_executable_release(release)
        course = _synthetic_course(6)
        student = Checkpoint("c" * 64, "bundles/parent", 23, True)
        school = start_new(course, student)
        receipt = dict(school=asdict(school), semantic_graph_sha256=_fingerprint(graph),
                       live_rubric_sha256="d" * 64, last_exam={"historical": "unchanged"})
        original = deepcopy(receipt)
        with tempfile.TemporaryDirectory() as temporary, patch('bilqis_mlx.compatibility.executable_projection.compile_projected_executable_release',
                return_value=(release, program, None)):
            migrated, _, _, rebound = _migrate_executable_release(
                Path(temporary), receipt, course, course, None, graph)
        self.assertEqual(migrated["live_rubric_sha256"], program.grades[0].assessment_sha256)
        self.assertEqual(rebound.current_student, student)
        self.assertEqual(migrated["last_exam"], receipt["last_exam"])
        self.assertEqual(receipt, original)

        from bilqis_mlx.runtime.session import _resume_admitted_student
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_file = _persist_executable_factory_release(root, release)
            saved = {**migrated, "factory_release_file": release_file, "generation": 1}
            with patch("bilqis_mlx.runtime.session._state_dag.read_current", return_value=saved), \
                    patch("bilqis_mlx.runtime.session._resume",
                          return_value=("params", "optimizer", graph, saved)) as resume, \
                    patch("bilqis_mlx.compatibility.executable_projection.legacy_course_for_profile",
                          side_effect=AssertionError("v2 re-entered legacy projection")), \
                    patch("bilqis_mlx.compatibility.executable_projection.resolve_legacy_resume_course",
                          side_effect=AssertionError("v2 re-entered legacy decoding")):
                for _ in range(2):
                    result = _resume_admitted_student(root, {}, course, course, None, "d" * 64)
                    self.assertEqual(result[-1], program)
                    self.assertEqual(resume.call_args.args[2], program)
                    self.assertIsNone(resume.call_args.kwargs["admitted_courses"])
                self.assertEqual(resume.call_count, 2)


class RuntimeAdmissionTests(unittest.TestCase):
    def setUp(self):
        course, self.registry = synthetic_release_inputs()
        grade = course.grades[0]
        caps = tuple(replace(cap, id=cap.id.replace("A.", "Z.")) for cap in grade.capabilities)
        self.course = replace(course, grades=(replace(
            grade, id="Z", capabilities=caps,
            exam_item_counts=tuple((cap.id, 4) for cap in caps)),))
        self.student = Checkpoint("a" * 64, "bundles/fixture", 7, True)

    def admission(self, root):
        release, path, admission = _factory_admission(
            root, self.course, self.student, "b" * 64, registry=self.registry)
        receipt = {"factory_release_sha256": release.release_sha256,
                   "factory_release_file": path, "factory_admission": asdict(admission),
                   "semantic_graph_sha256": "b" * 64,
                   "school": {"current_student": asdict(self.student)}}
        return release, receipt

    def test_synthetic_grade_admits_and_reads_back_without_a_live_grade_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release, receipt = self.admission(root)
            restored = _require_factory_admission(
                root, json.loads(json.dumps(receipt)), self.course, registry=self.registry)
            self.assertEqual(restored, release)
            self.assertEqual(restored.grades[0].grade_id, "Z")

    def test_schema_tamper_and_same_step_student_substitution_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, receipt = self.admission(root)
            receipt["factory_admission"]["student_sha256"] = "c" * 64
            with self.assertRaisesRegex(ValueError, "FACTORY_ADMISSION_BASELINE_DRIFT"):
                _require_factory_admission(root, receipt, self.course, registry=self.registry)
            receipt["factory_admission"]["student_sha256"] = self.student.sha256
            path = root / receipt["factory_release_file"]
            payload = json.loads(path.read_text())
            payload["schema"] = "unrelated.schema/v999"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "FACTORY_RELEASE_DURABLE_SCHEMA_INVALID"):
                _require_factory_admission(root, receipt, self.course, registry=self.registry)

    def test_optional_teaching_gate_reads_v2_and_checks_the_released_options(self):
        from bilqis_mlx.runtime.admission import admitted_release_supports_teaching_option
        from types import SimpleNamespace

        source = SimpleNamespace(teaching_option_ids=("source.single-event/v1",))
        release = SimpleNamespace(source_adapters=(source,))
        with patch('bilqis_mlx.runtime.admission._read_executable_factory_release_artifact',
                   return_value=release), patch('bilqis_mlx.runtime.admission._read_factory_release',
                   side_effect=AssertionError('v2 must not enter the legacy decoder')):
            receipt = {"factory_admission_v2": {}}
            self.assertTrue(admitted_release_supports_teaching_option(Path('/unused'), receipt))
            self.assertTrue(admitted_release_supports_teaching_option(
                Path('/unused'), receipt, "source.single-event/v1"))
            self.assertFalse(admitted_release_supports_teaching_option(
                Path('/unused'), receipt, "unreleased"))
        from bilqis_mlx.cli import parse_args
        args = parse_args(['train', '--human-run', '--source-teaching-enrichment'])
        self.assertTrue(args.boolean_association_bridge)

    def test_v2_executable_release_persists_and_cold_reads_without_course_rebuild(self):
        release, graph = _executable_fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release_file = _persist_executable_factory_release(root, release)
            receipt = {
                "factory_release_sha256": release.release_sha256,
                "factory_release_file": release_file,
            }
            restored = _read_executable_factory_release(
                root, receipt, graph)
            self.assertEqual(restored, release)
            self.assertEqual(
                restored.execution_plan.curriculum_sha256,
                release.curriculum.digest())

    def test_cli_preflight_and_artifact_readback_preserve_all_run_bytes(self):
        import io
        from contextlib import redirect_stdout
        from bilqis_mlx.presentation.operator_cli import preflight as cli
        from bilqis_mlx.runtime.admission import _read_executable_factory_release_artifact

        release, graph = _executable_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release_file = _persist_executable_factory_release(root, release)
            receipt = dict(factory_release_sha256=release.release_sha256,
                           factory_release_file=release_file, factory_admission_v2={},
                           school={"current_student": asdict(self.student)})
            original = deepcopy(receipt)
            (root / "state.json").write_text(json.dumps(receipt))
            (root / "model-and-own-adamw.safetensors").write_bytes(b"preserved-disposable-bytes")
            (root / "events.jsonl").write_text('{"historical":true}\n')
            snapshot = {"factory": {"active_grades": ["Z"], "canonical_grades": [],
                "profile_id": "fixture", "active_capabilities": ["Z.C0"]}}
            before = {str(path.relative_to(root)): path.read_bytes()
                      for path in root.rglob("*") if path.is_file()}
            with patch.object(cli, "_inspect", return_value=snapshot), \
                    patch.object(cli, "read_current", return_value=receipt), \
                    patch.object(cli, "_boolean_revision_preflight", return_value={}), \
                    patch.object(cli, "assert_headroom", return_value={}), \
                    patch("bilqis_mlx.grade_a_manifest.verify_manifest", return_value={
                        "verified_items": 72, "exam_rubric_sha256": "a" * 64}), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(cli.preflight(root, resume=True, verify_source=True), 0)
                self.assertEqual(_read_executable_factory_release_artifact(root, receipt), release)
            self.assertEqual(receipt, original)
            self.assertEqual({str(path.relative_to(root)): path.read_bytes()
                              for path in root.rglob("*") if path.is_file()}, before)

    def test_historical_qualification_preserves_receipt_and_run_bytes(self):
        from types import SimpleNamespace
        from bilqis_mlx.compatibility.executable_projection import preflight_sealed_v1_migration
        from bilqis_mlx.curriculum.scheduler import start_new
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release

        release, graph = _executable_fixture()
        course = _synthetic_course(6)
        receipt = dict(school=asdict(start_new(course, self.student)),
                       semantic_graph_sha256=_fingerprint(graph))
        original = deepcopy(receipt)
        program = schedule_program_from_executable_release(release)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "state.json").write_text(json.dumps(receipt))
            before = (root / "state.json").read_bytes()
            with patch("bilqis_mlx.runtime.admission._verified_legacy_upgrade_release",
                       return_value=SimpleNamespace(course=course)), \
                    patch("bilqis_mlx.runtime.assessment._verify_saved_cohort"), \
                    patch("bilqis_mlx.grade_a_probe.read_sources", return_value=(None, None, graph, None, None)), \
                    patch("bilqis_mlx.compatibility.executable_projection.verify_legacy_resume_binding"), \
                    patch("bilqis_mlx.grade_a_release.accepted_grade_a", return_value=course), \
                    patch("bilqis_mlx.compatibility.live_releases.initial_course", return_value=course), \
                    patch("bilqis_mlx.compatibility.executable_projection.compile_projected_executable_release",
                          return_value=(release, program, None)):
                result = preflight_sealed_v1_migration(root, receipt, {}, None)
            self.assertEqual(result["neural_updates"], 0)
            self.assertEqual(result["saved_course_sha256"], course.digest())
            self.assertEqual(result["source_qualified_successor_sha256"], release.release_sha256)
            self.assertEqual(receipt, original)
            self.assertEqual((root / "state.json").read_bytes(), before)
            self.assertEqual(tuple(path.name for path in root.iterdir()), ("state.json",))

    def test_v2_readback_rejects_schema_and_loaded_catalog_drift(self):
        release, graph = _executable_fixture(seed=19)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release_file = _persist_executable_factory_release(root, release)
            receipt = {
                "factory_release_sha256": release.release_sha256,
                "factory_release_file": release_file,
            }
            changed_graph = {
                "tokens": [
                    "fixture.padding",
                    "cogal.value.true",
                    "cogal.value.false",
                ],
            }
            with self.assertRaisesRegex(
                    ValueError, "FACTORY_EXECUTABLE_RELEASE_CATALOG_DRIFT"):
                _read_executable_factory_release(
                    root, receipt, changed_graph)

            path = root / release_file
            payload = json.loads(path.read_text())
            payload["schema"] = "unrelated.schema/v999"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(
                    ValueError, "FACTORY_EXECUTABLE_RELEASE_DURABLE_SCHEMA_INVALID"):
                _read_executable_factory_release(root, receipt, graph)

    def test_v2_graph_substitution_and_false_admission_digest_fail_closed(self):
        release, graph = _executable_fixture(seed=37)
        changed = {**graph, "nodes": [{"meaning": "substituted"}]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "SEMANTIC_GRAPH_DRIFT"):
                _executable_factory_admission(
                    root, release, self.student, _fingerprint(changed), changed)
            with self.assertRaisesRegex(ValueError, "SEMANTIC_GRAPH_DRIFT"):
                _executable_factory_admission(
                    root, release, self.student, "b" * 64, graph)
            self.assertFalse((root / "factory-releases").exists())
            _, release_file, admission = _executable_factory_admission(
                root, release, self.student, _fingerprint(graph), graph)
            receipt = dict(factory_release_sha256=release.release_sha256,
                           factory_release_file=release_file,
                           factory_admission_v2={**asdict(admission),
                                                 "semantic_graph_sha256": _fingerprint(changed)},
                           semantic_graph_sha256=_fingerprint(changed),
                           school={"current_student": asdict(self.student)})
            with self.assertRaisesRegex(ValueError, "SEMANTIC_GRAPH_DRIFT"):
                _require_executable_factory_admission(root, receipt, graph)

    def test_v2_admission_binds_release_plan_catalog_graph_and_student(self):
        release, graph = _executable_fixture(seed=23)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, release_file, admission = _executable_factory_admission(
                root, release, self.student, _fingerprint(graph), graph)
            receipt = {
                "factory_release_sha256": release.release_sha256,
                "factory_release_file": release_file,
                "factory_admission_v2": asdict(admission),
                "semantic_graph_sha256": _fingerprint(graph),
                "school": {"current_student": asdict(self.student)},
            }
            restored = _require_executable_factory_admission(
                root, json.loads(json.dumps(receipt)), graph)
            self.assertEqual(restored, release)
            self.assertEqual(
                admission.execution_plan_sha256,
                release.execution_plan.digest())
            self.assertEqual(
                admission.semantic_catalog_sha256,
                release.semantic_catalog_sha256)

    def test_v2_admission_rejects_same_step_student_substitution(self):
        release, graph = _executable_fixture(seed=29)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, release_file, admission = _executable_factory_admission(
                root, release, self.student, _fingerprint(graph), graph)
            receipt = {
                "factory_release_sha256": release.release_sha256,
                "factory_release_file": release_file,
                "factory_admission_v2": {
                    **asdict(admission),
                    "student_sha256": "c" * 64,
                },
                "semantic_graph_sha256": _fingerprint(graph),
                "school": {"current_student": asdict(self.student)},
            }
            with self.assertRaisesRegex(
                    ValueError, "FACTORY_EXECUTABLE_ADMISSION_BASELINE_DRIFT"):
                _require_executable_factory_admission(root, receipt, graph)
