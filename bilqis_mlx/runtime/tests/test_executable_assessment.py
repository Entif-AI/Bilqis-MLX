import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from bilqis_mlx.curriculum import BOOLEAN_OPERATORS
from bilqis_mlx.factory.assessment import assessment_scope_contract
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.tests.test_executable_consumers import _profile
from bilqis_mlx.factory.tests.test_executable_release import _boolean_answers
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_boolean_course
from bilqis_mlx.runtime.assessment import (
    _draw_executable_scope_cohort,
    _generalization_executable_cohort,
    _load_executable_cohort,
    _persist_executable_cohort,
    _promotion_executable_cohort,
    _routine_executable_cohort,
    load_championship_cohort,
)
from bilqis_mlx.runtime.admission import _persist_executable_factory_release
from bilqis_mlx.trainer import _verify_live_rubric_lineage


class ExecutableAssessmentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.course, self.registry = _synthetic_boolean_course()
        self.curriculum, self.bindings = from_legacy_course(self.course)
        self.answers = _boolean_answers()
        self.graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.false",
                "cogal.value.true",
                *(f"cogal.operator.{value}" for value in BOOLEAN_OPERATORS),
            ],
        }
        self.full = compile_executable_factory_release(
            self.curriculum, self.bindings, CurriculumProfile.full(),
            self.registry, self.answers, source_root=None, graph=self.graph,
            verification_seed=47, legacy_course=self.course)
        self.reduced = compile_executable_factory_release(
            self.curriculum, self.bindings, _profile(),
            self.registry, self.answers, source_root=None, graph=self.graph,
            verification_seed=47, legacy_course=self.course,
            predecessor=self.full)
        self.manifest = {"manifest_sha256": "c" * 64}
        self.a_scope = tuple(
            item.capability_id for item in self.full.execution_plan.capabilities
            if item.grade_id == "A")

    def draw(self, release, scope, seed=53):
        return _draw_executable_scope_cohort(
            None, self.graph, release, self.registry,
            capabilities=scope, seed=seed, legacy_course=self.course)

    def receipt(self):
        return {
            "run_id": "v2-assessment-fixture",
            "generation": 1,
            "qualification_cohort_v2": None,
            "burned_generalization_cohorts_v2": [],
        }

    def test_unrelated_profile_change_preserves_exact_a_cohort_identity(self):
        full, full_contract = self.draw(self.full, self.a_scope)
        reduced, reduced_contract = self.draw(
            self.reduced, reversed(self.a_scope))

        self.assertEqual(full_contract.rubric_sha256,
                         reduced_contract.rubric_sha256)
        self.assertEqual(full_contract.source_sha256,
                         reduced_contract.source_sha256)
        self.assertEqual(full.digest, reduced.digest)
        self.assertEqual(full.rows, reduced.rows)
        self.assertNotEqual(full_contract.factory_release_sha256,
                            reduced_contract.factory_release_sha256)

    def test_exact_scope_persists_and_cold_reads_with_separate_identities(self):
        cohort, contract = self.draw(
            self.reduced, (*self.a_scope, "B.AND", "B.IFF"))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = _persist_executable_cohort(
                root, self.manifest, contract, cohort)
            restored = _load_executable_cohort(
                root, self.manifest, self.reduced,
                contract.capabilities, pointer)

            self.assertEqual(restored, cohort)
            payload = json.loads((root / pointer["cohort_file"]).read_text())
            self.assertEqual(payload["rubric_sha256"], contract.rubric_sha256)
            self.assertEqual(payload["source_sha256"], contract.source_sha256)
            self.assertEqual(
                payload["factory_release_sha256"],
                self.reduced.release_sha256)
            self.assertNotEqual(
                payload["rubric_sha256"],
                payload["factory_release_sha256"])

    def test_recent_v2_exact_scope_exam_is_a_valid_live_rubric_authority(self):
        cohort, contract = self.draw(self.reduced, ("B.IDBOOLOPS",))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release_path = _persist_executable_factory_release(root, self.reduced)
            pointer = _persist_executable_cohort(root, self.manifest, contract, cohort)
            receipt = {
                "factory_release_sha256": self.reduced.release_sha256,
                "factory_release_file": release_path,
                "factory_admission_v2": {},
                "source_manifest_sha256": self.manifest["manifest_sha256"],
                "live_rubric_sha256": contract.rubric_sha256,
                "last_exam": {**pointer, "exam_rubric_sha256": contract.rubric_sha256},
            }
            program = SimpleNamespace(grades=(SimpleNamespace(
                assessment_sha256="f" * 64),))
            self.assertIsNone(_verify_live_rubric_lineage(root, receipt, program))
            with self.assertRaises(ValueError):
                _verify_live_rubric_lineage(root, {
                    **receipt, "last_exam": {**receipt["last_exam"],
                       "cohort_sha256": "0" * 64}}, program)
            with self.assertRaisesRegex(ValueError, "LIVE_RUBRIC_IDENTITY_DRIFT"):
                _verify_live_rubric_lineage(root, {
                    **receipt, "live_rubric_sha256": "e" * 64}, program)

    def test_v2_cohort_replays_as_championship_evidence_with_exact_rubric(self):
        cohort, contract = self.draw(self.reduced, self.a_scope)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = _persist_executable_cohort(
                root, self.manifest, contract, cohort)
            restored = load_championship_cohort(root, {
                "cohort_sha256": cohort.digest,
                "rubric_sha256": contract.rubric_sha256,
                "cohort_rubric_sha256": contract.rubric_sha256,
                "source_oracle_sha256": self.manifest["manifest_sha256"],
            })
        self.assertEqual(restored, cohort)

    def test_current_pointer_rejects_holistic_release_change_even_when_scope_matches(self):
        cohort, contract = self.draw(self.full, self.a_scope)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = _persist_executable_cohort(
                root, self.manifest, contract, cohort)
            with self.assertRaisesRegex(
                    ValueError, "FACTORY_EXECUTABLE_COHORT_RELEASE_DRIFT"):
                _load_executable_cohort(
                    root, self.manifest, self.reduced,
                    self.a_scope, pointer)

    def test_content_tamper_is_rejected(self):
        cohort, contract = self.draw(self.reduced, ("B.IDBOOLOPS",))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = _persist_executable_cohort(
                root, self.manifest, contract, cohort)
            path = root / pointer["cohort_file"]
            payload = json.loads(path.read_text())
            payload["rows"][0]["gold"] = (
                "IFF" if payload["rows"][0]["gold"] == "AND" else "AND")
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(
                    ValueError, "FACTORY_EXECUTABLE_COHORT_CONTENT_DRIFT"):
                _load_executable_cohort(
                    root, self.manifest, self.reduced,
                    ("B.IDBOOLOPS",), pointer)

    def test_routine_scope_is_fresh_at_each_boundary(self):
        receipt = self.receipt()
        scope = (*self.a_scope, "B.AND", "B.IFF")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, first_pointer = _routine_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=3,
                legacy_course=self.course)
            receipt["generation"] += 1
            second, second_pointer = _routine_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=4,
                legacy_course=self.course)
            self.assertNotEqual(first.digest, second.digest)
            self.assertNotEqual(
                first_pointer["cohort_sha256"],
                second_pointer["cohort_sha256"])
            self.assertEqual(first_pointer["policy"], "bilqis.grade-test.fresh-routine/v2")

    def test_promotion_scope_is_fixed_within_attempt_but_rotates_next_epoch(self):
        receipt = self.receipt()
        scope = (*self.a_scope, "B.AND", "B.IFF")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=7,
                legacy_course=self.course)
            receipt["qualification_cohort_v2"] = pointer
            receipt["generation"] += 10
            retry, retry_pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=7,
                legacy_course=self.course)
            self.assertEqual(retry.digest, first.digest)
            self.assertEqual(retry_pointer, pointer)

            second, second_pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=8,
                legacy_course=self.course)
            self.assertNotEqual(second.digest, first.digest)
            self.assertNotEqual(second_pointer, pointer)

    def test_generalization_is_fresh_from_promotion_and_burned_prior_attempt(self):
        receipt = self.receipt()
        scope = (*self.a_scope, "B.AND", "B.IFF")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, promotion_pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=11,
                legacy_course=self.course)
            first, first_pointer = _generalization_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=11,
                promotion_pointer=promotion_pointer,
                legacy_course=self.course)
            self.assertNotEqual(first.digest, promotion.digest)
            self.assertFalse(
                {row["id"] for row in first.rows} &
                {row["id"] for row in promotion.rows})

            receipt["burned_generalization_cohorts_v2"] = [first_pointer]
            receipt["generation"] += 1
            second, second_pointer = _generalization_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=11,
                promotion_pointer=promotion_pointer,
                legacy_course=self.course)
            self.assertNotEqual(second.digest, first.digest)
            self.assertNotEqual(second_pointer, first_pointer)
            self.assertNotEqual(
                {row["id"] for row in second.rows},
                {row["id"] for row in first.rows})

    def test_generalization_preserves_burned_cohort_from_prior_larger_scope(self):
        # A later grade's active scope may shrink after assessment scheduling.
        # Previously burned source evidence remains valid under its own signed
        # scope, not the newly scheduled assessment's narrower scope.
        receipt = self.receipt()
        current_scope = self.a_scope
        historical_scope = tuple(
            item.capability_id for item in self.reduced.execution_plan.capabilities)
        self.assertNotEqual(current_scope, historical_scope)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            historical, contract = self.draw(self.reduced, historical_scope, seed=72)
            burned_pointer = _persist_executable_cohort(
                root, self.manifest, contract, historical)
            promotion, promotion_pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=current_scope, assessment_epoch=12,
                legacy_course=self.course)
            receipt["burned_generalization_cohorts_v2"] = [burned_pointer]
            fresh, _ = _generalization_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=current_scope, assessment_epoch=12,
                promotion_pointer=promotion_pointer,
                legacy_course=self.course)
            self.assertNotEqual(fresh.digest, promotion.digest)
            self.assertNotEqual(fresh.digest, historical.digest)

    def test_generalization_verifies_burned_cohort_under_its_historical_release(self):
        receipt = self.receipt()
        current_scope = tuple(
            item.capability_id for item in self.reduced.execution_plan.capabilities)
        historical_scope = tuple(
            item.capability_id for item in self.full.execution_plan.capabilities)
        self.assertTrue(set(historical_scope) - set(current_scope))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _persist_executable_factory_release(root, self.full)
            _persist_executable_factory_release(root, self.reduced)
            historical, contract = self.draw(self.full, historical_scope, seed=73)
            burned_pointer = _persist_executable_cohort(
                root, self.manifest, contract, historical)
            promotion, promotion_pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=current_scope, assessment_epoch=13,
                legacy_course=self.course)
            receipt["burned_generalization_cohorts_v2"] = [burned_pointer]
            fresh, _ = _generalization_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=current_scope, assessment_epoch=13,
                promotion_pointer=promotion_pointer,
                legacy_course=self.course)
            self.assertNotEqual(fresh.digest, promotion.digest)
            self.assertNotEqual(fresh.digest, historical.digest)

    def test_fixed_frontier_reads_v2_cohort_without_using_schema_as_rubric(self):
        from bilqis_mlx.fixed_frontier import load_frontier_cohort
        cohort, contract = self.draw(self.full, self.a_scope)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pointer = _persist_executable_cohort(root, self.manifest, contract, cohort)
            self.assertEqual(load_frontier_cohort(root, pointer).digest, cohort.digest)

    def test_scheduler_accepts_verified_exact_scope_when_whole_later_grade_withheld(self):
        from dataclasses import replace
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.curriculum.scheduler import Assessment, Score, start_new, assess_withheld
        from bilqis_mlx.learning.champions import Checkpoint
        cohort, contract = self.draw(self.full, self.a_scope)
        program = schedule_program_from_executable_release(self.full)
        student = Checkpoint("a" * 64, "bundles/fixture", 10, True)
        school = replace(start_new(program, student), grade_index=1,
                         stage="ASSESS_MAIN", queue=(), champions={"A": student},
                         introduction_stage=max(0, len(program.grades[1].teaching_stages)-1))
        exam = Assessment(student.sha256, 10, program.digest(), contract.rubric_sha256,
                          {cap: Score(12, 12) for cap in self.a_scope}, "fixture")
        blocked = tuple(cap.id for cap in program.grades[1].capabilities)
        completed = assess_withheld(program, school, exam, blocked)
        self.assertEqual(completed.stage, "DEFERRED_STAGNATION")
        self.assertNotIn("B", completed.champions)

    def test_quarantine_after_exam_keeps_the_measured_rubric_scope(self):
        from dataclasses import replace
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.curriculum.scheduler import Assessment, Score, start_new, assess_withheld
        from bilqis_mlx.learning.champions import Checkpoint
        program = schedule_program_from_executable_release(self.full)
        student = Checkpoint("a" * 64, "bundles/fixture", 10, True)
        school = replace(start_new(program, student), grade_index=1,
                         stage="ASSESS_RECOVERY_2", queue=(),
                         first_recovery=("B.AND",), champions={"A": student},
                         introduction_stage=max(0, len(program.grades[1].teaching_stages)-1))
        measured_scope = tuple(item.capability_id
                               for item in self.full.execution_plan.capabilities)
        contract = assessment_scope_contract(self.full, measured_scope)
        blocked_after = ("B.IFF",)
        counts = {cap.id: cap.exam_item_count for grade in program.grades
                  for cap in grade.capabilities}
        filtered_scores = {cap: Score(counts[cap] - 1, counts[cap])
                           for cap in measured_scope if cap not in blocked_after}
        filtered = Assessment(student.sha256, student.optimizer_step,
                              program.digest(), contract.rubric_sha256,
                              filtered_scores, "measured-before-quarantine")
        next_state = assess_withheld(
            program, school, filtered, blocked_after,
            rubric_capabilities=measured_scope)
        self.assertNotIn("B", next_state.champions)
        self.assertNotEqual(next_state.stage, "AWAITING_NEXT_GRADE")
        with self.assertRaisesRegex(ValueError, "ASSESSMENT_NOT_GRADE_SEALED_RUBRIC"):
            assess_withheld(program, school, replace(filtered, rubric_digest="f" * 64),
                            blocked_after, rubric_capabilities=measured_scope)


if __name__ == "__main__":
    unittest.main()
