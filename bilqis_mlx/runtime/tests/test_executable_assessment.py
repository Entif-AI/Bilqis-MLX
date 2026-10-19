import json
from pathlib import Path
import tempfile
import unittest

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
)


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


if __name__ == "__main__":
    unittest.main()
