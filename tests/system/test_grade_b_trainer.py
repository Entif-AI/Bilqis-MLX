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
    VERSION, _bundle_pointer, _draw_live_rows, _fingerprint, _persist, _ensure_executable_release, _fixed_same_grade_rows, _learning_probe_rows, _migrate_championship_governance, _persist_live_cohort, _recover_orphaned_commit, _seed, _state_from_json, _publish_boundary, _reconcile_delivery_outbox, _resume, _schedule_for_receipt, _take_exam, _take_visit, _verify_saved_cohort, _with_delivery_outbox, prepare_source
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
            with patch('bilqis_mlx.runtime.checkpoints._record',side_effect=fail_on_second):
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
        import torch
        from types import SimpleNamespace
        from bilqis_mlx.curriculum.scheduler import append_next_grade
        graph = torch.load(CHECKPOINT,map_location="cpu",weights_only=True)["graph"]
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

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt = _persist(root, receipt)
            receipt, _, _ = _ensure_executable_release(
                root, receipt, self.b_course, self.a_course, SOURCE_ROOT, graph)
            with (patch('bilqis_mlx.runtime.assessment._draw_live_rows',
                        return_value=examples),
                  patch('bilqis_mlx.runtime.mlx_checkpoint.load_semantically_bound_bundle',
                        side_effect=AssertionError("prior grade master cannot nominate rows")),
                  patch('bilqis_mlx.learning.student_ops._train_score',return_value=.5),
                  patch('bilqis_mlx.learning.student_ops._predictions',
                        return_value={"old-true":"TRUE","old-false":"TRUE"}),
                  patch('bilqis_mlx.learning.student_ops._train_step',side_effect=toy_step)):
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
        with (patch('bilqis_mlx.runtime.checkpoints._record',
                    side_effect=lambda _,event:observed.append(event)),
              patch('bilqis_mlx.runtime.checkpoints._quarantine_newer_uncommitted_bundles'),
              patch('bilqis_mlx.learning.capability_frontier.retire_bundles',return_value=())):
            _publish_boundary(Path("/dummy"), record, (), (grade_b_role,),
                              exam_event={"event":"SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
                                          "grade":"B"})
        best = next(event for event in observed if event["event"] ==
                    "SCHOOL_CAPABILITY_BEST_COMMITTED")
        self.assertEqual(best["grade"],"B")
        self.assertEqual(best["capabilities"],[grade_b_role])


class TestDisposableAppendWriter(unittest.TestCase):
    """Exercise the real A->B append writer without historical checkpoint gates."""

    @classmethod
    def setUpClass(cls):
        from bilqis_mlx.compatibility import historical_teacher_policy as policy

        cls.manifest = json.loads(MANIFEST.read_text())
        cls.a_course = a_live_course(accepted_grade_a(cls.manifest))
        cls.b_course = b_live_course(cls.a_course, SOURCE_ROOT)
        strategy = {
            "old": 4, "preview": 0, "depth": 1, "contrast": 0.0,
            "lr": 0.00013, "distill": 0.0,
        }
        key = policy._policy_key(strategy)
        cls.teacher = {
            "strategies": {key: strategy},
            "global_stats": {key: policy._stats()},
            "grade_stats": {}, "events": 0, "mutations": 0,
        }
        cls.teacher_sha = _fingerprint({
            "fixture_only": "grade-b-append-writer-disposable-policy/v1",
            "teacher": cls.teacher,
        })

    def setUp(self):
        self.manifest = self.__class__.manifest
        self.a_course = self.__class__.a_course
        self.b_course = self.__class__.b_course
        self.teacher_sha = self.__class__.teacher_sha
        self.teacher = json.loads(json.dumps(self.__class__.teacher))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _saved_append_boundary(self):
        weights = b"disposable-model-and-own-adamw"
        sha = hashlib.sha256(weights).hexdigest()
        pointer = Checkpoint(sha, "bundles/append-writer", 153144, True)
        bundle = self.root / pointer.filename
        bundle.mkdir(parents=True)
        manifest = {"safetensors_sha256": sha,
                    "optimizer_step": pointer.optimizer_step}
        payload = bundle / "model-and-own-adamw.safetensors"
        payload.write_bytes(weights)
        (bundle / "manifest.json").write_text(json.dumps(manifest))
        school = start_new(self.a_course, pointer)
        for capability in self.a_course.grades[0].capabilities:
            school = visit(self.a_course, school, capability.id, pointer)
        scores = {
            capability.id: Score(12, 12)
            for capability in self.a_course.grades[0].capabilities
        }
        school = assess(self.a_course, school, Assessment(
            pointer.sha256, pointer.optimizer_step, self.a_course.digest(),
            self.a_course.grades[0].assessment_sha256, scores,
            "fixture-intact-grade-a"))
        # The append transaction consumes an already-admitted Grade-A boundary;
        # this disposable fixture supplies that boundary without claiming a
        # historical or human-trained checkpoint.
        school = replace(
            school, stage="AWAITING_NEXT_GRADE",
            champions={**school.champions, "A": pointer},
            queue=(), first_recovery=(), pending_failures=(),
            promotion_sweep_scope=(), promotion_sweep_return_stage=None,
            promotion_sweep_scores=())
        receipt = GradeBTrainerTests._receipt(self, school, pointer)
        saved = _persist(self.root, receipt)
        return pointer, weights, manifest, saved, payload


if __name__ == "__main__":
    unittest.main()
