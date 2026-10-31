"""Real default-program execution must preserve the selected capability meaning."""
from unittest import TestCase, skipUnless

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.generation import execute_release_family_program
from bilqis_mlx.factory.skos_curriculum.curriculum import LearnedFrontier
from bilqis_mlx.factory.skos_curriculum.registry import default_family_program_registry
from bilqis_mlx.semantics.cognitive_operators import TypedValue
from bilqis_mlx.factory.skos_curriculum.programs.tests.real_fixtures import (
    ARTIFACT, selection, full_boolean_release, formal_case,
)


@skipUnless(ARTIFACT, "real pinned A01 artifact not mounted")
class FormalProgramExecutionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release, cls.sources = full_boolean_release()
        cls.atlas = selection()

    def execute(self, semantic_id, operator, operands, answer):
        binding, inputs = formal_case(operator, *operands)
        return execute_release_family_program(
            self.release, self.sources, default_family_program_registry(),
            self.atlas, LearnedFrontier(self.atlas.release_sha256), "B.AND",
            construct_args=(self.atlas, semantic_id, inputs, binding),
            check_args=(TypedValue(answer[0], answer[1], self.atlas.release_sha256),
                        self.atlas, binding))

    def test_bound_boolean_and_runs_its_exact_pinned_semantics(self):
        result = self.execute("legacy:cogal.operator.AND", "BOOL_AND",
                              (("Boolean", True), ("Boolean", False)), ("Boolean", False))
        self.assertEqual((result.semantic_id, result.operator_id, result.positive.value),
                         ("legacy:cogal.operator.AND", "BOOL_AND", False))

    def test_boolean_capability_cannot_execute_numeric_successor(self):
        with self.assertRaises(BilqisError):
            self.execute("bilqis.numeric/v1:school.op.SUCC", "SUCC",
                         (("Number", 2),), ("Number", 3))

    def test_boolean_capability_cannot_execute_another_boolean_operator(self):
        with self.assertRaises(BilqisError):
            self.execute("legacy:cogal.operator.NOT", "BOOL_NOT",
                         (("Boolean", True),), ("Boolean", False))
