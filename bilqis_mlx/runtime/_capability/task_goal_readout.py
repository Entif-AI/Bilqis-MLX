"""B10 route decisions for bounded C04 TaskGoal holes."""
from __future__ import annotations

from dataclasses import replace

from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, DecisionKind, DecisionSpec, ModelOutput,
)
from bilqis_mlx.learning.atlas_readout.decoder.prediction import issued_output
from bilqis_mlx.runtime.cognitive_solver import NeuralProposal, NeuralRequest
from bilqis_mlx.semantics.cognitive_dag import DAGNode, TaskGoal
from bilqis_mlx.semantics.domains import contract_digest

from .capability_evaluation import _invalid


def _operator_id(node: DAGNode) -> str:
    return f"route.{node.node_id}.operator"


def _operand_id(node: DAGNode, index: int) -> str:
    return f"route.{node.node_id}.operand.{index}"


def task_goal_route_decisions(goal: TaskGoal) -> tuple[DecisionSpec, ...]:
    """Lower only declared DAG holes into bounded B10 decisions."""
    if type(goal) is not TaskGoal:
        _invalid("BAMF_C04_TASK_GOAL_ROUTE_INPUT_INVALID")
    result = []
    prior = ()
    for node in goal.expression_or_holes.nodes:
        if node.operator_id is not None:
            continue
        operator_id = _operator_id(node)
        result.append(DecisionSpec(
            operator_id, None, 0, DecisionKind.OPERATOR,
            node.candidate_operator_ids, prior,
        ))
        prior = (operator_id,)
        for index, (fixed, candidates) in enumerate(zip(
                node.operands, node.candidate_operand_refs)):
            if fixed is not None:
                continue
            decision_id = _operand_id(node, index)
            result.append(DecisionSpec(
                decision_id, None, index, DecisionKind.OPERAND,
                tuple(ref.identity for ref in candidates), prior,
            ))
            prior = (decision_id,)
    return tuple(result)


def augment_answer_plan_for_task_goal(
    plan: AnswerPlan, goal: TaskGoal,
) -> AnswerPlan:
    """Place route selection before the ordinary source-owned answer plan."""
    if type(plan) is not AnswerPlan or type(goal) is not TaskGoal:
        _invalid("BAMF_C04_TASK_GOAL_PLAN_INPUT_INVALID")
    route = task_goal_route_decisions(goal)
    if not route:
        return plan
    route_ids = tuple(item.decision_id for item in route)
    if len(route) + len(plan.decisions) > plan.maximum_decisions:
        _invalid("BAMF_C04_TASK_GOAL_ROUTE_BUDGET_EXCEEDED")
    ordinary = tuple(replace(
        decision,
        depends_on=tuple(dict.fromkeys((*route_ids, *decision.depends_on))),
    ) for decision in plan.decisions)
    return replace(plan, decisions=(*route, *ordinary))


def proposal_from_task_goal_output(
    goal: TaskGoal,
    request: NeuralRequest,
    output: ModelOutput,
) -> NeuralProposal:
    """Turn one live B10 route choice into the exact C04 proposal it selected."""
    if (type(goal) is not TaskGoal or type(request) is not NeuralRequest
            or type(output) is not ModelOutput or not issued_output(output)):
        _invalid("BAMF_C04_TASK_GOAL_ROUTE_OUTPUT_INVALID")
    route = task_goal_route_decisions(goal)
    route_ids = {item.decision_id for item in route}
    committed = {item.decision_id: item.value for item in output.committed
                 if item.decision_id in route_ids}
    if set(committed) != route_ids:
        _invalid("BAMF_C04_TASK_GOAL_ROUTE_INCOMPLETE")
    nodes = []
    for node in goal.expression_or_holes.nodes:
        if node.operator_id is not None:
            nodes.append(node)
            continue
        operator = committed[_operator_id(node)]
        operands = list(node.operands)
        for index, (fixed, candidates) in enumerate(zip(
                node.operands, node.candidate_operand_refs)):
            if fixed is not None:
                continue
            selected = committed[_operand_id(node, index)]
            matches = tuple(ref for ref in candidates if ref.identity == selected)
            if len(matches) != 1:
                _invalid("BAMF_C04_TASK_GOAL_OPERAND_SELECTION_INVALID")
            operands[index] = matches[0]
        nodes.append(replace(
            node, operator_id=operator, operands=tuple(operands),
            candidate_operator_ids=(), candidate_operand_refs=(), constraints=(),
        ))
    proposal_goal = replace(
        goal,
        expression_or_holes=replace(goal.expression_or_holes, nodes=tuple(nodes)),
    )
    receipt = contract_digest({
        "schema": "bilqis.mlx.b10-task-goal-route/v1",
        "goal": contract_digest(goal),
        "request": request,
        "plan": output.plan,
        "route": tuple((key, committed[key]) for key in sorted(committed)),
    })
    return NeuralProposal(
        proposal_goal, request.source_binding_digest,
        request.generation_digest, request.unresolved_signature, receipt,
    )


__all__ = (
    "augment_answer_plan_for_task_goal",
    "proposal_from_task_goal_output",
    "task_goal_route_decisions",
)
