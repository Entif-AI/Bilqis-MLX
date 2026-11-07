"""Trainer contract tests: disposable toy optimization, never real student steps."""
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
import io
import inspect
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from bilqis_mlx import trainer as trainer
from bilqis_mlx.state_dag import read_current, read_generation
from bilqis_mlx.grade_a_release import accepted_grade_a, RELEASE, AUTHORITY
from bilqis_mlx.live_grade_a import live_course, RELEASE as LIVE_RELEASE
from bilqis_mlx.trainer import (
    _make_batch, _persist, _seed, _state_from_json, _train_step,
    _take_visit, _take_exam,
    choose_lesson_batch,
    operator_lock, prepare_source,
    _initial_model, _bundle_pointer, _resume, _durable_json,
    _clean_staged_bundles, _quarantine_newer_uncommitted_bundles,
)
from bilqis_mlx.learning.learning_experiment import reserve_weakness_targets
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.source import AUDITED_PARENT
from bilqis_mlx.curriculum.scheduler import start_new, visit
from bilqis_mlx.learning.capability_frontier import promote
from tests.support.executable_school import admit_executable_school
from bilqis_mlx.diagnostics import DiagnosticStatus

ROOT = Path(__file__).resolve().parents[2] / "vendor" / "legacy-v16"
SOURCE = ROOT / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"
MANIFEST = Path(__file__).resolve().parents[2] / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"

class GradeATrainerExecutionTests(unittest.TestCase):
    def _fixture(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        import numpy as np
        import torch

        mx.set_default_device(mx.cpu)
        manifest, historical_course, engine, _sha, teacher, _provenance = prepare_source(
            ROOT, SOURCE, MANIFEST)
        course = live_course(historical_course)
        graph = torch.load(SOURCE, map_location="cpu", weights_only=True)["graph"]
        d = 12
        shapes = {
            "embedding.weight": (222, d), "position.weight": (96, d),
            "norm.weight": (d,),
            "blocks.0.n1.weight": (d,), "blocks.0.n2.weight": (d,),
            "blocks.0.qkv.weight": (3*d, d), "blocks.0.proj.weight": (d, d),
            "blocks.0.up.weight": (2*d, d), "blocks.0.down.weight": (d, 2*d),
        }
        rng = np.random.default_rng(888)
        params = {
            name: mx.array(rng.normal(0, .015, size=shape).astype(np.float32)
                           if len(shape) > 1 else np.ones(shape, dtype=np.float32))
            for name, shape in shapes.items()}
        opt = optim.AdamW(learning_rate=.00013, bias_correction=True)
        opt.update(params, {name: mx.zeros_like(arr) for name, arr in params.items()})
        mx.eval(params, opt.state)
        initial = Checkpoint("f" * 64, "fixture-bundle", 1, True)
        school = start_new(course, initial)
        control = {
            "schema": "synthetic-fixture", "run_id": "synthetic-execution",
            "generation": 1, "school": asdict(school),
            "teacher": teacher, "config": {"heads": 3, "layers": 1},
            "source_manifest_sha256": manifest["manifest_sha256"],
            "answer_ids": [6, 7],
            "model_bundle": initial.filename, "last_exam": None,
            "curriculum_mode": LIVE_RELEASE,
            "result": "ACTIVE_GRADE_A",
        }
        return mx, manifest, course, engine, teacher, graph, params, opt, initial, control

    def _admit(self, run_dir, control, course, graph, params, initial):
        release, program, _ = trainer.compile_projected_executable_release(
            course, course, ROOT, graph)
        school = start_new(program, initial)
        release, release_file, admission = trainer._executable_factory_admission(
            run_dir, release, initial, trainer._fingerprint(graph), graph)
        parameter_shapes = {name: list(value.shape) for name, value in params.items()}
        control.update({
            "school": asdict(school),
            "parameter_shapes": parameter_shapes,
            "semantic_graph_sha256": trainer._fingerprint(graph),
            "factory_release_sha256": release.release_sha256,
            "factory_release_file": release_file,
            "factory_release_schema": release.schema,
            "factory_admission_v2": asdict(admission),
            "championship_school_identity": trainer.build_school_identity(
                course_sha256=release.execution_plan.curriculum_sha256,
                semantic_graph_sha256=trainer._fingerprint(graph),
                parameter_shapes=parameter_shapes,
                factory_release_sha256=release.release_sha256),
        })
        return admit_executable_school(run_dir, control, course, course, ROOT, graph)

    def _visit_and_exam(self, mx, run_dir, control, manifest, course, engine,
                        teacher, params, opt, graph):
        with redirect_stdout(io.StringIO()):
            for _ in range(6):
                control = _take_visit(
                    mx, run_dir, control, manifest, course, engine,
                    params, opt, graph, steps_per_visit=1, batch_size=4,
                    reserve_gib=0., source_root=ROOT)
            self.assertEqual(control["school"]["stage"], "ASSESS_MAIN")
            self.assertEqual(control["school"]["visits"], 6)
            self.assertEqual(control["teacher"]["events"], teacher["events"] + 6)
            self.assertEqual(int(opt.state["step"].item()), 7)
            self.assertFalse((run_dir / "bundles").exists(),
                             "Unscored visits must not create a candidate checkpoint")
            return _take_exam(
                mx, run_dir, control, manifest, course, ROOT, SOURCE,
                params, opt, graph, reserve_gib=0.)

    def _assert_exam(self, run_dir, completed, program):
        self.assertEqual(completed["last_exam"]["exam_rubric_sha256"],
                         program.grades[0].assessment_sha256)
        self.assertEqual(sum(score["total"] for score in
                             completed["last_exam"]["scores"].values()), 72)
        self.assertEqual(completed["school"]["current_student"]["optimizer_step"], 7)
        self.assertEqual(read_current(run_dir), completed)
        self.assertEqual(len(list((run_dir / "bundles").iterdir())), 1)
        self.assertEqual(len(completed["capability_best"]), 6)
        saved = json.loads((run_dir / completed["last_exam"]["cohort_file"]).read_text())
        self.assertEqual(completed["last_exam"]["generator_version"],
                         saved["generator_version"])
        self.assertEqual(saved["generator_version"], saved["source_sha256"])
        self.assertEqual(completed["last_exam"]["schema"], saved["schema"])
        self.assertEqual(len(saved["rows"]), 72)
        self.assertEqual(saved["cohort_sha256"], completed["last_exam"]["cohort_sha256"])
        events = [json.loads(line) for line in
                  (run_dir / "events.jsonl").read_text().splitlines()]
        visits = [event for event in events
                  if event.get("event") == "SCHOOL_TEACHER_VISIT_COMMITTED"]
        self.assertEqual(len(visits), 6)
        for event in visits:
            method = event["lesson_methodology"]
            self.assertEqual(method["optimizer_batches_observed"], 1)
            self.assertEqual(method["delivered_examples"], 4)
            self.assertTrue(method["introductory_full_grade_pass"])
            s4, s5 = method["findings"]
            self.assertEqual(s4["status"], DiagnosticStatus.NOT_APPLICABLE)
            self.assertNotEqual(s5["status"], DiagnosticStatus.NOT_MEASURED)
        return saved

    def _recover_if_needed(self, mx, run_dir, completed, saved_cohort, manifest,
                           course, engine, params, opt, graph):
        if completed["school"]["stage"] != "RECOVERY_1":
            return
        with redirect_stdout(io.StringIO()):
            for _ in range(3):
                completed = _take_visit(
                    mx, run_dir, completed, manifest, course, engine,
                    params, opt, graph, steps_per_visit=1, batch_size=4,
                    reserve_gib=0., source_root=ROOT)
            self.assertEqual(len(list((run_dir / "bundles").iterdir())), 1)
            completed = _take_exam(
                mx, run_dir, completed, manifest, course, ROOT, SOURCE,
                params, opt, graph, reserve_gib=0.)
        self.assertNotEqual(completed["last_exam"]["cohort_sha256"],
                            saved_cohort["cohort_sha256"])
        outcomes = completed["last_exam"]["teacher_outcomes"]
        self.assertEqual(len(outcomes), 3)
        self.assertEqual({outcome["attribution"] for outcome in outcomes},
                         {"NOT_MEASURED_CHANGED_EXAM"})
        self.assertTrue(all(len(outcome["decision_ids"]) == 1 for outcome in outcomes))
        self.assertEqual(len(completed["last_exam"]["incumbent_comparisons"]), 1)
        self.assertEqual(completed["last_exam"]["incumbent_comparisons"][0]["cohort_sha256"],
                         completed["last_exam"]["candidate_cohort_sha256"])
        self.assertNotEqual(completed["last_exam"]["cohort_sha256"],
                            completed["last_exam"]["candidate_cohort_sha256"])
        retained = {item["checkpoint"]["filename"]
                    for item in completed["capability_best"].values()}
        retained.add(completed["model_bundle"])
        self.assertEqual(len(list((run_dir / "bundles").iterdir())), len(retained))

    @unittest.skipUnless(SOURCE.is_file(), "Pinned historic source not mounted")
    def test_synthetic_end_to_end_six_visits_generated_grade_exam(self):
        """The real training path executes, but only on freshly invented toy weights."""
        fixture = self._fixture()
        mx, manifest, course, engine, teacher, graph, params, opt, initial, control = fixture
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            control, _release, program = self._admit(
                run_dir, control, course, graph, params, initial)
            completed = self._visit_and_exam(
                mx, run_dir, control, manifest, course, engine,
                teacher, params, opt, graph)
            saved_cohort = self._assert_exam(run_dir, completed, program)
            self._recover_if_needed(
                mx, run_dir, completed, saved_cohort, manifest,
                course, engine, params, opt, graph)
