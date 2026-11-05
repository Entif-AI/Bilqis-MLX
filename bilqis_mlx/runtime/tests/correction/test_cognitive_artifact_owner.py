"""C09 production ownership for C04/C05 reusable cognitive artifacts."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.capability_retention import (
    CompleteSolver, EvaluationCase, EvaluationCohort, EvidenceKind,
    case_census_digest, evaluate_capabilities,
)
from bilqis_mlx.runtime.cognitive_solver import (
    QualifiedComposition, RouteKind, SolveContext,
)
from bilqis_mlx.runtime.atlas_requalification import RequalificationStatus
from bilqis_mlx.runtime.tests.capability.solver_helpers import _fixture
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _result,
)
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, DependencyKind,
)
from bilqis_mlx.semantics.cognitive_dag import DAGNode
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.cognitive_operators import TypedValue
from bilqis_mlx.semantics.tests.test_cognitive_dag import (
    _goal, _literal, _program,
)
from bilqis_mlx.semantics.tests.test_cognitive_operators import SCOPE, _case


class CognitiveArtifactOwnerTests(unittest.TestCase):
    def test_exact_cache_hold_blocks_real_solver_reuse_then_equal_output_clears(self):
        binding, generation, budget, add, _ = _fixture()
        solver = CompleteSolver(
            lambda goal, generation_id: SolveContext(binding), budget)

        first, _ = solver.evaluate(add, generation.generation_digest)
        self.assertEqual(first.route, RouteKind.EXACT)
        cache = next(
            node for node in solver.artifact_owner.index.nodes
            if node.kind is ArtifactKind.EXACT_CACHE)
        source = next(
            ref for ref in cache.immediate_dependencies
            if ref.kind is DependencyKind.SOURCE)
        self.assertTrue(any(
            ref.kind is DependencyKind.TIME
            and ref.key.startswith("time:task:")
            for ref in cache.immediate_dependencies))
        event = _event(source)
        queue = solver.artifact_owner.apply_correction(event, AUTHORITY)
        self.assertIn(cache.artifact_id, queue.held_artifact_ids)

        with self.assertRaises(BilqisError) as caught:
            solver.evaluate(add, generation.generation_digest)
        self.assertEqual(
            caught.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")

        progress = solver.artifact_owner.advance(
            _result(cache, digest=cache.content_digest, correction=event), AUTHORITY)
        self.assertEqual(progress.queue.pending, ())
        again, _ = solver.evaluate(add, generation.generation_digest)
        self.assertEqual(again.route, RouteKind.EXACT)
        self.assertGreater(again.dag_receipts[0].memo_hit_count, 0)

    def test_unrelated_cache_materializes_while_another_correction_is_pending(self):
        binding, generation, budget, add, _ = _fixture()
        sub_binding, sub_values = _case(("Number", 3), ("Number", 2))
        subtract = _goal(_program(DAGNode(
            "answer", "SUB", (_literal(sub_values[0]), _literal(sub_values[1])),
            "Number", SCOPE)), sub_binding)
        solver = CompleteSolver(
            lambda goal, generation_id: SolveContext(
                sub_binding if goal.goal_id == subtract.goal_id else binding), budget)
        solver.evaluate(add, generation.generation_digest)
        add_cache = next(
            node for node in solver.artifact_owner.index.nodes
            if node.kind is ArtifactKind.EXACT_CACHE)
        add_operator_source = next(
            ref for ref in add_cache.immediate_dependencies
            if ref.kind is DependencyKind.SOURCE
            and ref.key == "source:operator:ADD")
        queue = solver.artifact_owner.apply_correction(
            _event(add_operator_source), AUTHORITY)
        self.assertTrue(queue.pending)

        result, _ = solver.evaluate(subtract, generation.generation_digest)
        self.assertEqual(result.route, RouteKind.EXACT)
        sub_caches = tuple(
            node for node in solver.artifact_owner.index.nodes
            if node.kind is ArtifactKind.EXACT_CACHE
            and any(ref.key == "source:operator:SUB"
                    for ref in node.immediate_dependencies))
        self.assertTrue(sub_caches)
        self.assertTrue(all(
            node.artifact_id not in queue.held_artifact_ids for node in sub_caches))

    def test_composition_read_is_gated_and_real_cache_priority_precedes_it(self):
        binding, generation, budget, add, ambiguous = _fixture()
        composition = QualifiedComposition(
            goal=add,
            source_binding_digest=generation.source_binding_digest,
            rights_epoch=binding.frontier.rights_epoch,
            correction_generation=binding.frontier.correction_generation,
            qualification_receipt_sha256="a" * 64,
        )
        solver = CompleteSolver(
            lambda goal, generation_id: SolveContext(
                binding,
                qualified_compositions=(composition,),
                qualification_verifier=lambda item: True,
            ),
            budget,
        )
        first, _ = solver.evaluate(ambiguous, generation.generation_digest)
        self.assertEqual(first.route, RouteKind.CACHED_COMPOSITION)
        owner = solver.artifact_owner
        materialized = tuple(owner.index.nodes)
        composition_node = next(
            node for node in materialized
            if node.kind is ArtifactKind.OPERATOR_COMPOSITION)
        cache_ids = {
            node.artifact_id for node in materialized
            if node.kind is ArtifactKind.EXACT_CACHE}
        composition_artifacts = {
            ref.key for ref in composition_node.immediate_dependencies
            if ref.kind is DependencyKind.ARTIFACT}
        self.assertTrue(cache_ids)
        self.assertTrue(cache_ids <= composition_artifacts)
        self.assertTrue(any(
            ref.kind is DependencyKind.TIME
            and ref.key.startswith("time:task:")
            for ref in composition_node.immediate_dependencies))
        source = next(
            ref for ref in composition_node.immediate_dependencies
            if ref.kind is DependencyKind.SOURCE)
        queue = owner.apply_correction(_event(source), AUTHORITY)
        ordered_kinds = tuple(
            owner.index.node(task.artifact_id).kind for task in queue.pending)
        self.assertIn(ArtifactKind.EXACT_CACHE, ordered_kinds)
        self.assertIn(ArtifactKind.OPERATOR_COMPOSITION, ordered_kinds)
        self.assertLess(
            ordered_kinds.index(ArtifactKind.EXACT_CACHE),
            ordered_kinds.index(ArtifactKind.OPERATOR_COMPOSITION))
        with self.assertRaises(BilqisError) as caught:
            solver.evaluate(ambiguous, generation.generation_digest)
        self.assertIn(caught.exception.context["reason"], {
            "BAMF_C09_ARTIFACT_HELD",
            "BAMF_C09_ARTIFACT_DEPENDENCY_HELD",
        })

    def test_frozen_assessment_materializes_real_capability_support_for_requalification(self):
        binding, generation, budget, add, _ = _fixture()
        add = replace(add, goal_id="fixture:capability-support")
        case = EvaluationCase(
            "fixture:case", "capability:add", "grade:fixture",
            "fixture:source-family", "fixture:episode", add,
            TypedValue("Number", 5, add.semantic_release),
        )
        cohort = EvaluationCohort(
            EvidenceKind.FRESH_TARGET,
            (case,),
            (("capability:add", "grade:fixture"),),
            "1" * 64, "2" * 64, "3" * 64, "4" * 64,
            (), (), case_census_digest((case,)),
        )
        solver = CompleteSolver(
            lambda goal, generation_id: SolveContext(binding), budget)
        assessment = evaluate_capabilities(
            solver, cohort, generation.generation_digest)
        ledger = solver.artifact_owner.capability_ledger(assessment.digest())
        support = ledger.capability("capability:add")
        self.assertTrue(support.support_artifact_ids)
        self.assertTrue(all(
            solver.artifact_owner.index.node(artifact_id).kind
            is ArtifactKind.EXACT_CACHE
            for artifact_id in support.support_artifact_ids))
        capability_node = next(
            node for node in solver.artifact_owner.index.nodes
            if node.kind is ArtifactKind.CAPABILITY_SUPPORT)
        self.assertEqual(capability_node.content_digest, contract_digest(support))

        cache = solver.artifact_owner.index.node(support.support_artifact_ids[0])
        source = next(
            ref for ref in cache.immediate_dependencies
            if ref.kind is DependencyKind.SOURCE)
        solver.artifact_owner.apply_correction(_event(source), AUTHORITY)
        updated = solver.artifact_owner.capability_ledger(assessment.digest())
        self.assertEqual(
            updated.capability("capability:add").status,
            RequalificationStatus.REQUALIFICATION_REQUIRED)
        self.assertEqual(len(updated.pending_source_tasks), 1)
        self.assertEqual(len(updated.pending_c10_intents), 1)

    def test_frozen_support_uses_result_scope_not_later_same_task_history(self):
        binding, generation, budget, add, ambiguous = _fixture()
        later_binding = replace(
            binding,
            task=replace(binding.task, observed_frontier=binding.task.observed_frontier + 1),
        )
        first_composition = QualifiedComposition(
            add, generation.source_binding_digest,
            binding.frontier.rights_epoch, binding.frontier.correction_generation,
            "a" * 64)
        later_composition = QualifiedComposition(
            add, contract_digest(later_binding),
            later_binding.frontier.rights_epoch,
            later_binding.frontier.correction_generation,
            "b" * 64)
        later_generation = "e" * 64
        def context_for(goal, generation_id):
            selected_binding, composition = (
                (later_binding, later_composition)
                if generation_id == later_generation
                else (binding, first_composition))
            return SolveContext(
                selected_binding,
                qualified_compositions=(composition,),
                qualification_verifier=lambda item: True)
        solver = CompleteSolver(context_for, budget)
        case = EvaluationCase(
            "fixture:scoped", "capability:add", "grade:fixture",
            "fixture:source-family", "fixture:episode", ambiguous,
            TypedValue("Number", 5, ambiguous.semantic_release))
        cohort = EvaluationCohort(
            EvidenceKind.FRESH_TARGET, (case,),
            (("capability:add", "grade:fixture"),),
            "1" * 64, "2" * 64, "3" * 64, "4" * 64,
            (), (), case_census_digest((case,)))
        assessment = evaluate_capabilities(
            solver, cohort, generation.generation_digest)
        first_support = solver.artifact_owner.support_for_result(
            assessment.results[0])
        first_ledger = solver.artifact_owner.capability_ledger(
            assessment.digest())
        later_result, _ = solver.evaluate(ambiguous, later_generation)
        later_support = solver.artifact_owner.support_for_result(later_result)
        self.assertNotEqual(first_support, later_support)
        self.assertEqual(
            first_ledger.capability("capability:add").support_artifact_ids,
            first_support)


if __name__ == "__main__":
    unittest.main()
