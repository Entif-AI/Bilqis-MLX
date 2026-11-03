"""Stable public cognitive_solver class and function identities."""
import pickle
from unittest import TestCase

from bilqis_mlx.runtime import cognitive_solver
from bilqis_mlx.runtime.tests.capability.solver_helpers import _fixture


class CognitiveSolverFacadeTests(TestCase):
    def test_public_records_keep_their_canonical_pickle_identity(self):
        _binding, generation, budget, _add, _ambiguous = _fixture()
        for value in (generation, budget):
            self.assertEqual(type(value).__module__, "bilqis_mlx.runtime.cognitive_solver")
            self.assertEqual(pickle.loads(pickle.dumps(value)), value)
        for name in ("GenerationBinding", "QualifiedComposition", "SolveBudget",
                     "NeuralRequest", "NeuralProposal", "SolveContext", "CapabilityResult"):
            record = getattr(cognitive_solver, name)
            self.assertIs(pickle.loads(pickle.dumps(record)), record)

    def test_public_solver_keeps_its_canonical_module(self):
        self.assertEqual(cognitive_solver.solve_task.__module__,
                         "bilqis_mlx.runtime.cognitive_solver")
