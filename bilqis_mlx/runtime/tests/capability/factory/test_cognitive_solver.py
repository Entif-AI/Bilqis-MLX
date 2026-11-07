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
from bilqis_mlx.runtime.atlas_revalidation import apply_solve_context_correction

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
            generation_digest=generation.generation_digest,
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

    def test_cached_composition_is_bound_to_its_producing_generation(self):
        binding, generation, budget, add, ambiguous = _fixture()
        cached = QualifiedComposition(
            goal=add,
            source_binding_digest=generation.source_binding_digest,
            generation_digest=generation.generation_digest,
            rights_epoch=binding.frontier.rights_epoch,
            correction_generation=binding.frontier.correction_generation,
            qualification_receipt_sha256="a" * 64,
        )
        accepted = solve_task(
            ambiguous,
            SolveContext(
                binding, qualified_compositions=(cached,),
                qualification_verifier=lambda item: True),
            generation, budget)
        self.assertEqual(accepted.route, RouteKind.CACHED_COMPOSITION)

        later = replace(generation, generation_digest="e" * 64)
        rejected = solve_task(
            ambiguous,
            SolveContext(
                binding, qualified_compositions=(cached,),
                qualification_verifier=lambda item: True),
            later, budget)
        self.assertEqual(rejected.route, RouteKind.UNRESOLVED)

    def test_correction_hold_blocks_real_cached_composition_before_execution(self):
        binding, generation, budget, add, ambiguous = _fixture()
        cached = QualifiedComposition(
            add, generation.source_binding_digest,
            generation.generation_digest,
            binding.frontier.rights_epoch,
            binding.frontier.correction_generation, "a" * 64)
        context = SolveContext(
            binding, qualified_compositions=(cached,),
            qualification_verifier=lambda item: True)
        owner = context.operator_composition_artifact_owner
        node = owner.node_for(cached)
        source = next(ref for ref in node.immediate_dependencies
                      if ref.kind.value == "SOURCE")
        event = _event(source)
        self.assertTrue(apply_solve_context_correction(
            context, event, AUTHORITY))
        with self.assertRaises(BilqisError) as caught:
            solve_task(ambiguous, context, generation, budget)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_ARTIFACT_HELD")
        progress = owner.advance(
            _result(node, digest=node.content_digest, correction=event), AUTHORITY)
        self.assertEqual(progress.queue.held_artifact_ids, ())
        result = solve_task(ambiguous, context, generation, budget)
        self.assertEqual(result.route, RouteKind.CACHED_COMPOSITION)

        owner.apply_correction(event, AUTHORITY)
        node = owner.node_for(cached)
        owner.advance(
            _result(node, digest=node.content_digest, eligible=False,
                    correction=event), AUTHORITY)
        replacement = QualifiedComposition(
            add, generation.source_binding_digest,
            generation.generation_digest,
            binding.frontier.rights_epoch,
            binding.frontier.correction_generation, "b" * 64)
        owner.remember(replacement, binding)
        self.assertFalse(owner.node_for(cached).eligible)
        with self.assertRaises(BilqisError):
            owner.require(cached, binding)

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

    def test_successful_neural_composition_materializes_into_retained_owner(self):
        binding, generation, budget, add, ambiguous = _fixture()
        calls = []

        def neural(request):
            calls.append(request)
            return NeuralProposal(
                add, request.source_binding_digest,
                request.generation_digest,
                request.unresolved_signature,
                "c" * 64)

        context = SolveContext(binding, neural_proposer=neural)
        first = solve_task(ambiguous, context, generation, budget)
        self.assertEqual(first.route, RouteKind.NEURAL_COMPOSITION)
        self.assertEqual(len(calls), 1)
        retained = context.operator_composition_artifact_owner.compositions
        self.assertEqual(len(retained), 1)
        self.assertTrue(
            context.operator_composition_artifact_owner.is_materialized(retained[0]))

        second = solve_task(ambiguous, context, generation, budget)
        self.assertEqual(second.route, RouteKind.CACHED_COMPOSITION)
        self.assertEqual(len(calls), 1)

        owner = context.operator_composition_artifact_owner
        node = owner.node_for(retained[0])
        dependency = next(
            ref for ref in node.immediate_dependencies
            if ref.kind.value == "SOURCE")
        event = _event(dependency)
        self.assertTrue(apply_solve_context_correction(
            context, event, AUTHORITY))
        with self.assertRaises(BilqisError) as caught:
            solve_task(ambiguous, context, generation, budget)
        self.assertEqual(
            caught.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")

    def test_active_correction_holds_newly_materialized_affected_composition(self):
        binding, generation, _budget, add, _ambiguous = _fixture()
        cached = QualifiedComposition(
            add, generation.source_binding_digest, generation.generation_digest,
            binding.frontier.rights_epoch,
            binding.frontier.correction_generation, "a" * 64)
        context = SolveContext(
            binding, qualified_compositions=(cached,),
            qualification_verifier=lambda item: True)
        owner = context.operator_composition_artifact_owner
        source = next(
            ref for ref in owner.node_for(cached).immediate_dependencies
            if ref.kind.value == "SOURCE" and ref.key.startswith("source:binding:"))
        event = _event(source)
        self.assertTrue(apply_solve_context_correction(
            context, event, AUTHORITY))

        learned = QualifiedComposition(
            add, generation.source_binding_digest, generation.generation_digest,
            binding.frontier.rights_epoch,
            binding.frontier.correction_generation, "b" * 64)
        self.assertTrue(owner.remember(learned, binding))
        self.assertIn(owner.node_for(learned).artifact_id, owner.queue.held_artifact_ids)

    def test_neural_materialization_cannot_exceed_cached_candidate_budget(self):
        binding, generation, _budget, add, ambiguous = _fixture()
        cached = QualifiedComposition(
            add, generation.source_binding_digest,
            generation.generation_digest,
            binding.frontier.rights_epoch,
            binding.frontier.correction_generation, "a" * 64)
        calls = []

        def neural(request):
            calls.append(request)
            return NeuralProposal(
                add, request.source_binding_digest,
                request.generation_digest,
                request.unresolved_signature,
                "b" * 64)

        context = SolveContext(
            binding, qualified_compositions=(cached,),
            qualification_verifier=lambda item: False,
            neural_proposer=neural)
        budget = SolveBudget(
            DAGBudget(), max_neural_calls=1, max_cached_candidates=1)
        first = solve_task(ambiguous, context, generation, budget)
        self.assertEqual(first.route, RouteKind.NEURAL_COMPOSITION)
        self.assertEqual(
            len(context.operator_composition_artifact_owner.compositions), 1)
        second = solve_task(ambiguous, context, generation, budget)
        self.assertEqual(second.route, RouteKind.NEURAL_COMPOSITION)
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            len(context.operator_composition_artifact_owner.compositions), 1)

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
            generation.generation_digest,
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
            generation.generation_digest,
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
            generation.generation_digest,
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
