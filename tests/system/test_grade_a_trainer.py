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
from bilqis_mlx.grade_a_release import accepted_grade_a, RELEASE, AUTHORITY
from bilqis_mlx.live_grade_a import live_course, RELEASE as LIVE_RELEASE
from bilqis_mlx.trainer import (
    _make_batch, _persist, _seed, _state_from_json, _train_step,
    _take_visit, _take_exam,
    choose_lesson_batch, replay_missed_lessons,
    operator_lock, prepare_source,
    _initial_model, _bundle_pointer, _resume, _durable_json,
    _clean_staged_bundles, _quarantine_newer_uncommitted_bundles,
)
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.source import AUDITED_PARENT
from bilqis_mlx.curriculum.scheduler import start_new, visit
from bilqis_mlx.learning.capability_frontier import promote
from bilqis_mlx.diagnostics import DiagnosticStatus

ROOT = Path(__file__).resolve().parents[2] / "vendor" / "legacy-v16"
SOURCE = ROOT / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"
MANIFEST = Path(__file__).resolve().parents[2] / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


def _historical_v1_receipt(*, manifest, school, base, frontier, teacher,
                           teacher_sha, provenance, config, parameters, graph,
                           answer_ids):
    semantic_graph_sha256 = __import__(
        "bilqis_mlx.trainer", fromlist=["_fingerprint"])._fingerprint(graph)
    return {
        "schema": "bilqis.mlx.human-grade-a-trainer/v1",
        "generation": 1, "run_id": "historic-disposable",
        "accepted_authority": AUTHORITY,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "teacher_source_sha256": teacher_sha,
        "school": asdict(school), "model_bundle": base.filename,
        "capability_best": frontier, "teacher": teacher,
        "teacher_provenance": provenance, "config": config,
        "parameter_shapes": {name: list(value.shape)
                             for name, value in parameters.items()},
        "semantic_graph_sha256": semantic_graph_sha256,
        "answer_ids": answer_ids, "result": "ACTIVE_GRADE_A",
        "last_exam": None,
    }


class GradeATrainerContractTests(unittest.TestCase):
    def test_fixed_frontier_uses_newer_retained_parent_predictions(self):
        from bilqis_mlx.generated_assessment import make_cohort
        rows = [
            {"id": "B.NOT:0", "capability": "B.NOT", "gold": "TRUE"},
            {"id": "B.NOT:1", "capability": "B.NOT", "gold": "FALSE"},
        ]
        cohort = make_cohort(rows, generator_version="fixture", seed=7,
                             rubric_version="fixture-rubric")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "cohorts").mkdir()
            (root / "cohorts" / f"{cohort.digest}.json").write_text(
                json.dumps({"schema": "fixture-rubric", "generator_version": "fixture",
                            "seed": 7, "cohort_sha256": cohort.digest, "rows": rows}))
            receipt = {"config": {}, "answer_ids": [], "last_exam": {
                "student_sha256": "a" * 64, "optimizer_step": 13,
                "cohort_sha256": cohort.digest,
                "cohort_file": f"cohorts/{cohort.digest}.json",
                "scores": {"B.NOT": {"correct": 2, "total": 2}},
                "misses_for_teacher": [],
            }}
            school = SimpleNamespace(current_student=SimpleNamespace(
                sha256="b" * 64, optimizer_step=14))
            parent = {"B.NOT:0": "FALSE", "B.NOT:1": "FALSE"}
            candidate = {"B.NOT:0": "FALSE", "B.NOT:1": "TRUE"}

            def predict(_mx, weights, selected, _config, _answers):
                expected = parent if weights == "parent" else candidate
                return {row["id"]: expected[row["id"]] for row in selected}

            with (patch.object(trainer, "_predictions", side_effect=predict),
                  patch("bilqis_mlx.learning.fragile_replay.load_replay_rows",
                        return_value=())):
                fixed, replay, frontier = trainer._candidate_fixed_evidence(
                    None, root, receipt, None, school, "B.NOT", "parent",
                    "candidate", SimpleNamespace())
        self.assertEqual(fixed["before"], 1)
        self.assertEqual(fixed["after"], 0)
        self.assertEqual(frontier["regressions"], [
            {"id": "B.NOT:1", "capability": "B.NOT"}])
        self.assertEqual(replay["status"], "NOT_MEASURED")
    def test_candidate_frontier_protects_other_grades_when_active_grade_absent(self):
        rows = (
            {"id": "A.LINK:0", "capability": "A.LINK", "gold": "TRUE"},
            {"id": "C.MUL:0", "capability": "C.MUL", "gold": "FALSE"},
        )
        parent_predictions = {row["id"]: row["gold"] for row in rows}
        receipt = {
            "config": {}, "answer_ids": {},
            "last_exam": {"cohort_sha256": "a" * 64,
                          "student_sha256": "b" * 64,
                          "optimizer_step": 123},
        }
        school = SimpleNamespace(current_student=SimpleNamespace(
            sha256="b" * 64, optimizer_step=123))
        with (
            patch("bilqis_mlx.fixed_frontier.load_frontier",
                  return_value=(rows, parent_predictions)),
            patch.object(
                trainer, "_predictions",
                side_effect=lambda _mx, _bundle, selected, _config, _answers: {
                    row["id"]: row["gold"] for row in selected}),
            patch("bilqis_mlx.learning.fragile_replay.load_replay_rows",
                  return_value=()),
        ):
            fixed, replay, frontier = trainer._candidate_fixed_evidence(
                None, Path("."), receipt, None, school, "B.NOT",
                object(), object(), SimpleNamespace())
        self.assertEqual(fixed, {
            "status": "NOT_MEASURED",
            "reason": "ACTIVE_GRADE_ABSENT_FROM_FIXED_FRONTIER",
        })
        self.assertEqual(replay["status"], "NOT_MEASURED")
        self.assertEqual(frontier["status"], "MEASURED")
        self.assertEqual(frontier["before_correct"], 2)
        self.assertEqual(frontier["after_correct"], 2)

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_human_acceptance_admits_exact_proposal_not_new_exams(self):
        course = accepted_grade_a(self.manifest)
        self.assertTrue(course.executable)
        self.assertEqual(course.version, RELEASE)
        self.assertFalse(course.program_complete)
        self.assertEqual(course.grades[0].assessment_sha256,
                         self.manifest["exam_rubric_sha256"])
        tampered = deepcopy(self.manifest)
        tampered["exam_count"] = 12
        with self.assertRaisesRegex(ValueError, "SOURCE_INVENTORY_MISMATCH"):
            accepted_grade_a(tampered)

    def test_exam_reuse_identity_requires_same_checkpoint_and_exam_contract(self):
        school = type("School", (), {
            "grade": "B",
            "grade_exam_epoch": 7,
            "current_student": Checkpoint("a" * 64, "bundles/current", 123, True),
        })()
        exam = {
            "assessment_grade": "B",
            "grade_exam_epoch": 7,
            "student_sha256": "a" * 64,
            "optimizer_step": 123,
            "exam_rubric_sha256": "b" * 64,
            "assessment_scope_sha256": "c" * 64,
            "cohort_sha256": "d" * 64,
        }
        receipt = {"last_exam": exam}
        self.assertEqual(
            trainer._reusable_exam_identity(
                receipt, school, rubric_sha256="b" * 64,
                assessment_scope_sha256="c" * 64),
            ("a" * 64, 123, "d" * 64, "b" * 64, "c" * 64),
        )
        changed = type("School", (), {
            "grade": "B",
            "grade_exam_epoch": 7,
            "current_student": Checkpoint("e" * 64, "bundles/new", 124, True),
        })()
        self.assertIsNone(trainer._reusable_exam_identity(
            receipt, changed, rubric_sha256="b" * 64,
            assessment_scope_sha256="c" * 64))

    def test_routine_exam_reuse_shortcut_is_not_part_of_active_take_exam_path(self):
        source = inspect.getsource(trainer._take_exam)
        self.assertNotIn("_verified_reusable_exam(", source)
        self.assertNotIn("_reuse_unchanged_exam_boundary(", source)

    def test_operator_stop_does_not_discard_fixed_promotion_attempt(self):
        source = inspect.getsource(trainer._flush_working_student)
        self.assertNotIn('pop("qualification_cohort"', source)
        self.assertNotIn("pop('qualification_cohort'", source)

    def test_historical_manifest_partition_remains_unchanged_as_evidence(self):
        cap = "A.MEMBER"
        rows = [row for row in self.manifest["training_rows"]
                if row["capability"] == cap]
        exam_ids = {row["id"] for row in self.manifest["examination_rows"]}
        policy = {"depth": 4, "contrast": 1.0}
        batch = choose_lesson_batch(rows, policy, 554322, batch_size=32)
        self.assertEqual(len(batch), 32)
        self.assertEqual(sum(r["gold"] == "TRUE" for r in batch), 16)
        self.assertEqual(sum(r["gold"] == "FALSE" for r in batch), 16)
        self.assertFalse({r["id"] for r in batch} & exam_ids)
        self.assertEqual(batch, choose_lesson_batch(rows, policy, 554322, batch_size=32))
        tokens, lengths, labels = _make_batch(batch)
        self.assertEqual(tokens.shape[0], 32)
        self.assertTrue((lengths >= 1).all())
        self.assertEqual(sum(labels), 16)

    def test_distinct_same_label_exam_misses_all_replay_without_skew(self):
        chosen = ([{"id": f"t{i}", "gold": "TRUE"} for i in range(8)] +
                  [{"id": f"f{i}", "gold": "FALSE"} for i in range(8)])
        priority = [{"id": f"miss-{i}", "gold": "TRUE"} for i in range(3)]
        mixed = replay_missed_lessons(chosen, priority)
        self.assertEqual({p["id"] for p in priority} & {p["id"] for p in mixed},
                         {p["id"] for p in priority})
        self.assertEqual(sum(r["gold"] == "TRUE" for r in mixed), 8)
        full_class = [{"id": f"miss-all-{i}", "gold": "TRUE"} for i in range(8)]
        no_quarter_ceiling = replay_missed_lessons(chosen, full_class)
        self.assertEqual({p["id"] for p in full_class} &
                         {p["id"] for p in no_quarter_ceiling},
                         {p["id"] for p in full_class})

    def test_failed_bundle_write_never_enters_active_bundles(self):
        def fail_after_partial_stage(directory, *args, **kwargs):
            directory.mkdir(parents=True)
            (directory / "manifest.json").write_text("partial stage")
            raise OSError("injected disk interruption")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("bilqis_mlx.trainer.save_new_bundle",
                       side_effect=fail_after_partial_stage):
                with self.assertRaisesRegex(OSError, "injected disk interruption"):
                    _bundle_pointer(root, "interrupted-unique", {}, None, {},
                                    reserve_gib=0.)
            self.assertFalse((root / "bundles").exists())
            self.assertTrue((root / ".bundle-staging/interrupted-unique/manifest.json").is_file())
            self.assertEqual(_clean_staged_bundles(root),
                             {"discarded": ("interrupted-unique",), "quarantined": ()})
            self.assertFalse((root / ".bundle-staging").exists())
            # Failure after binary materialization retains it for an explicit
            # human recovery decision, outside active candidate retirement.
            staged = root / ".bundle-staging/completed-weights"
            staged.mkdir(parents=True)
            (staged / "model-and-own-adamw.safetensors").write_bytes(b"toy-weights")
            (staged / "manifest.json").write_text("partial")
            self.assertEqual(_clean_staged_bundles(root),
                             {"discarded": (), "quarantined": ("completed-weights",)})
            self.assertEqual((root / ".bundle-quarantine/completed-weights/"
                              "model-and-own-adamw.safetensors").read_bytes(),
                             b"toy-weights")

    def test_uncommitted_published_newer_student_is_saved_from_retirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            late = root / "bundles/candidate-after-crash"
            late.mkdir(parents=True)
            details = {"source_digest": AUDITED_PARENT.sha256,
                       "optimizer_step": 101, "safetensors_sha256": "f" * 64}
            with patch("bilqis_mlx.trainer.load_semantically_bound_bundle",
                       return_value=({}, None, details, {})):
                found = _quarantine_newer_uncommitted_bundles(root, set(), 100)
            self.assertEqual(found, ("candidate-after-crash",))
            self.assertFalse(late.exists())
            self.assertTrue((root / ".bundle-quarantine/candidate-after-crash").is_dir())
            event = json.loads((root / "events.jsonl").read_text().splitlines()[-1])
            self.assertEqual(event["optimizer_step"], 101)
            self.assertEqual(event["prior_committed_optimizer_step"], 100)

    def test_finder_metadata_cannot_block_bundle_custody_or_hide_unknown_files(self):
        from bilqis_mlx.learning.capability_frontier import retirement_plan, historical_frontier
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundles = root / "bundles"
            bundles.mkdir()
            finder = bundles / ".DS_Store"
            finder.write_bytes(b"Finder bookkeeping, not a student")
            self.assertEqual(retirement_plan(root, set()), ())
            self.assertEqual(historical_frontier(root), {})
            self.assertEqual(_quarantine_newer_uncommitted_bundles(root, set(), 20), ())
            self.assertFalse(finder.exists())
            unknown = bundles / "unexplained.bin"
            unknown.write_bytes(b"never silently ignore unknown files")
            with self.assertRaisesRegex(ValueError, "UNCOMMITTED_BUNDLE_UNSAFE_PATH"):
                _quarantine_newer_uncommitted_bundles(root, set(), 20)
            with self.assertRaisesRegex(ValueError, "CUSTODY_UNRECOGNIZED_BUNDLE"):
                retirement_plan(root, set())
            unknown.unlink()
            finder.symlink_to("/tmp/non-existent-unsafe-target")
            with self.assertRaisesRegex(ValueError, "UNCOMMITTED_BUNDLE_UNSAFE_PATH"):
                _quarantine_newer_uncommitted_bundles(root, set(), 20)
            self.assertTrue(finder.is_symlink())

    def test_snapshots_are_immutable_generations_with_one_latest_pointer(self):
        course = accepted_grade_a(self.manifest)
        student = Checkpoint("e"*64, "bundles/fixture", 116760, True)
        state = start_new(course, student)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = {"schema":"synthetic", "generation":1,
                     "school":self._serial(state)}
            _persist(root, first)
            normalized = json.loads(json.dumps(first))
            self.assertEqual(json.loads((root/"state.json").read_text()),normalized)
            second = {**first, "generation":2}
            _persist(root, second)
            self.assertEqual(json.loads((root/"state.json").read_text()),
                             json.loads(json.dumps(second)))
            self.assertEqual(json.loads((root/"states/0000001.json").read_text()),
                             normalized)
            self.assertEqual(_state_from_json(second["school"], course),state)
            self.assertEqual(_persist(root, second), json.loads(json.dumps(second)))
            with self.assertRaisesRegex(ValueError, "IMMUTABLE_GENERATION_COLLISION"):
                _persist(root, {**second, "model_bundle": "bundles/incorrect"})
            with operator_lock(root):
                with self.assertRaisesRegex(ValueError, "ANOTHER_OPERATOR_ACTIVE"):
                    with operator_lock(root):
                        pass

    @staticmethod
    def _serial(state):
        from dataclasses import asdict
        return asdict(state)

    @unittest.skipUnless(SOURCE.is_file(), "Original teacher/archive unavailable")
    def test_inherited_teacher_retains_original_policy_observations(self):
        manifest, old_course, engine, sha, teacher, provenance = prepare_source(
            ROOT, SOURCE, MANIFEST)
        course = live_course(old_course)
        # Prove the active path draws from constructors, even if the legacy
        # manifest's preserved fixed inventories are unavailable to it.
        manifest = {**manifest, "training_rows": [], "examination_rows": []}
        self.assertEqual(manifest["exam_count"], 72)
        self.assertEqual(provenance["teacher_origin_events"], teacher["events"])
        self.assertGreater(teacher["events"], 4000)
        self.assertGreater(len(teacher["strategies"]), 300)
        self.assertEqual(provenance["teacher_origin_step"], 116952)
        copy = deepcopy(teacher)
        import random
        key, policy = engine.pick(copy, "A", random.Random(52))
        self.assertEqual(set(policy), {"old","preview","depth","contrast","lr","distill"})
        engine.observe(copy, "A", key, .125)
        self.assertEqual(copy["events"], teacher["events"]+1)
        self.assertEqual(teacher["events"], provenance["teacher_origin_events"])
        self.assertIn("A", copy["grade_stats"])

    def test_synthetic_micro_transformer_training_step_updates_own_adamw(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        import numpy as np
        mx.set_default_device(mx.cpu)
        rng = np.random.default_rng(18)
        d = 12
        shapes = {
            "embedding.weight": (32,d),
            "position.weight": (8,d),
            "norm.weight": (d,),
            "blocks.0.n1.weight": (d,),
            "blocks.0.n2.weight": (d,),
            "blocks.0.qkv.weight": (3*d,d),
            "blocks.0.proj.weight": (d,d),
            "blocks.0.up.weight": (2*d,d),
            "blocks.0.down.weight": (d,2*d),
        }
        params = {
            name: mx.array(rng.normal(0, .05, size=shape).astype(np.float32)
                           if len(shape) > 1 else np.ones(shape,dtype=np.float32))
            for name, shape in shapes.items()}
        opt = optim.AdamW(learning_rate=.00013, bias_correction=True)
        rows = [
            {"gold":"TRUE","tokens":[1,2,3,6]},
            {"gold":"FALSE","tokens":[4,5,6,7]},
        ]
        before = np.asarray(params["embedding.weight"]).copy()
        loss, norm = _train_step(mx, params, opt, rows,
                                 {"heads":3,"layers":1}, [6,7])
        self.assertTrue(math.isfinite(loss))
        self.assertTrue(math.isfinite(norm))
        self.assertEqual(int(opt.state["step"].item()), 1)
        self.assertFalse(np.array_equal(before,np.asarray(params["embedding.weight"])))
        self.assertEqual(len(opt.state)-2, len(shapes))
        for name in shapes:
            self.assertEqual(set(opt.state[name]), {"m","v"})

    @unittest.skipUnless(SOURCE.is_file(), "Pinned historic source not mounted")
    def test_synthetic_end_to_end_six_visits_generated_grade_exam(self):
        """The real training path executes, but only on freshly invented toy weights."""
        import mlx.core as mx
        import mlx.optimizers as optim
        import numpy as np
        import torch
        mx.set_default_device(mx.cpu)
        manifest, historical_course, engine, sha, teacher, provenance = prepare_source(
            ROOT, SOURCE, MANIFEST)
        course = live_course(historical_course)
        graph = torch.load(SOURCE,map_location="cpu",weights_only=True)["graph"]
        d = 12
        shapes = {
            "embedding.weight": (222,d), "position.weight": (96,d),
            "norm.weight": (d,),
            "blocks.0.n1.weight": (d,), "blocks.0.n2.weight": (d,),
            "blocks.0.qkv.weight": (3*d,d), "blocks.0.proj.weight": (d,d),
            "blocks.0.up.weight": (2*d,d), "blocks.0.down.weight": (d,2*d),
        }
        rng = np.random.default_rng(888)
        params = {
            name: mx.array(rng.normal(0,.015,size=shape).astype(np.float32)
                           if len(shape)>1 else np.ones(shape,dtype=np.float32))
            for name,shape in shapes.items()}
        opt = optim.AdamW(learning_rate=.00013, bias_correction=True)
        opt.update(params, {name: mx.zeros_like(arr) for name,arr in params.items()})
        mx.eval(params,opt.state)
        initial = Checkpoint("f"*64, "fixture-bundle", 1, True)
        school = start_new(course, initial)
        control = {
            "schema": "synthetic-fixture", "run_id": "synthetic-execution",
            "generation": 1, "school": asdict(school),
            "teacher": teacher, "config": {"heads":3,"layers":1},
            "source_manifest_sha256": manifest["manifest_sha256"],
            "answer_ids": [6,7],
            "model_bundle": initial.filename, "last_exam": None,
            "curriculum_mode": LIVE_RELEASE,
            "result": "ACTIVE_GRADE_A",
        }
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
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
            with redirect_stdout(io.StringIO()):
                for i in range(6):
                    control = _take_visit(
                        mx,run_dir,control,manifest,course,engine,
                        params,opt,graph,steps_per_visit=1,batch_size=4,
                        reserve_gib=0.,source_root=ROOT)
                self.assertEqual(control["school"]["stage"], "ASSESS_MAIN")
                self.assertEqual(control["school"]["visits"], 6)
                self.assertEqual(control["teacher"]["events"],teacher["events"]+6)
                self.assertEqual(int(opt.state["step"].item()),7)
                self.assertFalse((run_dir / "bundles").exists(),
                                 "Unscored visits must not create a candidate checkpoint")
                completed = _take_exam(
                    mx,run_dir,control,manifest,course,ROOT,SOURCE,
                    params,opt,graph,reserve_gib=0.)
            self.assertEqual(completed["last_exam"]["exam_rubric_sha256"],
                             program.grades[0].assessment_sha256)
            self.assertEqual(sum(score["total"] for score in
                                 completed["last_exam"]["scores"].values()),72)
            self.assertEqual(completed["school"]["current_student"]["optimizer_step"],7)
            self.assertEqual(json.loads((run_dir/"state.json").read_text()),
                             completed)
            self.assertEqual(len(list((run_dir/"bundles").iterdir())),1)
            self.assertEqual(len(completed["capability_best"]),6)
            saved_cohort = json.loads((run_dir / completed["last_exam"]["cohort_file"]).read_text())
            self.assertEqual(completed["last_exam"]["generator_version"],
                             saved_cohort["generator_version"])
            self.assertEqual(saved_cohort["generator_version"],
                             saved_cohort["source_sha256"])
            self.assertEqual(len(saved_cohort["rows"]), 72)
            self.assertEqual(saved_cohort["cohort_sha256"],
                             completed["last_exam"]["cohort_sha256"])
            events = [json.loads(line) for line in
                      (run_dir / "events.jsonl").read_text().splitlines()]
            visits = [event for event in events if event.get("event") ==
                      "SCHOOL_TEACHER_VISIT_COMMITTED"]
            self.assertEqual(len(visits), 6)
            for event in visits:
                method = event["lesson_methodology"]
                self.assertEqual(method["optimizer_batches_observed"], 1)
                self.assertEqual(method["delivered_examples"], 4)
                self.assertTrue(method["introductory_full_grade_pass"])
                s4, s5 = method["findings"]
                self.assertEqual(s4["status"], DiagnosticStatus.NOT_APPLICABLE)
                self.assertNotEqual(s5["status"], DiagnosticStatus.NOT_MEASURED)
            # A second incomplete recovery group must never create three more
            # intermediate student archives. Old capability winners remain
            # pinned when a new full-student recovery point is committed.
            if completed["school"]["stage"] == "RECOVERY_1":
                with redirect_stdout(io.StringIO()):
                    for i in range(3):
                        completed = _take_visit(
                            mx, run_dir, completed, manifest, course, engine,
                            params, opt, graph, steps_per_visit=1, batch_size=4,
                            reserve_gib=0.,source_root=ROOT)
                    self.assertEqual(len(list((run_dir/"bundles").iterdir())), 1)
                    completed = _take_exam(
                        mx, run_dir, completed, manifest, course, ROOT, SOURCE,
                        params, opt, graph, reserve_gib=0.)
                self.assertNotEqual(completed["last_exam"]["cohort_sha256"],
                                    saved_cohort["cohort_sha256"])
                outcomes = completed["last_exam"]["teacher_outcomes"]
                self.assertEqual(len(outcomes), 3)
                # Three different optimizer-changing visits intervene. One
                # visit per capability is not unique whole-student causality.
                self.assertEqual({outcome["attribution"] for outcome in outcomes},
                                 {"NOT_MEASURED_CHANGED_EXAM"})
                self.assertTrue(all(len(outcome["decision_ids"]) == 1
                                    for outcome in outcomes))
                self.assertEqual(len(completed["last_exam"]["incumbent_comparisons"]), 1)
                self.assertEqual(completed["last_exam"]["incumbent_comparisons"][0]["cohort_sha256"],
                                 completed["last_exam"]["candidate_cohort_sha256"])
                self.assertNotEqual(completed["last_exam"]["cohort_sha256"],
                                    completed["last_exam"]["candidate_cohort_sha256"])
                retained = {x["checkpoint"]["filename"]
                            for x in completed["capability_best"].values()}
                retained.add(completed["model_bundle"])
                self.assertEqual(len(list((run_dir/"bundles").iterdir())),
                                 len(retained))

    @unittest.skipUnless(SOURCE.is_file(), "Pinned original student unavailable")
    def test_historical_v1_resume_preserves_full_optimizer_teacher_and_replays_old_best(self):
        """Copy, never optimize, original weights; migrate a disposable v1 run."""
        import mlx.core as mx
        mx.set_default_device(mx.cpu)
        manifest, old_course, engine, sha, teacher, provenance = prepare_source(
            ROOT, SOURCE, MANIFEST)
        course = live_course(old_course)
        parameters, optimizer, config, graph, answer_ids = _initial_model(SOURCE)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            with redirect_stdout(io.StringIO()):
                base = _bundle_pointer(run_dir, "old-v1-student", parameters,
                                       optimizer, graph, reserve_gib=0.)
            old_school = start_new(old_course, base)
            for cap in [c.id for c in old_course.grades[0].capabilities]:
                old_school = visit(old_course, old_school, cap, base)
            scores = {c.id: {"correct": 5, "total": 12}
                      for c in old_course.grades[0].capabilities}
            frontier = promote({}, scores, manifest["exam_rubric_sha256"],
                               asdict(base), "historic-evaluation",
                               tuple(sorted(scores)))
            historical = _historical_v1_receipt(
                manifest=manifest, school=old_school, base=base,
                frontier=frontier, teacher=teacher, teacher_sha=sha,
                provenance=provenance, config=config, parameters=parameters,
                graph=graph, answer_ids=answer_ids)
            trainer._record(run_dir, {
                "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                "generation": 1,
                "grade": "A",
                "optimizer_step": base.optimizer_step,
                "retained_optimizer_updates": 1,
                "recovered_at_student_sha256": base.sha256,
                "checkpoint_status": "RECORDED_AT_BOUNDARY",
            })
            _persist(run_dir, historical)
            with redirect_stdout(io.StringIO()):
                loaded, own_adamw, loaded_graph, resumed = _resume(
                    run_dir, manifest, course, sha,
                    grade_a_course=course, source_root=ROOT)
            self.assertEqual(resumed["curriculum_mode"], LIVE_RELEASE)
            self.assertEqual(resumed["school"]["current_student"], asdict(base))
            self.assertEqual(int(own_adamw.state["step"].item()), base.optimizer_step)
            self.assertEqual(resumed["teacher"], teacher)
            self.assertEqual(resumed["historical_capability_best"], frontier)
            self.assertTrue(resumed["legacy_frontier_pending_replay"])
            self.assertEqual(resumed["championship_checkpoint_origins"],
                             {base.sha256: "A"})
            admitted_release = trainer._read_executable_factory_release_artifact(
                run_dir, resumed)
            self.assertEqual(
                resumed["school"]["course_digest"],
                trainer.schedule_program_from_executable_release(
                    admitted_release).digest())
            self.assertEqual(json.loads((run_dir/"states/0000001.json").read_text()),
                             json.loads(json.dumps(historical)))
            self.assertIn("factory_admission_v2", resumed)
            self.assertEqual(resumed["factory_release_schema"],
                             "bilqis.mlx.factory-release/v2")
            self.assertEqual(resumed["factory_release_sha256"],
                             resumed["factory_admission_v2"]["factory_release_sha256"])
            # Fault injection: the live-course migration plus factory-admission
            # generations exist, but the mutable latest pointer is rewound to
            # the historical generation 1 receipt.
            # latest pointer still says generation 1 after interruption.
            _durable_json(run_dir / "state.json",
                          json.loads(json.dumps(historical)), replace_existing=True)
            with redirect_stdout(io.StringIO()):
                restored_weights, restored_adamw, restored_graph, repaired = _resume(
                    run_dir, manifest, course, sha,
                    grade_a_course=course, source_root=ROOT)
            self.assertEqual(repaired, resumed)
            self.assertEqual(repaired["generation"], 4)
            self.assertEqual(int(restored_adamw.state["step"].item()),
                             base.optimizer_step)
            with redirect_stdout(io.StringIO()):
                after = _take_exam(mx, run_dir, resumed, manifest, course,
                                   ROOT, SOURCE, loaded, own_adamw, loaded_graph,
                                   reserve_gib=0.)
            self.assertFalse(after["legacy_frontier_pending_replay"])
            self.assertEqual(len(after["last_exam"]["incumbent_comparisons"]), 1)
            self.assertEqual(after["last_exam"]["incumbent_comparisons"][0]
                             ["checkpoint"]["sha256"], base.sha256)
            self.assertEqual(after["last_exam"]["incumbent_comparisons"][0]
                             ["cohort_sha256"], after["last_exam"]["candidate_cohort_sha256"])


if __name__ == "__main__":
    unittest.main()
