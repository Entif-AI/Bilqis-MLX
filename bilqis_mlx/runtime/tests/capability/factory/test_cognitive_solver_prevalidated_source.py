"""Learning-first C04 source authority is established once, then carried forward."""
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.cognitive_solver import (
    NeuralProposal, RouteKind, SolveContext, solve_task,
)
from bilqis_mlx.runtime.tests.capability.factory.solver_helpers import _fixture
import bilqis_mlx.semantics._cognitive_dag.execution as dag_execution
import bilqis_mlx.semantics._cognitive_dag.prepare as dag_prepare
import bilqis_mlx.semantics.cognitive_operators.authorization as operator_authorization


class PrevalidatedSourceAuthorityTests(unittest.TestCase):
    def _context(self):
        binding, generation, budget, resolved, unresolved = _fixture()
        preflight = dag_execution.execute_dag(
            unresolved, binding,
            source_binding_digest=generation.source_binding_digest)

        def neural(request):
            return NeuralProposal(
                resolved,
                request.source_binding_digest,
                request.generation_digest,
                request.unresolved_signature,
                "b" * 64,
            )

        return (
            binding,
            generation,
            budget,
            unresolved,
            SolveContext(
                binding,
                source_binding_digest=generation.source_binding_digest,
                neural_proposer=neural,
                retain_validated_compositions=False,
                prevalidated_exact_goal=unresolved,
                prevalidated_exact_result=preflight,
                prevalidated_source_authority=True,
            ),
        )

    def test_learning_first_skips_reauthorization_and_provenance_rebuild(self):
        _binding, generation, budget, task, context = self._context()
        blocked = AssertionError("ordinary solve replayed prevalidated source authority")
        with (
            evidence_mode(strict=False),
            patch.object(dag_prepare, "_approved_frames", side_effect=blocked),
            patch.object(dag_prepare, "_authorize_inputs", side_effect=blocked),
            patch.object(dag_prepare, "_check_grant", side_effect=blocked),
            patch.object(dag_execution, "_check_grant", side_effect=blocked),
            patch.object(dag_execution, "_grant_record", side_effect=blocked),
            patch.object(dag_execution.PureOperationMemo, "key", side_effect=blocked),
            patch.object(operator_authorization, "_check_grant", side_effect=blocked),
        ):
            result = solve_task(task, context, generation, budget)

        self.assertEqual(result.route, RouteKind.NEURAL_COMPOSITION)
        self.assertEqual(result.answer.value, 5)

    def test_strict_mode_replays_source_authority_even_if_context_is_prevalidated(self):
        _binding, generation, budget, task, context = self._context()
        authorize = dag_prepare._authorize_inputs
        grant = dag_prepare._check_grant
        with (
            evidence_mode(strict=True),
            patch.object(dag_prepare, "_authorize_inputs", wraps=authorize) as authorize_call,
            patch.object(dag_prepare, "_check_grant", wraps=grant) as grant_call,
        ):
            result = solve_task(task, context, generation, budget)

        self.assertEqual(result.route, RouteKind.NEURAL_COMPOSITION)
        self.assertGreater(authorize_call.call_count, 0)
        self.assertGreater(grant_call.call_count, 0)


if __name__ == "__main__":
    unittest.main()
