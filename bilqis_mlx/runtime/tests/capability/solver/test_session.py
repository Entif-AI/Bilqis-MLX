"""C04.1 source-qualified exact/cache/neural route selection witnesses."""
from __future__ import annotations

from dataclasses import replace
import ast
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.cognitive_solver import (
    GenerationBinding, NeuralProposal, QualifiedComposition,
    RouteKind, SolveBudget, SolveContext, solve_task,
)
from bilqis_mlx.semantics.cognitive_dag import (
    DAGBudget, DAGNode, DAGOperand, RefKind,
)
from bilqis_mlx.semantics.cognitive_operators import ValueState
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.memo import PureOperationMemo
from bilqis_mlx.semantics.tests.test_cognitive_dag import (
    _goal, _literal, _program,
)
from bilqis_mlx.semantics.tests.test_cognitive_operators import (
    RELEASE, SCOPE, _case,
)

from bilqis_mlx.runtime.tests.capability.solver_helpers import _fixture

class CognitiveSolverTests(unittest.TestCase):
    def test_replay_reserves_unknown_executor_cost_without_inventing_work(self):
        binding, generation, budget, add, ambiguous = _fixture()
        from bilqis_mlx.runtime import cognitive_solver
        execute = cognitive_solver.execute_dag
        calls = 0

        def interrupted(goal, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                return execute(None, *args, **kwargs)
            return execute(goal, *args, **kwargs)

        def proposal(request):
            return NeuralProposal(add, request.source_binding_digest,
                                  request.generation_digest,
                                  request.unresolved_signature, "b" * 64)

        with patch.object(cognitive_solver, "execute_dag", interrupted):
            result = solve_task(
                ambiguous, SolveContext(binding, neural_proposer=proposal),
                generation, budget)
        self.assertEqual(result.route, RouteKind.UNRESOLVED)
        self.assertEqual(result.replay_record()["costs"]["pure_operations"], 0)
        self.assertEqual(result.replay_record()["costs"]["reserved_operations"], 64)


    def test_one_backbone_plus_bounded_local_refinement(self):
        binding, generation, _, add, ambiguous = _fixture()
        budget = SolveBudget(DAGBudget(), max_local_refinements=1)
        calls = []

        def refine(request, attempt):
            calls.append(attempt)
            return NeuralProposal(
                add, request.source_binding_digest,
                request.generation_digest,
                request.unresolved_signature,
                "b" * 64)

        result = solve_task(
            ambiguous, SolveContext(
                binding,
                neural_proposer=lambda request: None,
                local_refiner=refine),
            generation, budget)
        self.assertEqual(result.route, RouteKind.NEURAL_COMPOSITION)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.neural_calls, 1)
        self.assertEqual(result.local_refinement_calls, 1)
        self.assertEqual(calls, [1])
        replay = result.replay_record()
        self.assertEqual(replay["route"], "NEURAL_COMPOSITION")
        self.assertEqual(replay["costs"]["backbone_calls"], 1)
        self.assertEqual(replay["costs"]["local_refinements"], 1)
        self.assertEqual(replay["costs"]["pure_operations"], 1)
        self.assertIsNone(replay["costs"]["decoder_decisions"])


    def test_refinement_cannot_restart_consumed_operation_budget(self):
        binding, generation, _, add, ambiguous = _fixture()
        limit = DAGBudget(max_operations=1)
        add, ambiguous = (replace(goal, budget=limit)
                          for goal in (add, ambiguous))
        sub = replace(add, allowed_operator_ids=ambiguous.allowed_operator_ids,
                      expression_or_holes=_program(replace(
            add.expression_or_holes.nodes[0], operator_id="SUB")))

        def proposal(goal, request):
            return NeuralProposal(goal, request.source_binding_digest,
                                  request.generation_digest,
                                  request.unresolved_signature, "b" * 64)

        result = solve_task(
            ambiguous, SolveContext(
                binding, neural_proposer=lambda request: proposal(sub, request),
                local_refiner=lambda request, attempt: proposal(add, request)),
            generation, SolveBudget(limit, max_local_refinements=1))
        self.assertEqual(result.route, RouteKind.UNRESOLVED)
        self.assertEqual(sum(r.operation_count for r in result.dag_receipts), 1)


