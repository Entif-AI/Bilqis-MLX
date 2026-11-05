"""Execute one fully prepared, source-visible DAG."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade
from ..cognitive_dag import (
    DAGOperand, DAGProgram, DAGBudget, DAGNode, TaskGoal, DAGResult, DAGReceipt,
    OperatorBinding, TypedValue, PureOperationMemo,
)


def _public():
    return public_facade("bilqis_mlx.semantics.cognitive_dag")


from .execution_state import _Execution, _CONTINUE


def execute_dag(
    goal: TaskGoal,
    binding: OperatorBinding,
    *,
    memo: PureOperationMemo | None = None,
    operation_limit: int | None = None,
    artifact_owner=None,
    support_task_sha256: str | None = None,
) -> DAGResult:
    """Run one fully source-validated typed DAG without neural or gold inputs."""
    if memo is not None and not isinstance(memo, _public().PureOperationMemo):
        _public()._invalid("BAMF_DAG_MEMO_INVALID")
    order, prepared, visible, selected, unresolved = _public()._prepare(goal, binding)
    if operation_limit is not None and (
            type(operation_limit) is not int
            or not 0 <= operation_limit <= goal.budget.max_operations):
        _public()._invalid("BAMF_DAG_OPERATION_LIMIT_INVALID")
    state = _Execution(
        goal, binding, memo, operation_limit,
        (order, prepared, visible, selected, unresolved),
        artifact_owner, support_task_sha256)
    if unresolved is not None:
        return state.finish(
            _public().TypedValue(state.output_type, None, state.release,
                                 state=_public().ValueState.UNRESOLVED), unresolved)
    for node in order:
        result = state.step(node)
        if result is not _CONTINUE:
            return result
    return state.finish(state.results[state.program.output_node_id])
