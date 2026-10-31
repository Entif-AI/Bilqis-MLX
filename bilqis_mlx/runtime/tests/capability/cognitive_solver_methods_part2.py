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
        def test_qualified_cached_composition_precedes_neural_and_ties_stably(self):
            binding, generation, budget, add, ambiguous = _fixture()
            cached = QualifiedComposition(
                goal=add,
                source_binding_digest=generation.source_binding_digest,
                rights_epoch=binding.frontier.rights_epoch,
                correction_generation=binding.frontier.correction_generation,
                qualification_receipt_sha256="a" * 64,
            )
            calls = []

            def neural(request):
                calls.append(request)
                raise AssertionError("exact cached route must preempt neural")

            context = SolveContext(
                binding, qualified_compositions=(cached,),
                qualification_verifier=lambda item: (
                    item.qualification_receipt_sha256 == "a" * 64),
                neural_proposer=neural)
            result = solve_task(ambiguous, context, generation, budget)
            self.assertEqual(result.route, RouteKind.CACHED_COMPOSITION)
            self.assertEqual(result.answer.value, 5)
            self.assertEqual(result.score, 1.0)
            self.assertEqual(calls, [])
            rejected = solve_task(
                ambiguous, SolveContext(
                    binding, qualified_compositions=(cached,),
                    qualification_verifier=lambda item: False),
                generation, budget)
            self.assertEqual(rejected.route, RouteKind.UNRESOLVED)

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

        def test_neural_foreign_source_binding_rejects_before_dag_execution(self):
            binding, generation, budget, add, ambiguous = _fixture()
            foreign = replace(
                add, source_visible_bindings=tuple(sorted((
                    *add.source_visible_bindings, "literal:source:foreign"))))

            def neural(request):
                return NeuralProposal(
                    foreign, request.source_binding_digest,
                    request.generation_digest,
                    request.unresolved_signature,
                    "b" * 64)

            result = solve_task(
                ambiguous, SolveContext(binding, neural_proposer=neural),
                generation, budget)
            self.assertEqual(result.route, RouteKind.UNRESOLVED)
            self.assertEqual(result.neural_calls, 1)
            self.assertEqual(result.fallback_reason,
                             "BAMF_C04_NEURAL_PROPOSAL_SCOPE_DRIFT")

        def test_invalid_neural_uses_verified_deterministic_fallback(self):
            binding, generation, budget, add, ambiguous = _fixture()
            fallback = QualifiedComposition(
                add, generation.source_binding_digest,
                binding.frontier.rights_epoch,
                binding.frontier.correction_generation,
                "a" * 64)
            result = solve_task(
                ambiguous, SolveContext(
                    binding,
                    qualification_verifier=lambda item: True,
                    neural_proposer=lambda request: "invalid neural payload",
                    deterministic_fallback=fallback),
                generation, budget)
            self.assertEqual(result.route, RouteKind.DETERMINISTIC_FALLBACK)
            self.assertEqual(result.answer.value, 5)
            self.assertEqual(result.score, 1.0)
            self.assertEqual(result.neural_calls, 1)
            self.assertEqual(result.fallback_reason,
                             "BAMF_C04_NEURAL_PROPOSAL_INVALID")

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
