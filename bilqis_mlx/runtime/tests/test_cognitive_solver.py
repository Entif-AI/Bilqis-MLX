"""C04.1 source-qualified exact/cache/neural route selection witnesses."""
from __future__ import annotations

from dataclasses import replace
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

        with self.assertRaises(BilqisError) as caught:
            solve_task(
                ambiguous, SolveContext(binding, neural_proposer=neural),
                generation, budget)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C04_NEURAL_PROPOSAL_SCOPE_DRIFT")

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
