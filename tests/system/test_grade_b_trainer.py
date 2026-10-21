"""Disposable multi-grade trainer, model custody, and source-cohort checks."""
from dataclasses import asdict, replace
import hashlib
import io
import json
import os
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.support.executable_school import admit_executable_school

from bilqis_mlx.grade_a_release import accepted_grade_a, AUTHORITY
from bilqis_mlx.trainer import (
    VERSION, _activate_next_admitted_grade, _activate_revised_admitted_grade, _bundle_pointer,
    _draw_live_rows, _fingerprint, _persist,
    _fixed_same_grade_rows, _learning_probe_rows,
    _persist_live_cohort, _recover_orphaned_commit, _seed, _state_from_json,
    _publish_boundary, _reconcile_delivery_outbox, _resume, _take_exam,
    _take_visit, _verify_saved_cohort, _with_delivery_outbox,
    prepare_source,
)
from bilqis_mlx.generated_assessment import make_cohort
from bilqis_mlx.live_grade_a import live_course as a_live_course
from bilqis_mlx.live_grade_b import (GENERATOR as B_GENERATOR, RELEASE as B_RELEASE,
                                    live_course as b_live_course)
from bilqis_mlx.boolean_composite import (
    CAPABILITY as B_COMPOSITE, RELEASE as B_COMPOSITE_RELEASE,
    build_course as composite_b_course,
)
from bilqis_mlx.curriculum.scheduler import (Assessment, Score, assess, start_new, visit)
from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.diagnostics import DiagnosticStatus, LearningSignal
from bilqis_mlx.learning.teacher_feedback import OutcomeAttribution, TeachingOpportunity

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "vendor" / "legacy-v16"
CHECKPOINT = (SOURCE_ROOT / "runs/primitive-consolidation-v16-triplets/"
              "student-116760-7e9af4651f28.pt")
MANIFEST = ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


@unittest.skipUnless(CHECKPOINT.is_file(), "Original source not mounted")
@unittest.skipUnless(os.environ.get("BILQIS_FULL_GRADE_B_TESTS") == "1",
                     "legacy/full Grade B trainer tests are opt-in")
class GradeBTrainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, historical, cls.engine, cls.teacher_sha, cls.teacher, _ = (
            prepare_source(SOURCE_ROOT, CHECKPOINT, MANIFEST))
        cls.a_course = a_live_course(historical)
        cls.b_course = b_live_course(cls.a_course, SOURCE_ROOT)

    def test_pre_abi_refactor_human_release_retains_exact_seals(self):
        """A source-neutral ABI import must not strand sealed training states."""
        from bilqis_mlx.compatibility.historical_live_release import (
            HISTORICAL_A_RUBRIC_SHA256, HISTORICAL_B_COURSE_SHA256,
            HISTORICAL_B_RUBRIC_SHA256, historical_grade_b_course,
        )
        historical_a, historical_b = historical_grade_b_course(
            accepted_grade_a(self.manifest), SOURCE_ROOT)
        self.assertEqual(historical_a.grades[0].assessment_sha256,
                         HISTORICAL_A_RUBRIC_SHA256)
        self.assertEqual(historical_b.grades[-1].assessment_sha256,
                         HISTORICAL_B_RUBRIC_SHA256)
        self.assertEqual(historical_b.digest(), HISTORICAL_B_COURSE_SHA256)
        self.assertNotEqual(historical_b.digest(), self.b_course.digest())
        school = start_new(historical_b, Checkpoint("a"*64,"bundles/test",0,True))
        self.assertEqual(_state_from_json(asdict(school),historical_b), school)
        with self.assertRaises(BilqisError) as caught:
            _state_from_json(asdict(school),self.b_course)
        self.assertIs(
            caught.exception.spec, SCHOOL.STATE.COURSE_DIGEST_MISMATCH)

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
        graduate_exam = ({
            "student_sha256": pointer.sha256,
            "optimizer_step": pointer.optimizer_step,
            "cohort_sha256": "c" * 64,
            "exam_rubric_sha256": self.a_course.grades[0].assessment_sha256,
            "scores": {cap.id: {"correct": 12, "total": 12}
                       for cap in self.a_course.grades[0].capabilities},
        } if school.stage == "AWAITING_NEXT_GRADE" else None)
        return {"schema": VERSION, "generation": 1, "run_id": "disposable-fixture",
                "accepted_authority": AUTHORITY,
                "source_manifest_sha256": self.manifest["manifest_sha256"],
                "teacher_source_sha256": self.teacher_sha,
                "school": asdict(school), "model_bundle": pointer.filename,
                "curriculum_mode": self.a_course.version,
                "live_rubric_sha256": self.a_course.grades[0].assessment_sha256,
                "semantic_graph_sha256":
                    self.manifest["parent_student"]["full_student_graph_sha256"],
                "parameter_shapes": {"fixture.weight": [1]},
                "factory_release_sha256": "f" * 64,
                "championship_checkpoint_origins": {},
                "teacher": json.loads(json.dumps(self.teacher)),
                "capability_best": {}, "last_exam": graduate_exam,
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
            self.assertEqual(updated["mentor_epoch"]["active_roles"], {})
            self.assertEqual(updated["mentor_epoch"]["active_grade_soups"], {})
            self.assertEqual(updated["mentor_epoch"]["championship_school_identity"],
                             updated["championship_school_identity"])
            self.assertEqual((updated["school"]["grade_index"],
                              updated["school"]["active_grades"]), (1,["A","B"]))
            self.assertEqual(_state_from_json(updated["school"],self.b_course).grade,"B")
            self.assertEqual(json.loads((root/"states/0000001.json").read_text()),receipt)
            self.assertEqual(json.loads((root/"state.json").read_text()),updated)
            # Interrupt after immutable second generation, before current pointer.
            from bilqis_mlx.trainer import _durable_json
            _durable_json(root/"state.json",receipt,replace_existing=True)
            with redirect_stdout(io.StringIO()):
                recovered = _recover_orphaned_commit(root,receipt)
            self.assertEqual(recovered,updated)
            self.assertEqual(json.loads((root/"state.json").read_text()),updated)

    def test_boolean_composite_revision_preserves_student_and_reopens_b_mastery(self):
        weights = b"synthetic-composite-migration-model"
        sha = hashlib.sha256(weights).hexdigest()
        pointer = Checkpoint(sha, "bundles/student-composite", 153144, True)
        school = self._graduated_a(pointer)
        composite = composite_b_course(self.b_course, SOURCE_ROOT)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / pointer.filename
            bundle.mkdir(parents=True)
            (bundle / "model-and-own-adamw.safetensors").write_bytes(weights)
            (bundle / "manifest.json").write_text(json.dumps({
                "safetensors_sha256": sha, "optimizer_step": pointer.optimizer_step}))
            receipt = _persist(root, self._receipt(school, pointer))
            with redirect_stdout(io.StringIO()):
                admitted = _activate_next_admitted_grade(
                    root, receipt, self.a_course, self.b_course)
            old_school = dict(admitted["school"])
            old_school["champions"] = {
                **old_school["champions"], "B": asdict(pointer)}
            old_school["queue"] = [cap.id for cap in self.b_course.grades[-1].capabilities]
            admitted = {**admitted, "school": old_school,
                        "last_exam": {"cohort_sha256": "d" * 64},
                        "qualification_cohort": {"cohort_sha256": "e" * 64}}
            teacher = json.loads(json.dumps(admitted["teacher"]))
            with redirect_stdout(io.StringIO()):
                revised = _activate_revised_admitted_grade(
                    root, admitted, self.b_course, composite)
        self.assertEqual(revised["curriculum_mode"], B_COMPOSITE_RELEASE)
        self.assertEqual(revised["model_bundle"], admitted["model_bundle"])
        self.assertEqual(revised["teacher"], teacher)
        self.assertEqual(revised["school"]["current_student"], admitted["school"]["current_student"])
        self.assertEqual(set(revised["school"]["champions"]), {"A"})
        self.assertIn(B_COMPOSITE, revised["school"]["queue"])
        self.assertEqual(len(revised["school"]["queue"]), 7)
        self.assertIsNone(revised["last_exam"])
        self.assertNotIn("qualification_cohort", revised)
        self.assertEqual(revised["curriculum_history"][-1]["revised_grade"], "B")
        self.assertEqual(revised["curriculum_history"][-1]["retired_grade_champion"],
                         asdict(pointer))
        self.assertEqual(revised["mentor_epoch"]["active_roles"], {})
        self.assertEqual(revised["mentor_epoch"]["active_grade_soups"], {})

    def test_grade_b_transition_carries_permanent_settled_match_history_only(self):
        from bilqis_mlx.learning.mentor_epoch import begin_initial_epoch
        pointer = Checkpoint("a"*64,"bundles/inert",153144,True)
        school = self._graduated_a(pointer)
        epoch = begin_initial_epoch(
            student=asdict(pointer), introduced_grade="A",
            source_graph_sha256=self.manifest["parent_student"]["full_student_graph_sha256"],
            frontier={}, soups={})
        key = "A.IDENTITY|" + "a" * 64 + "|" + "b" * 64
        epoch["settled_matchups"] = {
            key: {"decision": "TITLE_DEFENDED", "winner_sha256": "a" * 64}}
        receipt = self._receipt(school, pointer, mentor_epoch=epoch)
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            root = Path(temp)
            saved = _persist(root, receipt)
            updated = _activate_next_admitted_grade(
                root, saved, self.a_course, self.b_course)
        self.assertEqual(updated["mentor_epoch"]["settled_matchups"],
                         epoch["settled_matchups"])
        self.assertEqual(updated["mentor_epoch"]["active_roles"], {})
        self.assertEqual(updated["mentor_epoch"]["active_grade_soups"], {})

    def test_admission_interrupt_after_immutable_state_replays_once_not_student(self):
        """A lost publication acknowledgment never repeats A->B mutation."""
        pointer = Checkpoint("a"*64,"bundles/inert",153144,True)
        school = self._graduated_a(pointer)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = _persist(root,self._receipt(school,pointer))
            with patch("bilqis_mlx.trainer._record",
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
            self.assertEqual(events[0]["event"],"SCHOOL_NEXT_GRADE_COURSE_ADMITTED")
            self.assertEqual(events[0]["previous_grade"], "A")
            self.assertEqual(events[0]["grade"], "B")
            self.assertEqual(events[0]["event_id"],saved["delivery_outbox"][0]["event_id"])

    def test_partial_event_write_recovery_exactly_once_and_detects_tampering(self):
        record = {"run_id":"test-event-journal", "generation":7}
        events = ({"event":"GRADE_A_TEACHER_VISIT_COMMITTED","grade":"A"},
                  {"event":"SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED","grade":"B"})
        record = _with_delivery_outbox(record,events)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            from bilqis_mlx.trainer import _record
            journal = root/"events.jsonl"
            old_record = _record
            delivered = []
            def fail_on_second(path,event):
                if delivered:
                    raise OSError("disk-interrupted-event-publication")
                delivered.append(event["event_id"])
                return old_record(path,event)
            with patch("bilqis_mlx.trainer._record",side_effect=fail_on_second):
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
            from bilqis_mlx.trainer import _durable_json
            _durable_json(root/"state.json",old,replace_existing=True)
            from bilqis_mlx.source import AUDITED_PARENT
            fake_meta = {"source_digest":AUDITED_PARENT.sha256,
                         "safetensors_sha256":sha,"optimizer_step":153144}
            with (patch("bilqis_mlx.trainer.load_semantically_bound_bundle",
                        return_value=(params,optimizer,fake_meta,graph)),
                  patch("bilqis_mlx.trainer._verify_best_custody"),
                  patch("bilqis_mlx.trainer._verify_saved_cohort"),
                  patch("bilqis_mlx.trainer._publish_boundary"),
                  redirect_stdout(io.StringIO())):
                saved_params, saved_optimizer, saved_graph, recovered = _resume(
                    root,self.manifest,self.b_course,self.teacher_sha,
                    grade_a_course=self.a_course, source_root=SOURCE_ROOT,
                    successor_course=self.b_course)
            self.assertEqual(recovered["school"]["current_student"],
                             successor["school"]["current_student"])
            self.assertEqual(recovered["teacher"], successor["teacher"])
            self.assertGreater(recovered["generation"], successor["generation"])
            self.assertIn("factory_admission_v2", recovered)
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
            with self.assertRaisesRegex(ValueError,"NEXT_GRADE_ADMISSION_BOUNDARY"):
                _activate_next_admitted_grade(root,receipt,self.a_course,self.b_course)
            draft = replace(self.b_course, grades=(self.b_course.grades[0],
                replace(self.b_course.grades[1],assessment_sha256=None)))
            with self.assertRaisesRegex(ValueError,"NEXT_GRADE_ADMISSION_BOUNDARY"):
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

    def test_fixed_grade_b_screen_covers_all_six_rubric_capabilities(self):
        from bilqis_mlx.curriculum.scheduler import append_next_grade, next_capability
        from bilqis_mlx.learning.learning_experiment import Settings
        import torch
        graph = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)["graph"]
        rows = _draw_live_rows(SOURCE_ROOT, graph, seed=222, course=self.b_course)
        cohort = make_cohort(rows, generator_version=B_GENERATOR,
                             seed=222, rubric_version=B_RELEASE)
        pointer = Checkpoint("a"*64, "bundles/not-loaded", 155, True)
        school = append_next_grade(self.a_course, self.b_course,
                                   self._graduated_a(pointer))
        while next_capability(school):
            school = visit(self.b_course, school, next_capability(school), pointer)
        self.assertTrue(school.stage.startswith("ASSESS_"))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stored = _persist_live_cohort(root, self.manifest, self.b_course, cohort)
            receipt = {"run_id": "grade-net-source-fixture", "generation": 1,
                       "source_manifest_sha256": self.manifest["manifest_sha256"],
                       "last_exam": {"assessment_grade": "B",
                                     "grade_exam_epoch": school.grade_exam_epoch,
                                     "cohort_sha256": cohort.digest,
                                     "cohort_seed": cohort.seed,
                                     "cohort_file": stored,
                                     "scores": {cap.id: {"correct": 11, "total": 12}
                                                for grade in self.b_course.grades
                                                for cap in grade.capabilities}}}
            selected = _fixed_same_grade_rows(
                root, receipt, self.b_course, school, "B.XOR", Settings())
            fresh, guarded, omitted = _learning_probe_rows(
                SOURCE_ROOT, graph, receipt, self.b_course,
                school, "B.XOR", Settings())
        self.assertEqual(len(selected), 72)
        self.assertEqual({cap: sum(r["capability"] == cap for r in selected)
                          for cap in ("B.AND", "B.IFF", "B.IMPLIES",
                                      "B.NOT", "B.OR", "B.XOR")},
                         {cap: 12 for cap in ("B.AND", "B.IFF", "B.IMPLIES",
                                              "B.NOT", "B.OR", "B.XOR")})
        self.assertEqual({cap: sum(r["capability"] == cap for r in fresh)
                          for cap in ("B.AND", "B.IFF", "B.IMPLIES",
                                      "B.NOT", "B.OR", "B.XOR")},
                         {cap: 12 for cap in ("B.AND", "B.IFF", "B.IMPLIES",
                                              "B.NOT", "B.OR", "B.XOR")})
        self.assertEqual(len(guarded), 8)
        self.assertEqual(omitted, 3)

    def test_b_weakest_three_rehearsal_credits_actual_a_lesson_not_b(self):
        """An A predicate taught during B recovery must train A's policy stats."""
        from types import SimpleNamespace
        from bilqis_mlx.curriculum.scheduler import append_next_grade
        pointer = Checkpoint("a"*64,"bundles/toy-only",300,True)
        school = append_next_grade(self.a_course,self.b_course,self._graduated_a(pointer))
        school = replace(school, stage="RECOVERY_1",queue=("A.IDENTITY",),
                         first_recovery=("A.IDENTITY",))
        misses = [
            {"id":"old-true","capability":"A.IDENTITY","tokens":[4,6],"gold":"TRUE"},
            {"id":"old-false","capability":"A.IDENTITY","tokens":[4,7],"gold":"FALSE"},
        ]
        receipt = self._receipt(school,pointer,config={"heads":3,"layers":1},
                                answer_ids=[6,7],curriculum_mode=B_RELEASE,
                                teacher_misses=misses,
                                teacher_miss_exposures={"old-true":2,"old-false":1})
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

        import torch
        graph = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)["graph"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt["semantic_graph_sha256"] = _fingerprint(graph)
            receipt, _, _ = admit_executable_school(
                root, receipt, self.b_course, self.a_course, SOURCE_ROOT, graph)
            with (patch("bilqis_mlx.trainer._draw_live_rows",
                        return_value=examples),
                  patch("bilqis_mlx.trainer.load_semantically_bound_bundle",
                        side_effect=AssertionError("prior grade master cannot nominate rows")),
                  patch("bilqis_mlx.trainer._train_score",return_value=.5),
                  patch("bilqis_mlx.trainer._predictions",
                        return_value={"old-true":"TRUE","old-false":"TRUE"}),
                  patch("bilqis_mlx.trainer._train_step",side_effect=toy_step)):
                updated = _take_visit(
                    None,root,receipt,self.manifest,
                    self.b_course,Teacher(),{},optimizer,graph,steps_per_visit=1,
                    batch_size=4,reserve_gib=0.,source_root=SOURCE_ROOT)
        self.assertEqual(observed,[("pick","A"),("observe","A")])
        event = updated["_pending_visit_events"][0]
        self.assertEqual(event["capability"],"A.IDENTITY")
        self.assertEqual(event["grade"],"A")
        self.assertEqual(event["active_grade"],"B")
        self.assertEqual(event["event"],"SCHOOL_TEACHER_VISIT_COMMITTED")
        self.assertEqual(event["prior_grade_champion_votes"], {})
        self.assertEqual(event["champion_directed_examples_available"], 0)
        self.assertEqual([row["id"] for row in updated["teacher_misses"]], ["old-false"])
        self.assertNotIn("old-true", updated["teacher_miss_exposures"])
        self.assertEqual(event["prior_exam_misses_available"],2)
        self.assertEqual(event["prior_exam_misses_remaining"],1)
        self.assertEqual(event["teacher_decision"]["selected"]["exam_mistakes_resolved"],1)

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
        with (patch("bilqis_mlx.trainer._record",
                    side_effect=lambda _,event:observed.append(event)),
              patch("bilqis_mlx.trainer._quarantine_newer_uncommitted_bundles"),
              patch("bilqis_mlx.trainer.retire_bundles",return_value=())):
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
                receipt, _, program = admit_executable_school(
                    root, receipt, self.b_course, self.a_course, SOURCE_ROOT, graph)

            def perfect_oracle_predictions(mx,parameters,rows,config,answer_ids):
                return {r["id"]:r["gold"] for r in rows}

            qualification_cohorts = []
            complete_grade_soups = None
            for expected_grade in ("B","A","B"):
                self.assertEqual(_state_from_json(receipt["school"],program).grade,
                                 expected_grade)
                with redirect_stdout(io.StringIO()):
                    for _ in range(6):
                        receipt = _take_visit(
                            mx,root,receipt,self.manifest,self.b_course,self.engine,
                            params,opt,graph,steps_per_visit=1,batch_size=4,
                            reserve_gib=0.,source_root=SOURCE_ROOT)
                self.assertEqual(receipt["school"]["stage"],"ASSESS_MAIN")
                diagnostic_observer = (
                    patch("bilqis_mlx.diagnostics.exam_events.observe_binary_exam",
                          side_effect=ValueError("INJECTED_DIAGNOSTIC_OBSERVER_FAILURE"))
                    if not qualification_cohorts else nullcontext()
                )
                with (patch("bilqis_mlx.trainer._predictions",
                            side_effect=perfect_oracle_predictions),
                      diagnostic_observer, redirect_stdout(io.StringIO())):
                    receipt = _take_exam(
                        mx,root,receipt,self.manifest,self.b_course,
                        SOURCE_ROOT,CHECKPOINT,params,opt,graph,reserve_gib=0.)
                exam = receipt["last_exam"]
                qualification_cohorts.append(exam["cohort_sha256"])
                self.assertEqual(len(exam["scores"]),12)
                self.assertEqual(sum(s["total"] for s in exam["scores"].values()),144)
                self.assertTrue(all(s["correct"] == s["total"] for s in exam["scores"].values()))
                self.assertEqual(len(exam["cohort_sha256"]),64)
                # SPEC-0002 rev9/10 separates title jurisdiction from checkpoint
                # training provenance and transfers a defended title on a tie.
                epoch = receipt["mentor_epoch"]
                self.assertEqual(set(epoch["active_roles"]), set(self.b_course.capability_map))
                for capability, role in epoch["active_roles"].items():
                    self.assertEqual(role["origin_grade"], capability.partition(".")[0])
                    self.assertEqual(role["checkpoint_origin_grade"], expected_grade)
                active_soups = epoch["active_grade_soups"]
                self.assertEqual(set(active_soups), {"A", "B"})
                self.assertEqual(set(exam["grade_soups_refreshed"]), {"A", "B"})
                self.assertEqual({entry["vote_count"] for entry in active_soups.values()}, {6})
                soup_shas = {grade: entry["sha256"] for grade, entry in active_soups.items()}
                if complete_grade_soups is not None:
                    self.assertTrue(all(soup_shas[g] != complete_grade_soups[g] for g in soup_shas))
                complete_grade_soups = soup_shas
            self.assertEqual(len(set(qualification_cohorts)), 3,
                             "Every grade enrollment, including a revisit, gets a new test")
            final = _state_from_json(receipt["school"],program)
            self.assertEqual(final.stage,"AWAITING_NEXT_GRADE")
            self.assertEqual(final.active_grades,("A","B"))
            self.assertEqual(final.revalidation_target_grade,None)
            self.assertEqual(set(final.champions),{"A","B"})
            self.assertEqual(opt.state["step"].item(),19)
            self.assertEqual(receipt["teacher"]["events"],self.teacher["events"]+18)
            self.assertEqual(json.loads((root/"state.json").read_text()),receipt)
            events = [json.loads(line) for line in
                      (root/"events.jsonl").read_text().splitlines()]
            teacher_visits = [event for event in events if event.get("event") ==
                              "SCHOOL_TEACHER_VISIT_COMMITTED"]
            self.assertTrue(teacher_visits)
            # Each lesson receives direct advice from its own earned title-grade
            # roles; the separately diluted soups span the admitted grades.
            self.assertTrue(all(event.get("prior_grade_champion_votes") == {}
                                for event in teacher_visits))
            self.assertTrue(all(event["champion_confidence"]["direct_capability_votes"] ==
                                ({} if index < 6 else {"A": 6} if index < 12 else {"B": 6})
                                for index, event in enumerate(teacher_visits)))
            self.assertTrue(all(event.get("champion_directed_examples_available") == 0
                                for event in teacher_visits))
            b_visits = [e for e in events if e.get("event") ==
                        "SCHOOL_TEACHER_VISIT_COMMITTED" and e.get("grade") == "B"]
            self.assertEqual(len(b_visits), 12)
            with_soups = [e for e in events if e.get("event") ==
                          "SCHOOL_GRADE_SOUP_FROZEN"]
            self.assertEqual(len(with_soups), 6)
            self.assertEqual({e["grade"] for e in with_soups}, {"A", "B"})
            for event in b_visits[6:]:
                votes = {v["soup_grade"]: v["effective_votes"] for v in
                         event["champion_confidence"]["frozen_grade_soups"]}
                self.assertEqual(votes, {"A": 3.0, "B": 6.0})
            for event in b_visits:
                evidence = event["lesson_methodology"]
                decision = event["teacher_decision"]
                self.assertEqual(evidence["delivered_examples"], 4)
                self.assertEqual(evidence["optimizer_batches_observed"], 1)
                self.assertTrue(evidence["constituent_capabilities_delivered"])
                self.assertEqual(evidence["findings"][0]["status"], DiagnosticStatus.NOT_OBSERVED)
                self.assertNotEqual(evidence["findings"][1]["status"], DiagnosticStatus.NOT_MEASURED)
                self.assertEqual(decision["capability"], event["capability"])
                self.assertEqual(decision["policy_key"], event["teacher_policy"])
                self.assertIn(TeachingOpportunity.PREREQUISITE_CONNECTION,
                              decision["opportunities"])
                self.assertEqual(len(decision["decision_id"]), 64)
            examination_events = [e for e in events if e.get("event") ==
                                  "SCHOOL_LIVE_EXAM_COMMITTED"]
            self.assertEqual(len(examination_events), 3)
            for index, event in enumerate(examination_events):
                warnings = event["learning_diagnostics"]
                self.assertEqual(warnings["assessment_cohort_sha256"],
                                 event["cohort_sha256"])
                self.assertEqual(warnings["optimizer_step"], event["optimizer_step"])
                self.assertEqual(warnings["active_warnings"], [])
                if index == 0:
                    self.assertFalse(warnings["history_usable"])
                    self.assertEqual(warnings["history_issue"],
                                     "INJECTED_DIAGNOSTIC_OBSERVER_FAILURE")
                    self.assertTrue(warnings["findings"])
                    self.assertTrue(all(finding["status"] == DiagnosticStatus.NOT_MEASURED
                                        for finding in warnings["findings"]))
                self.assertTrue(any(f["signal"] == LearningSignal.CHANCE_LEVEL_OR_LAGGING and
                                    f["target"] == "GRADE" for f in warnings["findings"]))
                self.assertEqual(len(event["teacher_outcomes"]), 6)
                # The complete Grade A graduation proof is now bound to
                # admission. Its older cohort cannot be scored as a B exam
                # baseline, so even the first B visit reports changed exam.
                expected_attribution = OutcomeAttribution.NOT_MEASURED_CHANGED_EXAM
                self.assertEqual({outcome["attribution"] for outcome in event["teacher_outcomes"]},
                                 {expected_attribution})
            self.assertEqual(receipt["last_exam"]["learning_diagnostics"],
                             examination_events[-1]["learning_diagnostics"])
            self.assertEqual(receipt["last_exam"]["teacher_outcomes"],
                             examination_events[-1]["teacher_outcomes"])
            from bilqis_mlx.diagnostics.audit import audit_saved_run
            audit = audit_saved_run(root)
            self.assertEqual(audit["verified_methodology_visit_count"], 18)
            self.assertEqual(audit["verified_teacher_decision_count"], 18)
            self.assertEqual(set(audit["latest_teacher_decisions"]), {
                cap.id for grade in self.b_course.grades for cap in grade.capabilities})
            self.assertEqual(audit["latest_teacher_outcomes"],
                             examination_events[-1]["teacher_outcomes"])
            self.assertEqual(audit["unresolved_teacher_miss_count"], 0)
            latest_b = next(item for item in audit["current_findings"] if
                            item["capability"] == "B.NOT" and
                            item["signal"] == LearningSignal.DISCONNECTED_PREREQUISITES)
            self.assertEqual(latest_b["status"], DiagnosticStatus.NOT_OBSERVED)
            # A plausible but uncommitted rewritten teaching warning must
            # not enter the audit merely because it appears in events.jsonl.
            ledger = root / "events.jsonl"
            original = ledger.read_text()
            changed = [json.loads(line) for line in original.splitlines()]
            target = next(event for event in changed if "lesson_methodology" in event)
            target["lesson_methodology"]["findings"][0]["status"] = DiagnosticStatus.NOT_MEASURED
            ledger.write_text("".join(json.dumps(e) + "\n" for e in changed))
            with self.assertRaisesRegex(ValueError, "METHOD_LEDGER_OUTBOX_CONFLICT"):
                audit_saved_run(root)
            ledger.write_text(original)
            self.assertEqual(audit_saved_run(root)["verified_methodology_visit_count"], 18)


if __name__ == "__main__":
    unittest.main()
