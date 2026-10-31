"""Structural test shard from test_cognitive_solver.py; assertions preserved."""
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
from bilqis_mlx.runtime.tests.capability.test_cognitive_solver_helpers import (_fixture)

class CognitiveSolverTests(unittest.TestCase):
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

        def test_neural_cannot_rewrite_fixed_operands(self):
            binding, generation, budget, add, ambiguous = _fixture()
            node = add.expression_or_holes.nodes[0]
            changed = replace(add, expression_or_holes=_program(replace(
                node, operands=(node.operands[0], node.operands[0]))))
            result = solve_task(
                ambiguous, SolveContext(binding, neural_proposer=lambda request:
                    NeuralProposal(changed, request.source_binding_digest,
                                   request.generation_digest,
                                   request.unresolved_signature, "b" * 64)),
                generation, budget)
            self.assertEqual(result.route, RouteKind.UNRESOLVED)
            self.assertEqual(sum(r.operation_count for r in result.dag_receipts), 0)

        def test_qualified_cache_and_fallback_cannot_change_fixed_question(self):
            binding, generation, budget, add, ambiguous = _fixture()
            node = add.expression_or_holes.nodes[0]
            changed = replace(add, expression_or_holes=_program(replace(
                node, operands=(node.operands[0], node.operands[0]))))
            cached = QualifiedComposition(
                changed, generation.source_binding_digest,
                binding.frontier.rights_epoch,
                binding.frontier.correction_generation, "a" * 64)
            for context in (
                    SolveContext(binding, qualified_compositions=(cached,),
                                 qualification_verifier=lambda item: True),
                    SolveContext(binding, deterministic_fallback=cached,
                                 qualification_verifier=lambda item: True)):
                result = solve_task(ambiguous, context, generation, budget)
                self.assertEqual(result.route, RouteKind.UNRESOLVED)
                self.assertEqual(sum(r.operation_count for r in result.dag_receipts), 0)

        def test_decoder_construction_errors_use_qualified_fallback(self):
            binding, generation, budget, add, ambiguous = _fixture()
            fallback = QualifiedComposition(
                add, generation.source_binding_digest,
                binding.frontier.rights_epoch,
                binding.frontier.correction_generation, "a" * 64)
            for malformed_digest in (False, True):
                with self.subTest(malformed_digest=malformed_digest):
                    def malformed(request):
                        if malformed_digest:
                            return NeuralProposal(
                                add, request.source_binding_digest, "bad",
                                request.unresolved_signature, "b" * 64)
                        raise ValueError("malformed decoder payload")
                    result = solve_task(
                        ambiguous, SolveContext(
                            binding, qualification_verifier=lambda item: True,
                            neural_proposer=malformed,
                            deterministic_fallback=fallback), generation, budget)
                    self.assertEqual(result.route, RouteKind.DETERMINISTIC_FALLBACK)
                    self.assertEqual(result.answer.value, 5)
                    self.assertEqual(result.neural_calls, 1)

        def test_unresolved_without_neural_preserves_typed_state_and_no_score(self):
            binding, generation, budget, _, ambiguous = _fixture()
            result = solve_task(
                ambiguous, SolveContext(binding), generation, budget)
            self.assertEqual(result.route, RouteKind.UNRESOLVED)
            self.assertEqual(result.answer.state, ValueState.UNRESOLVED)
            self.assertIsNone(result.score)
            self.assertEqual(result.neural_calls, 0)
