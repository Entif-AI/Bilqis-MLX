"""Validate the entire DAG before any computation."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade
from ..cognitive_dag import (
    DAGOperand, DAGProgram, DAGBudget, DAGNode, TaskGoal, DAGResult, DAGReceipt,
    OperatorBinding, TypedValue, PureOperationMemo,
)


def _public():
    return public_facade("bilqis_mlx.semantics.cognitive_dag")


from .preparation_state import _Preparation


def _prepare(goal: TaskGoal, binding: OperatorBinding):
    """Validate the entire typed dependency graph before any computation."""
    if (not isinstance(goal, _public().TaskGoal)
            or not isinstance(binding, _public().OperatorBinding)):
        _public()._invalid("BAMF_DAG_EXECUTION_INPUT_INVALID")
    program = goal.expression_or_holes
    budget = goal.budget
    output = next(
        node for node in program.nodes
        if node.node_id == program.output_node_id)
    if (goal.scope != binding.task.scope
            or goal.semantic_release != binding.task.semantic_release
            or goal.output_signature != output.expected_output_type):
        _public()._invalid("BAMF_DAG_SCOPE_MISMATCH")
    order = _public()._topological(program, budget)
    by_id = {node.node_id: node for node in program.nodes}
    approved = _public()._approved_frames(binding)
    _public()._authorize_inputs((), binding)
    state = _Preparation(goal, binding, budget, by_id, approved)
    for node in order:
        matches = state.candidates(node)
        if any(ref is None for ref in node.operands):
            state.bind_open(node, matches)
            continue
        state.bind_fixed(node, matches)
    return state.finish(order)
