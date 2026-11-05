"""C09 production ownership for C04/C05 reusable cognitive artifacts."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.capability_evidence_history import (
    materialize_capability_support,
)
from bilqis_mlx.runtime.capability_retention import (
    CompleteSolver, EvaluationCase, EvaluationCohort, EvidenceKind,
    case_census_digest, evaluate_capabilities,
)
from bilqis_mlx.runtime.cognitive_solver import (
    QualifiedComposition, RouteKind, SolveContext,
)
from bilqis_mlx.runtime.atlas_requalification import mark_affected_capabilities
from bilqis_mlx.runtime.tests.capability.solver_helpers import _fixture
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _result,
)
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, DependencyKind,
)
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.cognitive_operators import TypedValue


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
        ledger = materialize_capability_support(
            assessment, solver.artifact_owner)
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
        queue = solver.artifact_owner.apply_correction(_event(source), AUTHORITY)
        update = mark_affected_capabilities(
            ledger, solver.artifact_owner.index, queue)
        self.assertEqual(
            update.affected_capability_ids, ("capability:add",))


if __name__ == "__main__":
    unittest.main()
