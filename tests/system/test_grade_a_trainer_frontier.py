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

class GradeATrainerFrontierTests(unittest.TestCase):
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

            with (patch('bilqis_mlx.learning.student_ops._predictions', side_effect=predict),
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
            patch('bilqis_mlx.learning.student_ops._predictions',
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
        mixed, delivered = reserve_weakness_targets(chosen, priority)
        self.assertEqual(tuple(priority), delivered)
        self.assertEqual({p["id"] for p in priority} & {p["id"] for p in mixed},
                         {p["id"] for p in priority})
        self.assertEqual(sum(r["gold"] == "TRUE" for r in mixed), 8)
        full_class = [{"id": f"miss-all-{i}", "gold": "TRUE"} for i in range(8)]
        no_quarter_ceiling, delivered = reserve_weakness_targets(chosen, full_class)
        self.assertEqual(tuple(full_class), delivered)
        self.assertEqual({p["id"] for p in full_class} &
                         {p["id"] for p in no_quarter_ceiling},
                         {p["id"] for p in full_class})
