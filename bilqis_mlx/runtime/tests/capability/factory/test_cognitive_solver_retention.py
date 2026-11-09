"""C04 retained-composition custody and C09 correction regressions."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_revalidation import apply_solve_context_correction
from bilqis_mlx.runtime.cognitive_solver import (
    NeuralProposal, QualifiedComposition, RouteKind, SolveContext, solve_task,
)
from bilqis_mlx.runtime.tests.capability.factory.solver_helpers import _fixture
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _result,
)


class CognitiveSolverRetentionTests(unittest.TestCase):
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
            add, generation.source_binding_digest, generation.generation_digest,
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
        self.assertEqual(
            solve_task(ambiguous, context, generation, budget).route,
            RouteKind.CACHED_COMPOSITION)

    def test_successful_neural_composition_materializes_into_retained_owner(self):
        binding, generation, budget, add, ambiguous = _fixture()
        calls = []

        def neural(request):
            calls.append(request)
            return NeuralProposal(
                add, request.source_binding_digest, request.generation_digest,
                request.unresolved_signature, "c" * 64)

        context = SolveContext(binding, neural_proposer=neural)
        first = solve_task(ambiguous, context, generation, budget)
        self.assertEqual(first.route, RouteKind.NEURAL_COMPOSITION)
        retained = context.operator_composition_artifact_owner.compositions
        self.assertEqual((len(calls), len(retained)), (1, 1))
        self.assertTrue(
            context.operator_composition_artifact_owner.is_materialized(retained[0]))
        self.assertEqual(
            solve_task(ambiguous, context, generation, budget).route,
            RouteKind.CACHED_COMPOSITION)
        self.assertEqual(len(calls), 1)

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

if __name__ == "__main__":
    unittest.main()
