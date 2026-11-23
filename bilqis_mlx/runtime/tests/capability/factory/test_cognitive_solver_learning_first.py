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

from bilqis_mlx.runtime.tests.capability.factory.solver_helpers import _fixture
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY, _event, _result
from bilqis_mlx.runtime._atlas_owner_ingress import apply_solve_context_correction
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
import bilqis_mlx.runtime.cognitive_solver as cognitive_solver_module
import bilqis_mlx.semantics._cognitive_dag.execution as dag_execution_module

class CognitiveSolverTests(unittest.TestCase):
    def test_learning_first_prebound_source_identity_avoids_binding_rehash(self):
        binding, generation, budget, add, _ = _fixture()
        real_solver_digest = cognitive_solver_module.contract_digest
        real_dag_digest = dag_execution_module.contract_digest

        def solver_digest(value):
            if value is binding:
                raise AssertionError("learning-first solver rehashed source binding")
            return real_solver_digest(value)

        def dag_digest(value):
            if value is binding:
                raise AssertionError("learning-first DAG rehashed source binding")
            return real_dag_digest(value)

        with (
                evidence_mode(strict=False),
                patch.object(cognitive_solver_module, "contract_digest", side_effect=solver_digest),
                patch.object(dag_execution_module, "contract_digest", side_effect=dag_digest)):
            result = solve_task(
                add, SolveContext(
                    binding, source_binding_digest=generation.source_binding_digest),
                generation, budget)
        self.assertEqual(result.answer.value, 5)

    def test_strict_prebound_source_identity_is_reverified(self):
        binding, generation, budget, add, _ = _fixture()
        with evidence_mode(strict=True):
            with self.assertRaises(Exception):
                solve_task(
                    add, SolveContext(binding, source_binding_digest="0" * 64),
                    generation, budget)

    def test_applicable_exact_operator_wins_with_full_score_no_neural(self):
        binding, generation, budget, add, _ = _fixture()
        result = solve_task(
            add, SolveContext(binding), generation, budget)
        self.assertEqual(result.route, RouteKind.EXACT)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.answer.type_name, "Number")
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.neural_calls, 0)




    def test_neural_proposes_only_a_source_bound_dag_for_unresolved_part(self):
        binding, generation, budget, add, ambiguous = _fixture()
        calls = []

        def neural(request):
            calls.append(request)
            self.assertEqual(request.generation_digest,
                             generation.generation_digest)
            self.assertFalse(hasattr(request, "raw_source_values"))
            return NeuralProposal(
                add, request.source_binding_digest,
                request.generation_digest,
                request.unresolved_signature,
                "b" * 64)

        result = solve_task(
            ambiguous, SolveContext(binding, neural_proposer=neural),
            generation, budget)
        self.assertEqual(result.route, RouteKind.NEURAL_COMPOSITION)
        self.assertEqual(result.answer.value, 5)
        self.assertIsNone(result.score)
        self.assertEqual(result.neural_calls, 1)
        self.assertEqual(len(calls), 1)

    def test_learning_first_neural_result_skips_ephemeral_composition_retention(self):
        binding, generation, budget, add, ambiguous = _fixture()

        def neural(request):
            return NeuralProposal(
                add, request.source_binding_digest,
                request.generation_digest,
                request.unresolved_signature,
                "b" * 64)

        context = SolveContext(
            binding,
            source_binding_digest=generation.source_binding_digest,
            neural_proposer=neural,
            retain_validated_compositions=False,
        )
        with patch.object(
                context.operator_composition_artifact_owner, "remember",
                side_effect=AssertionError(
                    "learning-first retained ephemeral solver composition")):
            result = solve_task(ambiguous, context, generation, budget)

        self.assertEqual(result.route, RouteKind.NEURAL_COMPOSITION)

    def test_learning_first_reuses_prevalidated_exact_result_before_neural_proposal(self):
        binding, generation, budget, add, ambiguous = _fixture()
        preflight = dag_execution_module.execute_dag(
            ambiguous, binding,
            source_binding_digest=generation.source_binding_digest)

        def neural(request):
            return NeuralProposal(
                add, request.source_binding_digest,
                request.generation_digest,
                request.unresolved_signature,
                "b" * 64)

        context = SolveContext(
            binding,
            source_binding_digest=generation.source_binding_digest,
            neural_proposer=neural,
            retain_validated_compositions=False,
            prevalidated_exact_goal=ambiguous,
            prevalidated_exact_result=preflight,
        )
        with (
            evidence_mode(strict=False),
            patch.object(
                cognitive_solver_module, "execute_dag",
                wraps=cognitive_solver_module.execute_dag) as execute,
        ):
            result = solve_task(ambiguous, context, generation, budget)

        self.assertEqual(execute.call_count, 1)
        self.assertEqual(result.route, RouteKind.NEURAL_COMPOSITION)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.dag_receipts[0], preflight.receipt)
        self.assertEqual(len(result.dag_receipts), 2)

    def test_strict_mode_replays_exact_result_even_when_prevalidated_result_exists(self):
        binding, generation, budget, add, ambiguous = _fixture()
        preflight = dag_execution_module.execute_dag(
            ambiguous, binding,
            source_binding_digest=generation.source_binding_digest)

        def neural(request):
            return NeuralProposal(
                add, request.source_binding_digest,
                request.generation_digest,
                request.unresolved_signature,
                "b" * 64)

        context = SolveContext(
            binding,
            source_binding_digest=generation.source_binding_digest,
            neural_proposer=neural,
            prevalidated_exact_goal=ambiguous,
            prevalidated_exact_result=preflight,
        )
        with (
            evidence_mode(strict=True),
            patch.object(
                cognitive_solver_module, "execute_dag",
                wraps=cognitive_solver_module.execute_dag) as execute,
        ):
            result = solve_task(ambiguous, context, generation, budget)

        self.assertEqual(execute.call_count, 2)
        self.assertEqual(result.route, RouteKind.NEURAL_COMPOSITION)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.neural_calls, 1)
