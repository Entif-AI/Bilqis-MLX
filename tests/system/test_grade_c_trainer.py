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
from bilqis_mlx.runtime.exam_execution import _measure_debt_admission_boundary
from bilqis_mlx.trainer import (_bundle_pointer, _fingerprint, _persist,
    _ensure_executable_release, _migrate_championship_governance, _resume,
    _state_from_json, _take_exam, _take_visit, prepare_source)
from bilqis_mlx.live_grade_a import live_course as a_course
from bilqis_mlx.live_grade_b import RELEASE as B_RELEASE, constructor_digest as b_digest, live_course as b_course
from bilqis_mlx.live_grade_c import PLANS, RELEASE as C_RELEASE, live_course, prepare_course
from bilqis_mlx.curriculum.scheduler import Assessment, Score, assess, next_capability, start_new, visit
from bilqis_mlx.source import AUDITED_PARENT

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "vendor" / "legacy-v16"
PARENT = SOURCE / "runs/primitive-consolidation-v16-triplets" / AUDITED_PARENT.basename
MANIFEST = ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


class GradeTransitionCompatibilityDisposableTests(unittest.TestCase):
    """Exercise historical transition contracts without the archived checkpoint."""

    @classmethod
    def setUpClass(cls):
        from bilqis_mlx.compatibility import historical_teacher_policy as policy
        from bilqis_mlx.live_grade_c import registry_graph
        from bilqis_mlx.semantics.abi import HISTORICAL_PREFIX_SIZE

        cls.manifest = json.loads(MANIFEST.read_text())
        cls.grade_a = a_course(accepted_grade_a(cls.manifest))
        cls.previous = b_course(cls.grade_a, SOURCE)
        registered = registry_graph()
        tokens = registered["tokens"][:HISTORICAL_PREFIX_SIZE]
        cls.parent_graph = {**registered, "tokens": tokens,
            "nodes": registered["nodes"][:HISTORICAL_PREFIX_SIZE],
            "row_contract_sha256": {name: registered["row_contract_sha256"][name]
                                    for name in tokens}}
        cls.course, cls.graph = prepare_course(cls.previous, maximum=10)
        strategy = dict(old=4, preview=0, depth=1, contrast=0.0, lr=0.00013, distill=0.0)
        key = policy._policy_key(strategy)
        cls.teacher = dict(strategies={key: strategy}, global_stats={key: policy._stats()},
                           grade_stats={}, events=0, mutations=0)
        cls.policy_sha = _fingerprint({
            "fixture_only": "grade-transition-compatibility/v1", "teacher": cls.teacher})

    def setUp(self):
        from copy import deepcopy
        self.fixture = GradeCTrainerTests()
        for name in ("manifest", "grade_a", "previous", "parent_graph", "course",
                     "graph", "teacher", "policy_sha"):
            setattr(self.fixture, name, deepcopy(getattr(self, name)))

    def test_historical_compatibility_has_no_migration_or_activation(self):
        import bilqis_mlx.compatibility.grade_transition as historical
        import bilqis_mlx.compatibility.resume_migration as inspection
        self.assertFalse(hasattr(historical, "activate_numeric_grade"))
        self.assertFalse(hasattr(inspection, "migrate_historical_grade_a"))
        self.assertTrue(callable(inspection.inspect_historical_run))

    def test_current_module_exposes_no_transition_or_readiness(self):
        import bilqis_mlx.grade_transition as current
        self.assertFalse(hasattr(current, "activate_numeric_grade"))
        self.assertFalse(hasattr(current, "next_grade_readiness"))


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
