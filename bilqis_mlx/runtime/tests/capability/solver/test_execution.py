"""Public C04 solve boundary rejects invalid arguments and foreign source identity."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.cognitive_solver import SolveContext, solve_task
from bilqis_mlx.runtime.tests.capability.solver_helpers import _fixture


class SolveBoundaryTests(unittest.TestCase):
    def test_invalid_task_rejects_at_public_argument_boundary(self):
        binding, generation, budget, _add, _ambiguous = _fixture()
        with self.assertRaises(BilqisError) as caught:
            solve_task(None, SolveContext(binding), generation, budget)
        self.assertEqual(caught.exception.context["reason"], "BAMF_C04_SOLVE_ARGUMENT_INVALID")

    def test_foreign_source_generation_rejects_before_route_execution(self):
        binding, generation, budget, add, _ambiguous = _fixture()
        foreign = replace(generation, source_binding_digest="f" * 64)
        with self.assertRaises(BilqisError) as caught:
            solve_task(add, SolveContext(binding), foreign, budget)
        self.assertEqual(caught.exception.context["reason"], "BAMF_C04_SOLVE_SOURCE_DRIFT")
