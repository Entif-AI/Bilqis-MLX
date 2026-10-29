"""C04.1 source-qualified exact/cache/neural route selection witnesses."""
from __future__ import annotations

from dataclasses import replace
import ast
from pathlib import Path
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
from bilqis_mlx.semantics.tests.test_cognitive_dag import (
    _goal, _literal, _program,
)
from bilqis_mlx.semantics.tests.test_cognitive_operators import (
    RELEASE, SCOPE, _case,
)


def _fixture():
    binding, values = _case(("Number", 2), ("Number", 3))
    add = _goal(_program(DAGNode(
        "answer", "ADD", (_literal(values[0]), _literal(values[1])),
        "Number", SCOPE)), binding)
    ambiguous = _goal(_program(DAGNode(
        "answer", None, (_literal(values[0]), _literal(values[1])),
        "Number", SCOPE, candidate_operator_ids=("ADD", "SUB"))), binding)
    generation = GenerationBinding(
        generation_digest="f" * 64,
        semantic_release=RELEASE,
        source_binding_digest=contract_digest(binding),
    )
    budget = SolveBudget(DAGBudget())
    return binding, generation, budget, add, ambiguous


class CognitiveSolverTests(unittest.TestCase):
    def test_replay_receipt_records_only_bound_operations_costs_and_outcome(self):
        binding, generation, budget, add, _ = _fixture()
        solved = solve_task(
            add, SolveContext(binding), generation, budget)
        receipt = solved.replay_receipt
        self.assertEqual(receipt.route, RouteKind.EXACT)
        self.assertEqual(receipt.goal_id, add.goal_id)
        self.assertEqual(receipt.operation_count, 1)
        self.assertEqual(receipt.neural_calls, 0)
        self.assertEqual(receipt.local_refinement_calls, 0)
        self.assertEqual(receipt.selected_bindings[0][2], "ADD")
        self.assertEqual(receipt.outcome_digest,
                         contract_digest(solved.answer))
        self.assertEqual(receipt.visibility, "INTERNAL_ONLY")
        self.assertNotIn("raw_private_input", receipt.canonical_json)
        with self.assertRaises(BilqisError):
            replace(receipt, outcome_digest="0" * 64)
        runtime = Path(__file__).resolve().parents[1]
        for name in (
                "cognitive_solver.py", "cognitive_replay.py",
                "operator_registry.py"):
            tree = ast.parse((runtime / name).read_text())
            imports = [
                alias.name for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names
            ]
            self.assertFalse(any(
                token in imported.lower()
                for imported in imports
                for token in ("gold", "assessment", "evaluator")))

    def test_applicable_exact_operator_wins_with_full_score_no_neural(self):
        binding, generation, budget, add, _ = _fixture()
        result = solve_task(
            add, SolveContext(binding), generation, budget)
        self.assertEqual(result.route, RouteKind.EXACT)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.answer.type_name, "Number")
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.neural_calls, 0)

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

    def test_unresolved_without_neural_preserves_typed_state_and_no_score(self):
        binding, generation, budget, _, ambiguous = _fixture()
        result = solve_task(
            ambiguous, SolveContext(binding), generation, budget)
        self.assertEqual(result.route, RouteKind.UNRESOLVED)
        self.assertEqual(result.answer.state, ValueState.UNRESOLVED)
        self.assertIsNone(result.score)
        self.assertEqual(result.neural_calls, 0)


if __name__ == "__main__":
    unittest.main()
