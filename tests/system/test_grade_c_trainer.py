"""Disposable staged C through real trainer functions, never operate/human-run."""
from contextlib import redirect_stdout
from dataclasses import asdict, replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.compatibility.frontier_recovery import (
    _measure_debt_admission_boundary, _migrate_grade_c_fixed_frontier)
from bilqis_mlx.trainer import (_bundle_pointer, _fingerprint, _persist,
    _ensure_executable_release, _migrate_championship_governance, _resume,
    _state_from_json, _take_exam, _take_visit, prepare_source)
from bilqis_mlx.grade_transition import activate_numeric_grade
from bilqis_mlx.live_grade_a import live_course as a_course
from bilqis_mlx.live_grade_b import RELEASE as B_RELEASE, constructor_digest as b_digest, live_course as b_course
from bilqis_mlx.live_grade_c import PLANS, RELEASE as C_RELEASE, live_course, prepare_course
from bilqis_mlx.curriculum.scheduler import Assessment, Score, assess, next_capability, start_new, visit
from bilqis_mlx.source import AUDITED_PARENT

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "vendor" / "legacy-v16"
PARENT = SOURCE / "runs/primitive-consolidation-v16-triplets" / AUDITED_PARENT.basename
MANIFEST = ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


class GradeCTrainerTests(unittest.TestCase):
    def test_other_epoch_does_not_replay_original_c_admission(self):
        from bilqis_mlx.compatibility.frontier_recovery import _recover_grade_c_boundary_source
        current = {"sha256": "b" * 64, "optimizer_step": 14}
        receipt = {"grade_c_parent_course_digest": "d" * 64,
                   "school": {"current_student": current},
                   "mentor_epoch": {"introduced_grade": "B", "baseline": current},
                   "last_exam": {"student_sha256": "a" * 64, "optimizer_step": 13}}
        self.assertIsNone(_recover_grade_c_boundary_source(
            None, Path("/unused"), receipt))

    @classmethod
    def setUpClass(cls):
        cls.manifest, old, cls.engine, cls.policy_sha, cls.teacher, _ = prepare_source(SOURCE, PARENT, MANIFEST)
        cls.grade_a = a_course(old)
        cls.previous = b_course(cls.grade_a, SOURCE)
        from bilqis_mlx.pedagogical_parity import _source_stack
        _, _, _, _, cls.parent_graph, _ = _source_stack(SOURCE)
        cls.course, cls.graph = prepare_course(cls.previous, maximum=10)

    def toy(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        import numpy as np
        mx.set_default_device(mx.cpu)
        rng, width = np.random.default_rng(5), 12
        shapes = {"embedding.weight": (len(self.parent_graph["tokens"]), width),
                  "position.weight": (96, width), "norm.weight": (width,)}
        for i in range(6):
            shapes.update({f"blocks.{i}."+name: shape for name,shape in {
                "n1.weight": (width,), "n2.weight": (width,), "qkv.weight": (3*width,width),
                "proj.weight": (width,width), "up.weight": (2*width,width), "down.weight": (width,2*width)}.items()})
        params = {name: mx.array(rng.normal(0,.01,shape).astype(np.float32) if len(shape)>1
                                else np.ones(shape,dtype=np.float32)) for name,shape in shapes.items()}
        opt = optim.AdamW(learning_rate=.00013, bias_correction=True)
        opt.update(params, {name: mx.zeros_like(value) for name,value in params.items()})
        mx.eval(params,opt.state)
        return mx, params, opt

    def graduated(self, pointer):
        school = start_new(self.previous, pointer)
        for grade in ("A", "B", "A", "B"):
            while next_capability(school):
                school = visit(self.previous, school, next_capability(school), pointer)
            scores = {c.id: Score(12,12) for g in self.previous.grades
                      if g.id in school.champions or g.id == grade for c in g.capabilities}
            rubric = self.previous.grades[1 if any(c.startswith("B.") for c in scores) else 0].assessment_sha256
            school = assess(self.previous, school, Assessment(pointer.sha256,pointer.optimizer_step,
                self.previous.digest(),rubric,scores,"toy-pass"))
            while school.stage == "PROMOTION_SWEEP":
                school = visit(
                    self.previous, school, next_capability(school), pointer)
                school = assess(
                    self.previous, school,
                    Assessment(pointer.sha256, pointer.optimizer_step,
                               self.previous.digest(), rubric, scores,
                               "toy-stability-pass"))
        return school

    def receipt(self, school, pointer, params):
        from bilqis_mlx.trainer import VERSION
        from bilqis_mlx.grade_a_release import AUTHORITY
        return dict(schema=VERSION,run_id="disposable-c-only",generation=1,
            accepted_authority=AUTHORITY, source_manifest_sha256=self.manifest["manifest_sha256"],
            teacher_source_sha256=self.policy_sha, grade_b_code_sha256=b_digest(),
            curriculum_mode=B_RELEASE,school=asdict(school),model_bundle=pointer.filename,
            config={"heads":3,"layers":6}, answer_ids=[6,7],
            parameter_shapes={n:list(v.shape) for n,v in params.items()},
            semantic_graph_sha256=_fingerprint(self.parent_graph),
            live_rubric_sha256=self.previous.grades[-1].assessment_sha256,
            teacher=json.loads(json.dumps(self.teacher)),capability_best={},
            last_exam=dict(student_sha256=pointer.sha256,optimizer_step=pointer.optimizer_step,
                cohort_sha256="c"*64,
                exam_rubric_sha256=self.previous.grades[-1].assessment_sha256,
                scores={c.id: {"correct":12,"total":12} for g in self.previous.grades for c in g.capabilities}))

    def debt_receipt(self, pointer, params, *, session_id):
        school = start_new(self.previous, pointer)
        b = self.previous.grades[-1]
        school = replace(
            school, grade_index=1,
            introduction_stage=(len(b.teaching_stages)-1 if b.teaching_stages else 0),
            stage="RECOVERY_2", queue=("B.AND", "B.IFF"),
            first_recovery=("B.AND", "B.IFF"), champions={"A": pointer},
            latest_rubric_digest=b.assessment_sha256)
        receipt = self.receipt(school, pointer, params)
        receipt["stagnation_session"] = {
            "schema": "bilqis.mlx.stagnation-session/v1",
            "session_id": session_id, "started_generation": 1,
            "required_capabilities": [
                cap.id for grade in self.previous.grades for cap in grade.capabilities],
            "cycle_index": 3, "cycle_first_recovery": [], "cycle_visits": {},
            "quarantined": {}, "alerts": [],
            "rehabilitation": {
                "grade": "B", "capabilities": ["B.AND", "B.IFF"],
                "started_generation": 1,
                "reason": "SOLE_REMAINING_GRADE_MASTERY_DEBT",
            },
        }
        return receipt

    @staticmethod
    def boundary_predictions(_mx, _params, rows, *_args):
        miss_ids = {
            min(row["id"] for row in rows if row["capability"] == cap)
            for cap in {"A.EDGE", "B.AND", "B.IFF"}
        }
        return {
            row["id"]: ("FALSE" if row["gold"] == "TRUE" else "TRUE")
            if row["id"] in miss_ids else row["gold"]
            for row in rows
        }

    def test_c_resume_selects_the_exact_historical_parent_release(self):
        from bilqis_mlx.compatibility.historical_live_release import (
            HISTORICAL_B_COURSE_SHA256, resume_grade_courses)
        a, b = resume_grade_courses(accepted_grade_a(self.manifest), SOURCE,
            {'curriculum_mode': C_RELEASE, 'school': {'course_digest': 'successor'},
             'grade_c_parent_course_digest': HISTORICAL_B_COURSE_SHA256})
        self.assertEqual(b.digest(), HISTORICAL_B_COURSE_SHA256)
        self.assertEqual(a.grades, b.grades[:1])

    def test_c_requires_one_complete_cumulative_a_b_result_before_growth(self):
        mx, params, opt = self.toy()
        pointer = Checkpoint("a"*64,"bundles/inert",1,True)
        receipt = self.receipt(self.graduated(pointer), pointer, params)
        receipt["last_exam"]["scores"]["B.NOT"]["correct"] = 11
        with patch("bilqis_mlx.grade_transition.extend_mlx_student", side_effect=AssertionError("premature growth")):
            with self.assertRaisesRegex(ValueError,"CUMULATIVE_A_B"):
                activate_numeric_grade(mx, Path("/unused"), receipt, self.previous, self.course,
                    params,opt,self.parent_graph,reserve_gib=0.)

    def test_human_debt_admission_grows_c_without_fabricating_b_mastery(self):
        mx, params, opt = self.toy()
        pointer = Checkpoint("a"*64,"bundles/inert",1,True)
        receipt = self.debt_receipt(pointer, params, session_id="debt-admission")
        # Mirror the live staged-B shape: the hot `last_exam` is narrower than
        # the full declared prior release and there is no complete same-checkpoint
        # generalization event to recover. Debt admission itself must measure it.
        omitted = next(cap for cap in receipt["last_exam"]["scores"]
                       if cap.startswith("B.") and cap not in ("B.AND", "B.IFF"))
        receipt["last_exam"]["scores"] = {
            cap: value for cap, value in receipt["last_exam"]["scores"].items()
            if cap != omitted
        }
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            root = Path(temp)
            receipt = _persist(root, receipt)
            with patch('bilqis_mlx.learning.student_ops._predictions',
                       side_effect=self.boundary_predictions):
                receipt = _measure_debt_admission_boundary(
                    mx, root, receipt, self.manifest, self.previous, SOURCE,
                    params, self.parent_graph)
                grown, own, graph, changed = activate_numeric_grade(
                    mx, root, receipt, self.previous, self.course,
                    params, opt, self.parent_graph, reserve_gib=0.,
                    allow_mastery_debt=True)
            from bilqis_mlx.fixed_frontier import load_frontier
            current = changed["school"]["current_student"]
            rows, parent = load_frontier(
                root, changed,
                parent_sha256=current["sha256"],
                parent_optimizer_step=current["optimizer_step"])
            self.assertEqual(
                len(rows),
                sum(count for grade in self.previous.grades
                    for _, count in grade.exam_item_counts))
            self.assertEqual(set(parent), {row["id"] for row in rows})

        changed_school = changed["school"]
        self.assertEqual(
            changed_school["carried_mastery_debt"],
            ["A.EDGE", "B.AND", "B.IFF"])
        self.assertEqual(
            changed_school["active_grades"][changed_school["grade_index"]], "C")
        self.assertEqual(set(changed_school["champions"]), {"A"})
        self.assertEqual(changed["mentor_epoch"]["previous_mastery_debt"],
                         ["A.EDGE", "B.AND", "B.IFF"])
        self.assertIsNone(changed["grade_c_debt_source_generation"])
        self.assertEqual(changed["grade_c_debt_source_exam_plane"],
                         "DEBT_ADMISSION_BOUNDARY")
        self.assertNotIn("debt_admission_boundary_exam", changed)
        from bilqis_mlx.learning.mentor_epoch import reference_checkpoints
        references = reference_checkpoints(changed["mentor_epoch"])
        self.assertIn(pointer.sha256, {item["sha256"] for item in references})
        self.assertEqual(int(own.state["step"].item()), int(opt.state["step"].item()))

    def test_c_checks_native_catalog_without_external_review_before_growth(self):
        mx, params, opt = self.toy()
        pointer = Checkpoint("a"*64,"bundles/inert",1,True)
        receipt = self.receipt(self.graduated(pointer), pointer, params)
        with patch("bilqis_mlx.grade_transition.expanded_graph",
                   side_effect=ValueError("NATIVE_CATALOG_INVALID")), \
                patch("bilqis_mlx.next_grade_review.require_admission_review",
                      side_effect=AssertionError("research review entered")), \
                patch("bilqis_mlx.grade_transition.extend_mlx_student",
                      side_effect=AssertionError("premature growth")):
            with self.assertRaisesRegex(ValueError, "NATIVE_CATALOG_INVALID"):
                activate_numeric_grade(mx, Path("/unused"), receipt, self.previous,
                    self.course, params, opt, self.parent_graph, reserve_gib=0.)

    def test_resume_repairs_pre_fix_c_frontier_from_exact_debt_boundary(self):
        mx, params, opt = self.toy()
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            root = Path(temp)
            pointer = _bundle_pointer(
                root, "pre-c", params, opt, self.parent_graph, reserve_gib=0.)
            pre = self.debt_receipt(
                pointer, params, session_id="debt-admission-recovery")
            pre = _persist(root, pre)
            with patch('bilqis_mlx.learning.student_ops._predictions',
                       side_effect=self.boundary_predictions):
                measured = _measure_debt_admission_boundary(
                    mx, root, pre, self.manifest, self.previous, SOURCE,
                    params, self.parent_graph)
                grown, own, graph, admitted = activate_numeric_grade(
                    mx, root, measured, self.previous, self.course,
                    params, opt, self.parent_graph, reserve_gib=0.,
                    allow_mastery_debt=True)

            # Recreate the historical bug: admission succeeded, but last_exam
            # still names the pre-growth parent instead of the grown C baseline.
            broken = json.loads(json.dumps(admitted))
            broken["last_exam"] = json.loads(json.dumps(pre["last_exam"]))
            broken.pop("grade_c_fixed_frontier_cohort_sha256", None)
            with patch('bilqis_mlx.learning.student_ops._predictions',
                       side_effect=self.boundary_predictions):
                repaired = _migrate_grade_c_fixed_frontier(
                    mx, root, broken, self.course, grown)
            current = repaired["school"]["current_student"]
            self.assertEqual(repaired["generation"], broken["generation"] + 1)
            self.assertEqual(repaired["last_exam"]["student_sha256"],
                             current["sha256"])
            self.assertEqual(repaired["last_exam"]["optimizer_step"],
                             current["optimizer_step"])
            self.assertEqual(repaired["last_exam"]["exam_plane"],
                             "FIXED_FRONTIER_REBASELINE")
            self.assertEqual(
                repaired["last_exam"]["scores"],
                admitted["last_exam"]["scores"])
            self.assertEqual(
                _migrate_grade_c_fixed_frontier(
                    mx, root, repaired, self.course, grown), repaired)

    def test_c_graph_growth_starts_empty_authority_and_carries_settled_history(self):
        from bilqis_mlx.learning.mentor_epoch import begin_initial_epoch
        mx, params, opt = self.toy()
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            root = Path(temp)
            pointer = _bundle_pointer(root, "initial", params, opt,
                                      self.parent_graph, reserve_gib=0.)
            receipt = self.receipt(self.graduated(pointer), pointer, params)
            epoch = begin_initial_epoch(
                student=asdict(pointer), introduced_grade="B",
                source_graph_sha256=_fingerprint(self.parent_graph),
                frontier={}, soups={})
            key = "B.AND|" + "a" * 64 + "|" + "b" * 64
            epoch["settled_matchups"] = {
                key: {"decision": "TITLE_DEFENDED", "winner_sha256": "a" * 64}}
            receipt["mentor_epoch"] = epoch
            receipt = _persist(root, receipt)
            grown, own, graph, changed = activate_numeric_grade(
                mx, root, receipt, self.previous, self.course,
                params, opt, self.parent_graph, reserve_gib=0.)
        self.assertEqual(changed["mentor_epoch"]["active_roles"], {})
        self.assertEqual(changed["mentor_epoch"]["active_grade_soups"], {})
        self.assertEqual(changed["mentor_epoch"]["settled_matchups"],
                         epoch["settled_matchups"])
        self.assertEqual(changed["mentor_epoch"]["championship_school_identity"],
                         changed["championship_school_identity"])
        self.assertEqual(int(own.state["step"].item()), int(opt.state["step"].item()))

    def test_staged_c_real_toy_updates_fixed_exam_and_restart_preserve_custody(self):
        import numpy as np
        from bilqis_mlx.diagnostics.audit import audit_saved_run
        mx, params, opt = self.toy()
        original_embedding = np.asarray(params["embedding.weight"]).copy()
        original_moments = np.asarray(opt.state["embedding.weight"]["m"]).copy()
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            root = Path(temp)
            pointer = _bundle_pointer(root,"initial",params,opt,self.parent_graph,reserve_gib=0.)
            receipt = _persist(root,self.receipt(self.graduated(pointer),pointer,params))
            params,opt,graph,receipt = activate_numeric_grade(mx,root,receipt,self.previous,
                self.course,params,opt,self.parent_graph,reserve_gib=0.)
            receipt, executable_release, _ = _ensure_executable_release(
                root, receipt, self.course, self.grade_a, SOURCE, graph)
            receipt = _migrate_championship_governance(
                root, receipt, self.course)
            self.assertEqual(receipt["curriculum_mode"],C_RELEASE)
            self.assertEqual(receipt["teacher"],self.teacher)
            self.assertEqual(int(opt.state["step"].item()),1)
            n = len(self.parent_graph["tokens"])
            np.testing.assert_array_equal(np.asarray(params["embedding.weight"])[:n],original_embedding)
            np.testing.assert_array_equal(np.asarray(opt.state["embedding.weight"]["m"])[:n],original_moments)
            self.assertFalse(np.asarray(opt.state["embedding.weight"]["m"])[n:].any())
            routine_cohorts = []
            for stage, plan in enumerate(PLANS):
                self.assertEqual(receipt["school"]["queue"],[plan.capability])
                receipt = _take_visit(mx,root,receipt,self.manifest,self.course,self.engine,
                    params,opt,graph,steps_per_visit=1,batch_size=6,reserve_gib=0.,source_root=SOURCE)
                # Oracle fixture validates graduation mechanics; these scores are not neural mastery.
                with patch('bilqis_mlx.learning.student_ops._predictions',side_effect=
                           lambda _m,_p,rows,*args: {r["id"]:r["gold"] for r in rows}):
                    receipt = _take_exam(mx,root,receipt,self.manifest,self.course,SOURCE,PARENT,
                                         params,opt,graph,reserve_gib=0.)
                swept = 0
                while receipt["school"]["stage"] == "PROMOTION_SWEEP":
                    swept += 1
                    self.assertLessEqual(swept, stage + 1)
                    receipt = _take_visit(
                        mx, root, receipt, self.manifest, self.course, self.engine,
                        params, opt, graph, steps_per_visit=1, batch_size=6,
                        reserve_gib=0., source_root=SOURCE)
                    with patch("bilqis_mlx.learning.student_ops._predictions", side_effect=
                               lambda _m, _p, rows, *args:
                               {row["id"]: row["gold"] for row in rows}):
                        receipt = _take_exam(
                            mx, root, receipt, self.manifest, self.course,
                            SOURCE, PARENT, params, opt, graph, reserve_gib=0.)
                self.assertEqual(swept, stage + 1)
                routine = receipt["last_exam"]["routine_cohort_sha256"]
                routine_cohorts.append(routine)
                self.assertEqual(len(set(routine_cohorts)), len(routine_cohorts))
                if "qualification_cohort" in receipt:
                    self.assertNotEqual(
                        receipt["qualification_cohort"]["cohort_sha256"], routine)
                self.assertEqual(len(receipt["last_exam"]["scores"]),13+stage)
                self.assertEqual(receipt["last_exam"]["learning_diagnostics"]["history_issue"],None)
                drifted = replace(
                    self.course, program_complete=not self.course.program_complete)
                admitted = {self.course.version: drifted}
                params,opt,graph,reloaded = _resume(
                    root,self.manifest,drifted,self.policy_sha,
                    grade_a_course=self.grade_a, source_root=SOURCE,
                    admitted_courses=admitted)
                self.assertEqual(reloaded,receipt)
                self.assertEqual(reloaded["factory_release_sha256"],
                                 executable_release.release_sha256)
                self.assertEqual(
                    reloaded["factory_admission_v2"]["factory_release_sha256"],
                    executable_release.release_sha256)
            self.assertEqual(receipt["school"]["active_grades"][receipt["school"]["grade_index"]],"A")
            self.assertEqual(receipt["school"]["revalidation_target_grade"],"C")
            self.assertEqual(len(set(routine_cohorts)), len(PLANS))
            expected_visits = len(PLANS) + sum(range(1, len(PLANS) + 1))
            self.assertEqual(int(opt.state["step"].item()), 1 + expected_visits)
            self.assertEqual(
                receipt["teacher"]["events"],
                self.teacher["events"] + expected_visits)
            report = audit_saved_run(root)
            self.assertEqual(report["verified_teacher_decision_count"], expected_visits)
