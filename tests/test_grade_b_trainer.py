"""Disposable multi-grade trainer, model custody, and source-cohort checks."""
from dataclasses import asdict, replace
import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.grade_a_release import accepted_grade_a, AUTHORITY
from bilqis_mlx.grade_a_trainer import (
    VERSION, _activate_next_admitted_grade, _bundle_pointer,
    _champion_teacher_votes, _draw_live_rows, _fingerprint, _persist,
    _persist_live_cohort, _recover_orphaned_commit, _seed, _state_from_json,
    _publish_boundary, _reconcile_delivery_outbox, _resume, _take_exam,
    _take_visit, _verify_saved_cohort, _with_delivery_outbox,
    champion_directed_lessons, prepare_source,
)
from bilqis_mlx.generated_assessment import make_cohort
from bilqis_mlx.live_grade_a import live_course as a_live_course
from bilqis_mlx.live_grade_b import (GENERATOR as B_GENERATOR, RELEASE as B_RELEASE,
                                    live_course as b_live_course)
from bilqis_mlx.school import (Assessment, Score, assess, start_new, visit)
from bilqis_mlx.champions import Checkpoint

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT.parent / "bilqis-triplets-v16"
CHECKPOINT = (SOURCE_ROOT / "runs/primitive-consolidation-v16-triplets/"
              "student-116760-7e9af4651f28.pt")
MANIFEST = ROOT / "docs/GRADE_A_CANDIDATE_MANIFEST_V2.json"


@unittest.skipUnless(CHECKPOINT.is_file(), "Original source not mounted")
class GradeBTrainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, historical, cls.engine, cls.teacher_sha, cls.teacher, _ = (
            prepare_source(SOURCE_ROOT, CHECKPOINT, MANIFEST))
        cls.a_course = a_live_course(historical)
        cls.b_course = b_live_course(cls.a_course, SOURCE_ROOT)

    def _graduated_a(self, pointer):
        school = start_new(self.a_course, pointer)
        for c in self.a_course.grades[0].capabilities:
            school = visit(self.a_course, school, c.id, pointer)
        scores = {c.id: Score(12, 12) for c in self.a_course.grades[0].capabilities}
        school = assess(self.a_course, school, Assessment(
            pointer.sha256, pointer.optimizer_step, self.a_course.digest(),
            self.a_course.grades[0].assessment_sha256, scores,
            "fixture-intact-grade-a"))
        self.assertEqual(school.stage, "AWAITING_NEXT_GRADE")
        return school

    def _receipt(self, school, pointer, **extra):
        return {"schema": VERSION, "generation": 1, "run_id": "disposable-fixture",
                "accepted_authority": AUTHORITY,
                "source_manifest_sha256": self.manifest["manifest_sha256"],
                "teacher_source_sha256": self.teacher_sha,
                "school": asdict(school), "model_bundle": pointer.filename,
                "curriculum_mode": self.a_course.version,
                "live_rubric_sha256": self.a_course.grades[0].assessment_sha256,
                "teacher": json.loads(json.dumps(self.teacher)),
                "capability_best": {}, "last_exam": None,
                "result": "GRADE_A_MASTERED_AWAITING_GRADE_B", **extra}

    def test_grade_b_transition_preserves_student_optimizer_teacher_and_generations(self):
        weights = b"synthetic-disposable-model-bytes"
        sha = hashlib.sha256(weights).hexdigest()
        pointer = Checkpoint(sha, "bundles/student-test", 153144, True)
        school = self._graduated_a(pointer)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / pointer.filename
            bundle.mkdir(parents=True)
            (bundle / "model-and-own-adamw.safetensors").write_bytes(weights)
            (bundle / "manifest.json").write_text(json.dumps({
                "safetensors_sha256": sha, "optimizer_step": 153144}))
            receipt = _persist(root, self._receipt(school, pointer))
            with redirect_stdout(io.StringIO()):
                updated = _activate_next_admitted_grade(
                    root, receipt, self.a_course, self.b_course)
            self.assertEqual(updated["generation"], 2)
            self.assertEqual(updated["curriculum_mode"], B_RELEASE)
            self.assertEqual(updated["model_bundle"], receipt["model_bundle"])
            self.assertEqual(updated["teacher"], receipt["teacher"])
            self.assertEqual(updated["school"]["current_student"],
                             receipt["school"]["current_student"])
            self.assertEqual(updated["school"]["champions"],
                             receipt["school"]["champions"])
            self.assertEqual((updated["school"]["grade_index"],
                              updated["school"]["active_grades"]), (1,["A","B"]))
            self.assertEqual(_state_from_json(updated["school"],self.b_course).grade,"B")
            self.assertEqual(json.loads((root/"states/0000001.json").read_text()),receipt)
            self.assertEqual(json.loads((root/"state.json").read_text()),updated)
            # Interrupt after immutable second generation, before current pointer.
            from bilqis_mlx.grade_a_trainer import _durable_json
            _durable_json(root/"state.json",receipt,replace_existing=True)
            with redirect_stdout(io.StringIO()):
                recovered = _recover_orphaned_commit(root,receipt)
            self.assertEqual(recovered,updated)
            self.assertEqual(json.loads((root/"state.json").read_text()),updated)

    def test_admission_interrupt_after_immutable_state_replays_once_not_student(self):
        """A lost publication acknowledgment never repeats A->B mutation."""
        pointer = Checkpoint("a"*64,"bundles/inert",153144,True)
        school = self._graduated_a(pointer)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = _persist(root,self._receipt(school,pointer))
            with patch("bilqis_mlx.grade_a_trainer._record",
                       side_effect=RuntimeError("crash-after-state-commit")):
                with self.assertRaisesRegex(RuntimeError,"crash-after-state-commit"):
                    _activate_next_admitted_grade(root,old,self.a_course,self.b_course)
            saved = json.loads((root/"state.json").read_text())
            self.assertEqual(saved["curriculum_mode"],B_RELEASE)
            self.assertEqual(saved["school"]["grade_index"],1)
            self.assertEqual(saved["school"]["current_student"],
                             old["school"]["current_student"])
            self.assertEqual(len(saved["delivery_outbox"]),1)
            with redirect_stdout(io.StringIO()):
                _reconcile_delivery_outbox(root,saved)
                _reconcile_delivery_outbox(root,saved)
            events = [json.loads(line) for line in
                      (root/"events.jsonl").read_text().splitlines()]
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]["event"],"SCHOOL_GRADE_B_COURSE_ADMITTED")
            self.assertEqual(events[0]["event_id"],saved["delivery_outbox"][0]["event_id"])

    def test_partial_event_write_recovery_exactly_once_and_detects_tampering(self):
        record = {"run_id":"test-event-journal", "generation":7}
        events = ({"event":"GRADE_A_TEACHER_VISIT_COMMITTED","grade":"A"},
                  {"event":"SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED","grade":"B"})
        record = _with_delivery_outbox(record,events)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            from bilqis_mlx.grade_a_trainer import _record
            journal = root/"events.jsonl"
            old_record = _record
            delivered = []
            def fail_on_second(path,event):
                if delivered:
                    raise OSError("disk-interrupted-event-publication")
                delivered.append(event["event_id"])
                return old_record(path,event)
            with patch("bilqis_mlx.grade_a_trainer._record",side_effect=fail_on_second):
                with self.assertRaisesRegex(OSError,"disk-interrupted"):
                    _reconcile_delivery_outbox(root,record)
            with redirect_stdout(io.StringIO()):
                _reconcile_delivery_outbox(root,record)
                _reconcile_delivery_outbox(root,record)
            observed = [json.loads(line) for line in journal.read_text().splitlines()]
            self.assertEqual(observed,record["delivery_outbox"])
            tampered = json.loads(json.dumps(record))
            tampered["delivery_outbox"][0]["grade"] = "B"
            with self.assertRaisesRegex(ValueError,"OUTBOX_LINEAGE_DRIFT"):
                _reconcile_delivery_outbox(root,tampered)

    def test_resume_recovers_orphaned_b_admission_when_latest_pointer_is_a(self):
        """Synthetic complete-state readback, no actual student optimizer steps."""
        import mlx.core as mx
        import torch
        graph = torch.load(CHECKPOINT,map_location="cpu",weights_only=True)["graph"]
        params = {f"synthetic-weight-{n}":mx.array([float(n)]) for n in range(39)}
        class FakeOptimizer:
            state = {"step":mx.array(153144)}
        optimizer = FakeOptimizer()
        contents = b"safe-disposable-model"
        sha = hashlib.sha256(contents).hexdigest()
        pointer = Checkpoint(sha,"bundles/complete-toy",153144,True)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root/pointer.filename
            bundle.mkdir(parents=True)
            (bundle/"model-and-own-adamw.safetensors").write_bytes(contents)
            (bundle/"manifest.json").write_text(json.dumps({
                "safetensors_sha256":sha,"optimizer_step":153144}))
            old = _persist(root,self._receipt(
                self._graduated_a(pointer),pointer,
                semantic_graph_sha256=_fingerprint(graph),
                parameter_shapes={name:list(value.shape) for name,value in params.items()}))
            with redirect_stdout(io.StringIO()):
                successor = _activate_next_admitted_grade(
                    root,old,self.a_course,self.b_course)
            from bilqis_mlx.grade_a_trainer import _durable_json
            _durable_json(root/"state.json",old,replace_existing=True)
            from bilqis_mlx.source import AUDITED_PARENT
            fake_meta = {"source_digest":AUDITED_PARENT.sha256,
                         "safetensors_sha256":sha,"optimizer_step":153144}
            with (patch("bilqis_mlx.grade_a_trainer.load_semantically_bound_bundle",
                        return_value=(params,optimizer,fake_meta,graph)),
                  patch("bilqis_mlx.grade_a_trainer._verify_best_custody"),
                  patch("bilqis_mlx.grade_a_trainer._publish_boundary"),
                  redirect_stdout(io.StringIO())):
                saved_params, saved_optimizer, saved_graph, recovered = _resume(
                    root,self.manifest,self.a_course,self.teacher_sha,
                    successor_course=self.b_course)
            self.assertEqual(recovered,successor)
            self.assertEqual(recovered["curriculum_mode"],B_RELEASE)
            self.assertEqual(recovered["school"]["grade_index"],1)
            self.assertEqual(saved_graph,graph)
            self.assertEqual(list(saved_params),list(params))
            self.assertIs(saved_optimizer,optimizer)

    def test_refuse_any_nonmastered_or_unexecutable_grade_transition(self):
        pointer = Checkpoint("a"*64, "bundles/disposable", 100, True)
        school = start_new(self.a_course, pointer)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt = self._receipt(school, pointer)
            with self.assertRaisesRegex(ValueError,"GRADE_B_ADMISSION_BOUNDARY"):
                _activate_next_admitted_grade(root,receipt,self.a_course,self.b_course)
            draft = replace(self.b_course, grades=(self.b_course.grades[0],
                replace(self.b_course.grades[1],assessment_sha256=None)))
            with self.assertRaisesRegex(ValueError,"GRADE_B_ADMISSION_BOUNDARY"):
                _activate_next_admitted_grade(root,
                    self._receipt(self._graduated_a(pointer),pointer),
                    self.a_course,draft)

    def test_cumulative_cohort_and_old_grade_a_cohort_remain_immutable(self):
        import torch
        graph = torch.load(CHECKPOINT,map_location="cpu",weights_only=True)["graph"]
        b_rows = _draw_live_rows(SOURCE_ROOT,graph,seed=222,course=self.b_course)
        self.assertEqual(len(b_rows),144)
        self.assertEqual({r["capability"].split(".")[0] for r in b_rows},{"A","B"})
        b_cohort = make_cohort(b_rows,generator_version=B_GENERATOR,
                               seed=222,rubric_version=B_RELEASE)
        a_rows = _draw_live_rows(SOURCE_ROOT,graph,seed=111,course=self.a_course)
        a_cohort = make_cohort(a_rows,
            generator_version="bilqis.mlx.grade-a-live-constructor/v1",seed=111,
            rubric_version=self.a_course.version)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a_file = _persist_live_cohort(root,self.manifest,self.a_course,a_cohort)
            b_file = _persist_live_cohort(root,self.manifest,self.b_course,b_cohort)
            self.assertNotEqual(a_file,b_file)
            for selected,cohort,course in ((a_file,a_cohort,self.a_course),
                                            (b_file,b_cohort,self.b_course),
                                            (a_file,a_cohort,self.b_course)):
                receipt = {"source_manifest_sha256":self.manifest["manifest_sha256"],
                           "last_exam":{"cohort_sha256":cohort.digest,
                                        "cohort_seed":cohort.seed,"cohort_file":selected}}
                _verify_saved_cohort(root,receipt,course)
            document = json.loads((root/b_file).read_text())
            document["rows"][0]["gold"] = "CHEATED"
            (root/b_file).write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError,"CONTENT_DRIFT"):
                _verify_saved_cohort(root,{"source_manifest_sha256":self.manifest["manifest_sha256"],
                    "last_exam":{"cohort_sha256":b_cohort.digest,
                                 "cohort_seed":b_cohort.seed,"cohort_file":b_file}},self.b_course)

    def test_champion_votes_only_shift_source_approved_teaching_examples(self):
        chosen = ([{"id":f"t{i}","gold":"TRUE"} for i in range(4)] +
                  [{"id":f"f{i}","gold":"FALSE"} for i in range(4)])
        candidates = [
            {"id":"new-true","gold":"TRUE"},
            {"id":"new-false","gold":"FALSE"},
        ]
        result = champion_directed_lessons(chosen,candidates,
                                         {"new-true":3,"new-false":1},capacity=2)
        self.assertEqual({r["id"] for r in result}&{"new-true","new-false"},
                         {"new-true","new-false"})
        self.assertEqual(sum(r["gold"] == "TRUE" for r in result),4)
        self.assertEqual(sum(r["gold"] == "FALSE" for r in result),4)
        self.assertEqual(chosen[0]["id"],"t0")
        with self.assertRaisesRegex(ValueError,"COUNT_INVALID"):
            champion_directed_lessons(chosen,candidates,{"new-false":-1},capacity=1)

    def test_b_weakest_three_rehearsal_credits_actual_a_lesson_not_b(self):
        """An A predicate taught during B recovery must train A's policy stats."""
        from types import SimpleNamespace
        from bilqis_mlx.school import append_next_grade
        pointer = Checkpoint("a"*64,"bundles/toy-only",300,True)
        school = append_next_grade(self.a_course,self.b_course,self._graduated_a(pointer))
        school = replace(school, stage="RECOVERY_1",queue=("A.IDENTITY",),
                         first_recovery=("A.IDENTITY",))
        receipt = self._receipt(school,pointer,config={"heads":3,"layers":1},
                                answer_ids=[6,7],curriculum_mode=B_RELEASE)
        observed = []

        class Teacher:
            def pick(self,state,grade,rng):
                observed.append(("pick",grade))
                return "source-policy",{"lr":.00013,"depth":1,"contrast":1.}
            def observe(self,state,grade,key,reward):
                observed.append(("observe",grade))

        class Step:
            def __init__(self):self.count = 300
            def item(self):return self.count

        optimizer = SimpleNamespace(state={"step":Step()},learning_rate=.00013)
        examples = [{"id":str(i),"capability":"A.IDENTITY",
                     "tokens":[4,6],"gold":"TRUE" if i%2 else "FALSE"}
                    for i in range(4)]
        def toy_step(*args,**kwargs):
            optimizer.state["step"].count += 1
            return .25,.2

        with (patch("bilqis_mlx.grade_a_trainer._draw_live_rows",
                    return_value=examples),
              patch("bilqis_mlx.grade_a_trainer._champion_teacher_votes",
                    return_value={}),
              patch("bilqis_mlx.grade_a_trainer._train_score",return_value=.5),
              patch("bilqis_mlx.grade_a_trainer._train_step",side_effect=toy_step)):
            updated = _take_visit(
                None,Path("/unused-during-disposable-test"),receipt,self.manifest,
                self.b_course,Teacher(),{},optimizer,{},steps_per_visit=1,
                batch_size=4,reserve_gib=0.,source_root=SOURCE_ROOT)
        self.assertEqual(observed,[("pick","A"),("observe","A")])
        event = updated["_pending_visit_events"][0]
        self.assertEqual(event["capability"],"A.IDENTITY")
        self.assertEqual(event["grade"],"A")
        self.assertEqual(event["active_grade"],"B")
        self.assertEqual(event["event"],"GRADE_A_TEACHER_VISIT_COMMITTED")

    def test_b_exam_best_receipt_keeps_completed_grade_after_b_to_a_transition(self):
        pointer = {"sha256":"b"*64,"filename":"bundles/fixture",
                   "optimizer_step":400,"model_and_native_adamw":True}
        rubric = "c"*64
        grade_b_role = "B.NOT"
        record = {"generation":3,
                  "school":{"active_grades":["A","B"],"grade_index":0,
                            "current_student":pointer,"champions":{"A":pointer,"B":pointer}},
                  "capability_best":{rubric+":"+grade_b_role:{
                      "capability":grade_b_role,"rubric":rubric,"checkpoint":pointer,
                      "correct":12,"total":12,"evaluation_id":"source-verified-test"}}}
        observed = []
        with (patch("bilqis_mlx.grade_a_trainer._record",
                    side_effect=lambda _,event:observed.append(event)),
              patch("bilqis_mlx.grade_a_trainer._quarantine_newer_uncommitted_bundles"),
              patch("bilqis_mlx.grade_a_trainer.retire_bundles",return_value=())):
            _publish_boundary(Path("/dummy"), record, (), (grade_b_role,),
                              exam_event={"event":"SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                                          "grade":"B"})
        best = next(event for event in observed if event["event"] ==
                    "SCHOOL_CAPABILITY_BEST_COMMITTED")
        self.assertEqual(best["grade"],"B")
        self.assertEqual(best["capabilities"],[grade_b_role])

    def test_disposable_full_billy_madison_human_trainer_functions(self):
        """Toy optimizer only: B graduation -> A replay -> B replay -> wait C."""
        import mlx.core as mx
        import mlx.optimizers as optim
        import numpy as np
        import torch

        mx.set_default_device(mx.cpu)
        graph = torch.load(CHECKPOINT,map_location="cpu",weights_only=True)["graph"]
        width = 12
        shapes = {
            "embedding.weight": (222,width), "position.weight": (96,width),
            "norm.weight": (width,), "blocks.0.n1.weight": (width,),
            "blocks.0.n2.weight": (width,),
            "blocks.0.qkv.weight": (3*width,width),
            "blocks.0.proj.weight": (width,width),
            "blocks.0.up.weight": (2*width,width),
            "blocks.0.down.weight": (width,2*width),
        }
        rng = np.random.default_rng(37)
        params = {name: mx.array(rng.normal(0,.01,size=shape).astype(np.float32)
                           if len(shape)>1 else np.ones(shape,dtype=np.float32))
                  for name,shape in shapes.items()}
        opt = optim.AdamW(learning_rate=.00013,bias_correction=True)
        opt.update(params,{name: mx.zeros_like(value) for name,value in params.items()})
        mx.eval(params,opt.state)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            initial = _bundle_pointer(root,"fixture-start",params,opt,graph,reserve_gib=0.)
            school = self._graduated_a(initial)
            receipt = self._receipt(school,initial,
                config={"heads":3,"layers":1}, answer_ids=[6,7],
                semantic_graph_sha256=_fingerprint(graph),
                parameter_shapes={name:list(value.shape) for name,value in params.items()})
            receipt = _persist(root,receipt)
            with redirect_stdout(io.StringIO()):
                receipt = _activate_next_admitted_grade(
                    root,receipt,self.a_course,self.b_course)

            def perfect_oracle_predictions(mx,parameters,rows,config,answer_ids):
                return {r["id"]:r["gold"] for r in rows}

            qualification_cohorts = []
            for expected_grade in ("B","A","B"):
                self.assertEqual(_state_from_json(receipt["school"],self.b_course).grade,
                                 expected_grade)
                with redirect_stdout(io.StringIO()):
                    for _ in range(6):
                        receipt = _take_visit(
                            mx,root,receipt,self.manifest,self.b_course,self.engine,
                            params,opt,graph,steps_per_visit=1,batch_size=4,
                            reserve_gib=0.,source_root=SOURCE_ROOT)
                self.assertEqual(receipt["school"]["stage"],"ASSESS_MAIN")
                with (patch("bilqis_mlx.grade_a_trainer._predictions",
                            side_effect=perfect_oracle_predictions),
                      redirect_stdout(io.StringIO())):
                    receipt = _take_exam(
                        mx,root,receipt,self.manifest,self.b_course,
                        SOURCE_ROOT,CHECKPOINT,params,opt,graph,reserve_gib=0.)
                exam = receipt["last_exam"]
                qualification_cohorts.append(exam["cohort_sha256"])
                self.assertEqual(len(exam["scores"]),12)
                self.assertEqual(sum(s["total"] for s in exam["scores"].values()),144)
                self.assertTrue(all(s["correct"] == s["total"] for s in exam["scores"].values()))
                self.assertEqual(len(exam["cohort_sha256"]),64)
            self.assertEqual(len(set(qualification_cohorts)), 3,
                             "Every grade enrollment, including a revisit, gets a new test")
            final = _state_from_json(receipt["school"],self.b_course)
            self.assertEqual(final.stage,"AWAITING_NEXT_GRADE")
            self.assertEqual(final.active_grades,("A","B"))
            self.assertEqual(final.revalidation_target_grade,None)
            self.assertEqual(set(final.champions),{"A","B"})
            self.assertEqual(opt.state["step"].item(),19)
            self.assertEqual(receipt["teacher"]["events"],self.teacher["events"]+18)
            self.assertEqual(json.loads((root/"state.json").read_text()),receipt)
            events = [json.loads(line) for line in
                      (root/"events.jsonl").read_text().splitlines()]
            self.assertTrue(any(event.get("grade") == "B" and
                list(event.get("prior_grade_champion_votes",{}).values()) == [1]
                for event in events if event.get("event") ==
                                   "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED"))
            self.assertTrue(any(event.get("grade") == "A" and
                list(event.get("prior_grade_champion_votes",{}).values()) == [2]
                for event in events if event.get("event") ==
                                   "GRADE_A_TEACHER_VISIT_COMMITTED"))


if __name__ == "__main__":
    unittest.main()
