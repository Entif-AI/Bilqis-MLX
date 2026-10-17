"""Disposable staged C through real trainer functions, never operate/human-run."""
from contextlib import redirect_stdout
from dataclasses import asdict, replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.champions import Checkpoint
from bilqis_mlx.grade_a_trainer import (_bundle_pointer, _fingerprint, _persist,
    _resume, _state_from_json, _take_exam, _take_visit, prepare_source)
from bilqis_mlx.grade_transition import activate_numeric_grade
from bilqis_mlx.live_grade_a import live_course as a_course
from bilqis_mlx.live_grade_b import RELEASE as B_RELEASE, constructor_digest as b_digest, live_course as b_course
from bilqis_mlx.live_grade_c import PLANS, RELEASE as C_RELEASE, live_course, proposed_graph
from bilqis_mlx.school import Assessment, Score, assess, next_capability, start_new, visit
from bilqis_mlx.source import AUDITED_PARENT

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "bilqis-triplets-v16"
PARENT = SOURCE / "runs/primitive-consolidation-v16-triplets" / AUDITED_PARENT.basename
MANIFEST = ROOT / "docs/GRADE_A_CANDIDATE_MANIFEST_V2.json"


class GradeCTrainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, old, cls.engine, cls.policy_sha, cls.teacher, _ = prepare_source(SOURCE, PARENT, MANIFEST)
        cls.previous = b_course(a_course(old), SOURCE)
        from bilqis_mlx.pedagogical_parity import _source_stack
        _, _, _, _, cls.parent_graph, _ = _source_stack(SOURCE)
        cls.graph = proposed_graph(cls.parent_graph)
        cls.course = live_course(cls.previous, cls.graph, maximum=10)

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
        return school

    def receipt(self, school, pointer, params):
        from bilqis_mlx.grade_a_trainer import VERSION
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
                scores={c.id: {"correct":12,"total":12} for g in self.previous.grades for c in g.capabilities}))

    def test_c_requires_one_complete_cumulative_a_b_result_before_growth(self):
        mx, params, opt = self.toy()
        pointer = Checkpoint("a"*64,"bundles/inert",1,True)
        receipt = self.receipt(self.graduated(pointer), pointer, params)
        receipt["last_exam"]["scores"]["B.NOT"]["correct"] = 11
        with patch("bilqis_mlx.grade_transition.extend_mlx_student", side_effect=AssertionError("premature growth")):
            with self.assertRaisesRegex(ValueError,"CUMULATIVE_A_B"):
                activate_numeric_grade(mx, Path("/unused"), receipt, self.previous, self.course,
                    params,opt,self.parent_graph,reserve_gib=0.)

    def test_c_requires_repeated_selection_review_before_model_growth(self):
        mx, params, opt = self.toy()
        pointer = Checkpoint("a"*64,"bundles/inert",1,True)
        receipt = self.receipt(self.graduated(pointer), pointer, params)
        with patch("bilqis_mlx.grade_transition.extend_mlx_student",
                   side_effect=AssertionError("model growth happened")):
            with self.assertRaisesRegex(ValueError, "NEXT_GRADE_REVIEW_BLOCKED"):
                activate_numeric_grade(mx, Path("/unused"), receipt, self.previous,
                    self.course, params, opt, self.parent_graph, reserve_gib=0.)

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
            with patch("bilqis_mlx.grade_transition.expanded_graph",return_value=self.graph), \
                    patch("bilqis_mlx.next_grade_review.require_admission_review",
                          return_value={"status":"READY_FOR_INDEPENDENT_REVIEW"}):
                params,opt,graph,receipt = activate_numeric_grade(mx,root,receipt,self.previous,
                    self.course,params,opt,self.parent_graph,reserve_gib=0.)
            self.assertEqual(receipt["curriculum_mode"],C_RELEASE)
            self.assertEqual(receipt["teacher"],self.teacher)
            self.assertEqual(int(opt.state["step"].item()),1)
            n = len(self.parent_graph["tokens"])
            np.testing.assert_array_equal(np.asarray(params["embedding.weight"])[:n],original_embedding)
            np.testing.assert_array_equal(np.asarray(opt.state["embedding.weight"]["m"])[:n],original_moments)
            self.assertFalse(np.asarray(opt.state["embedding.weight"]["m"])[n:].any())
            fixed = None
            for stage, plan in enumerate(PLANS):
                self.assertEqual(receipt["school"]["queue"],[plan.capability])
                receipt = _take_visit(mx,root,receipt,self.manifest,self.course,self.engine,
                    params,opt,graph,steps_per_visit=1,batch_size=6,reserve_gib=0.,source_root=SOURCE)
                # Oracle fixture validates graduation mechanics; these scores are not neural mastery.
                with patch("bilqis_mlx.grade_a_trainer._predictions",side_effect=
                           lambda _m,_p,rows,*args: {r["id"]:r["gold"] for r in rows}):
                    receipt = _take_exam(mx,root,receipt,self.manifest,self.course,SOURCE,PARENT,
                                         params,opt,graph,reserve_gib=0.)
                full = receipt["qualification_cohort"]["cohort_sha256"]
                fixed = full if fixed is None else fixed
                self.assertEqual(full,fixed)
                self.assertEqual(len(receipt["last_exam"]["scores"]),13+stage)
                self.assertEqual(receipt["last_exam"]["learning_diagnostics"]["history_issue"],None)
                with patch("bilqis_mlx.live_grade_c.registry_graph",return_value=self.graph):
                    params,opt,graph,reloaded = _resume(root,self.manifest,self.course,self.policy_sha,
                        admitted_courses={self.course.version:self.course})
                self.assertEqual(reloaded,receipt)
            self.assertEqual(receipt["school"]["active_grades"][receipt["school"]["grade_index"]],"A")
            self.assertEqual(receipt["school"]["revalidation_target_grade"],"C")
            self.assertEqual(int(opt.state["step"].item()),8)
            self.assertEqual(receipt["teacher"]["events"],self.teacher["events"]+7)
            report = audit_saved_run(root)
            self.assertEqual(report["verified_teacher_decision_count"],7)
