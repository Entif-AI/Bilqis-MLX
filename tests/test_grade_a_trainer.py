"""Trainer contract tests: disposable toy optimization, never real student steps."""
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.grade_a_release import accepted_grade_a, RELEASE
from bilqis_mlx.grade_a_trainer import (
    _make_batch, _persist, _seed, _state_from_json, _train_step,
    _take_visit, _take_exam,
    choose_lesson_batch, operator_lock, prepare_source,
)
from bilqis_mlx.champions import Checkpoint
from bilqis_mlx.school import start_new

ROOT = Path(__file__).resolve().parents[2] / "bilqis-triplets-v16"
SOURCE = ROOT / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"
MANIFEST = Path(__file__).resolve().parents[1] / "docs/GRADE_A_CANDIDATE_MANIFEST_V2.json"


class GradeATrainerContractTests(unittest.TestCase):
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

    def test_teacher_batches_stay_inside_sealed_training_partition(self):
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
            with self.assertRaises(FileExistsError):
                _persist(root, second)
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
        manifest, course, engine, sha, teacher, provenance = prepare_source(
            ROOT, SOURCE, MANIFEST)
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
    def test_synthetic_end_to_end_six_visits_checkpoint_and_sealed_grade_exam(self):
        """The real training path executes, but only on freshly invented toy weights."""
        import mlx.core as mx
        import mlx.optimizers as optim
        import numpy as np
        import torch
        mx.set_default_device(mx.cpu)
        manifest, course, engine, sha, teacher, provenance = prepare_source(
            ROOT, SOURCE, MANIFEST)
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
            "answer_ids": [6,7],
            "model_bundle": initial.filename, "last_exam": None,
            "result": "ACTIVE_GRADE_A",
        }
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            with redirect_stdout(io.StringIO()):
                for i in range(6):
                    control = _take_visit(
                        mx,run_dir,control,manifest,course,engine,
                        params,opt,graph,steps_per_visit=1,batch_size=4,
                        reserve_gib=0.)
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
                             manifest["exam_rubric_sha256"])
            self.assertEqual(sum(score["total"] for score in
                                 completed["last_exam"]["scores"].values()),72)
            self.assertEqual(completed["school"]["current_student"]["optimizer_step"],7)
            self.assertEqual(json.loads((run_dir/"state.json").read_text()),
                             completed)
            self.assertEqual(len(list((run_dir/"bundles").iterdir())),1)
            self.assertEqual(len(completed["capability_best"]),6)
            # A second incomplete recovery group must never create three more
            # intermediate student archives. Old capability winners remain
            # pinned when a new full-student recovery point is committed.
            if completed["school"]["stage"] == "RECOVERY_1":
                with redirect_stdout(io.StringIO()):
                    for i in range(3):
                        completed = _take_visit(
                            mx, run_dir, completed, manifest, course, engine,
                            params, opt, graph, steps_per_visit=1, batch_size=4,
                            reserve_gib=0.)
                    self.assertEqual(len(list((run_dir/"bundles").iterdir())), 1)
                    completed = _take_exam(
                        mx, run_dir, completed, manifest, course, ROOT, SOURCE,
                        params, opt, graph, reserve_gib=0.)
                retained = {x["checkpoint"]["filename"]
                            for x in completed["capability_best"].values()}
                retained.add(completed["model_bundle"])
                self.assertEqual(len(list((run_dir/"bundles").iterdir())),
                                 len(retained))


if __name__ == "__main__":
    unittest.main()
