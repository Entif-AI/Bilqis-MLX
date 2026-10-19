import unittest

from bilqis_mlx.curriculum import BOOLEAN_OPERATORS
from bilqis_mlx.factory.assessment import assessment_scope_contract
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.tests.test_executable_consumers import _profile
from bilqis_mlx.factory.tests.test_executable_release import _boolean_answers
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_boolean_course


class AssessmentScopeContractTests(unittest.TestCase):
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
            verification_seed=43, legacy_course=self.course)
        self.reduced = compile_executable_factory_release(
            self.curriculum, self.bindings, _profile(),
            self.registry, self.answers, source_root=None, graph=self.graph,
            verification_seed=43, legacy_course=self.course,
            predecessor=self.full)

    def test_unrelated_b_profile_change_preserves_a_scope_rubric_and_source(self):
        a_scope = tuple(
            item.capability_id for item in self.full.execution_plan.capabilities
            if item.grade_id == "A")
        before = assessment_scope_contract(self.full, a_scope)
        after = assessment_scope_contract(self.reduced, reversed(a_scope))

        self.assertEqual(before.capabilities, a_scope)
        self.assertEqual(after.capabilities, a_scope)
        self.assertEqual(before.rubric_sha256, after.rubric_sha256)
        self.assertEqual(before.source_sha256, after.source_sha256)
        self.assertNotEqual(
            before.factory_release_sha256, after.factory_release_sha256)

    def test_exact_partial_b_scope_is_independent_of_disabled_unscored_capabilities(self):
        a_scope = tuple(
            item.capability_id for item in self.full.execution_plan.capabilities
            if item.grade_id == "A")
        scope = (*a_scope, "B.AND", "B.IFF")
        before = assessment_scope_contract(self.full, scope)
        after = assessment_scope_contract(self.reduced, scope)

        self.assertEqual(before.rubric_sha256, after.rubric_sha256)
        self.assertEqual(before.source_sha256, after.source_sha256)

    def test_narrowed_idboolops_changes_exact_rubric_and_source_identity(self):
        a_scope = tuple(
            item.capability_id for item in self.full.execution_plan.capabilities
            if item.grade_id == "A")
        scope = (*a_scope, "B.IDBOOLOPS")
        before = assessment_scope_contract(self.full, scope)
        after = assessment_scope_contract(self.reduced, scope)

        self.assertNotEqual(before.rubric_sha256, after.rubric_sha256)
        self.assertNotEqual(before.source_sha256, after.source_sha256)

    def test_unknown_or_duplicate_scope_fails_closed(self):
        with self.assertRaisesRegex(
                ValueError, "FACTORY_ASSESSMENT_SCOPE_UNKNOWN_CAPABILITY"):
            assessment_scope_contract(self.reduced, ("Z.UNKNOWN",))
        with self.assertRaisesRegex(
                ValueError, "FACTORY_ASSESSMENT_SCOPE_DUPLICATE_CAPABILITY"):
            assessment_scope_contract(
                self.reduced, ("B.AND", "B.AND"))


if __name__ == "__main__":
    unittest.main()
