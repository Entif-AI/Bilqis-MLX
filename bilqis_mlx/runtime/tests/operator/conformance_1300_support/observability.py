"""Read-only captures of production priority and complete-solver decisions."""
from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

from bilqis_mlx.runtime.capability_retention import CompleteSolver
import bilqis_mlx.runtime.bamf_operator.session as operator_session
import bilqis_mlx.runtime.factory_candidate_microbatch as candidate_microbatch


class ProductionRouteCapture:
    """Observe root-owned lawful-frontier and solver routes without changing them."""

    def __init__(self):
        self.priority_results = []
        self.solver_routes = []
        self.training_goals = []

    def context(self):
        stack = ExitStack()
        select = operator_session.select_foundation_priority_visit
        measure = CompleteSolver._measure
        training_goal = candidate_microbatch.factory_task_training_goal

        def capture_priority(*args, **kwargs):
            result = select(*args, **kwargs)
            self.priority_results.append(result)
            return result

        def capture_measure(solver, goal, generation, context):
            measured = measure(solver, goal, generation, context)
            result = measured[0]
            operators = tuple(dict.fromkeys(
                operator_id
                for receipt in result.dag_receipts
                for _node_id, operator_id, _refs in receipt.selected_bindings
            ))
            self.solver_routes.append((goal.scope, result.route.value, operators))
            return measured

        def capture_training_goal(*args, **kwargs):
            resolved = training_goal(*args, **kwargs)
            authority = args[2]
            self.training_goals.append((authority, resolved))
            return resolved

        stack.enter_context(patch.object(
            operator_session,
            "select_foundation_priority_visit",
            side_effect=capture_priority,
        ))
        stack.enter_context(patch.object(
            CompleteSolver,
            "_measure",
            autospec=True,
            side_effect=capture_measure,
        ))
        stack.enter_context(patch.object(
            candidate_microbatch,
            "factory_task_training_goal",
            side_effect=capture_training_goal,
        ))
        return stack

    def assert_release_present_exclusion(
            self, test, release, capability_id: str, *, expected_code: str) -> None:
        release_ids = set(release.execution_plan.capability_map)
        test.assertIn(capability_id, release_ids)
        witnessed = [
            exclusion
            for result in self.priority_results
            for exclusion in result.exclusions
            if exclusion.capability_id == capability_id
            and exclusion.capability_id in release_ids
            and exclusion.code.value == expected_code
        ]
        test.assertTrue(
            witnessed,
            "production root never exposed the intended release-present exclusion",
        )

    @property
    def route_kinds(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            route for _scope, route, _operators in self.solver_routes
        ))

    def assert_routes_for(self, test, capability_id: str, *expected: str) -> None:
        routes = {
            route for scope, route, _operators in self.solver_routes
            if scope == capability_id
        }
        for route in expected:
            test.assertIn(route, routes)

    def assert_neural_composition_executes_exact_operator(
            self, test, capability_id: str) -> None:
        witnesses = [
            operators
            for scope, route, operators in self.solver_routes
            if scope == capability_id and route == "NEURAL_COMPOSITION"
            and operators
        ]
        test.assertTrue(
            witnesses,
            "neural composition never executed a concrete source-qualified operator",
        )

    def assert_exact_training_route_for(self, test, capability_id: str) -> None:
        matches = [
            (authority, goal)
            for authority, goal in self.training_goals
            if authority.capability_id == capability_id
        ]
        test.assertTrue(matches)
        authority, goal = matches[-1]
        from bilqis_mlx.runtime.cognitive_solver import (
            GenerationBinding, SolveBudget, SolveContext, solve_task,
        )
        from bilqis_mlx.semantics.domains import contract_digest
        result = solve_task(
            goal,
            SolveContext(authority.binding),
            GenerationBinding(
                authority.generation_binding,
                goal.semantic_release,
                contract_digest(authority.binding),
            ),
            SolveBudget(goal.budget, max_neural_calls=0),
        )
        test.assertEqual(result.route.value, "EXACT")
        test.assertEqual(result.neural_calls, 0)
        test.assertTrue(result.dag_receipts)

