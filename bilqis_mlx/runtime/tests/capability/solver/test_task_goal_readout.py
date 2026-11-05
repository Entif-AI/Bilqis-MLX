"""B10 owns TaskGoal route choices; callers cannot mint neural proposals."""
from copy import deepcopy
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout import DecisionKind, predict_typed
from bilqis_mlx.learning.atlas_readout.decoder.tests.helpers import case
from bilqis_mlx.runtime.task_goal_readout import (
    augment_answer_plan_for_task_goal, proposal_from_task_goal_output,
    task_goal_route_decisions,
)
from bilqis_mlx.runtime.cognitive_solver import NeuralRequest
from bilqis_mlx.source_adapters.answer_choice_task_goal import (
    lower_answer_choice_task_goal,
)
from bilqis_mlx.curriculum import AnswerFamily, BINARY
from types import SimpleNamespace
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import (
    CANDIDATE, _cases,
)
from bilqis_mlx.semantics.domains import contract_digest


class TaskGoalReadoutTests(unittest.TestCase):
    def _case(self):
        cases, contexts = _cases("target", "amber", 1, "route")
        goal = cases[0].goal
        binding = contexts[goal.goal_id]
        memory, context, plan, semantics, parameters = case()
        plan = replace(plan, generation_binding=CANDIDATE)
        memory = replace(memory, generation_binding=CANDIDATE)
        request = NeuralRequest(
            goal.goal_id, "Number", contract_digest(binding), CANDIDATE,
            goal.allowed_operator_ids,
        )
        return goal, binding, request, memory, context, plan, semantics, parameters

    def test_task_goal_hole_becomes_operator_route_before_normal_answer(self):
        goal, _, _, _, _, plan, _, _ = self._case()
        augmented = augment_answer_plan_for_task_goal(plan, goal)
        route = task_goal_route_decisions(goal)

        self.assertEqual(route[0].legal_values, ("ADD", "SUB"))
        self.assertEqual(augmented.decisions[:len(route)], route)
        self.assertTrue(all(
            set(item.decision_id for item in route) <= set(decision.depends_on)
            for decision in augmented.decisions[len(route):]
        ))

    def test_live_decoder_route_becomes_scope_preserving_neural_proposal(self):
        goal, binding, request, memory, context, plan, semantics, parameters = self._case()
        augmented = augment_answer_plan_for_task_goal(plan, goal)
        output = predict_typed(memory, context, augmented, semantics, parameters)

        proposal = proposal_from_task_goal_output(goal, request, output)

        original = goal.expression_or_holes.nodes[0]
        chosen = proposal.goal.expression_or_holes.nodes[0]
        self.assertIn(chosen.operator_id, original.candidate_operator_ids)
        self.assertEqual(chosen.candidate_operator_ids, ())
        self.assertEqual(chosen.candidate_operand_refs, ())
        self.assertEqual(proposal.source_binding_digest, contract_digest(binding))
        self.assertEqual(proposal.generation_digest, CANDIDATE)

    def test_copied_route_strings_without_live_output_cannot_mint_proposal(self):
        goal, _, request, memory, context, plan, semantics, parameters = self._case()
        augmented = augment_answer_plan_for_task_goal(plan, goal)
        output = predict_typed(memory, context, augmented, semantics, parameters)
        fake = deepcopy(output)
        with self.assertRaises(BilqisError):
            proposal_from_task_goal_output(goal, request, fake)

    def test_fixed_selector_routes_only_source_visible_answer_operand(self):
        _, _, _, memory, context, plan, semantics, parameters = self._case()
        capability = SimpleNamespace(
            capability_id="A.IDENTITY",
            answer_families=(AnswerFamily("binary", BINARY),),
        )
        goal, binding = lower_answer_choice_task_goal(
            {"id": "answer-choice", "capability": "A.IDENTITY", "tokens": [1, 2]},
            semantic_release=semantics.features.semantic_release,
            capability=capability,
        )
        route = task_goal_route_decisions(goal)
        self.assertEqual(len(route), 1)
        self.assertIs(route[0].kind, DecisionKind.OPERAND)
        self.assertEqual(len(route[0].legal_values), 2)
        self.assertFalse(any(item.kind is DecisionKind.OPERATOR for item in route))

        plan = replace(plan, generation_binding=CANDIDATE)
        output = predict_typed(
            memory, context, augment_answer_plan_for_task_goal(plan, goal),
            semantics, parameters)
        request = NeuralRequest(
            goal.goal_id, "Boolean", contract_digest(binding), CANDIDATE,
            goal.allowed_operator_ids)
        proposal = proposal_from_task_goal_output(goal, request, output)
        node = proposal.goal.expression_or_holes.nodes[0]
        self.assertEqual(node.operator_id, "SELECT_BOOLEAN")
        self.assertEqual(node.candidate_operand_refs, ())
        self.assertEqual(len(node.operands), 1)
        self.assertIn(node.operands[0].identity, route[0].legal_values)


if __name__ == "__main__":
    unittest.main()
