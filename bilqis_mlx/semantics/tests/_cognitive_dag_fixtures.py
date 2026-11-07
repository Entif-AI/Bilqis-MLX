"""Shared fixtures for the split cognitive DAG tests."""
from dataclasses import replace
import socket
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.cognitive_dag import (
    DAGBudget, DAGNode, DAGOperand, DAGProgram, DAGReceipt, DAGResult, RefKind,
    TaskGoal, execute_dag, task_goal_from_program,
)
from bilqis_mlx.semantics.cognitive_operators import (
    Duration, SourceKind, TypedValue, ValueState,
)
from bilqis_mlx.semantics.foundation.memo import PureOperationMemo
from bilqis_mlx.semantics.tests.test_cognitive_operators import (
    RELEASE, SCOPE, _case, _grant, _with_frame, _with_unit_edge,
)

def _literal(value):
    return DAGOperand(RefKind.LITERAL, value.type_name, source_handle=value.source_handle)

def _result(node_id: str, type_name: str = "Number"):
    return DAGOperand(RefKind.RESULT, type_name, result_node_id=node_id)

def _program(*nodes, output=None):
    return DAGProgram(tuple(nodes), output or nodes[-1].node_id, SCOPE)

def _goal(program, binding, budget=None):
    return task_goal_from_program(program, binding, goal_id="synthetic:goal", budget=budget)

def _execute(program, binding, *, memo=None, budget=None):
    return execute_dag(_goal(program, binding, budget), binding, memo=memo)


__all__ = [
    "replace", "socket", "patch", "BilqisError", "DAGBudget", "DAGNode",
    "DAGOperand", "DAGProgram", "DAGReceipt", "DAGResult", "RefKind",
    "TaskGoal", "execute_dag", "task_goal_from_program", "Duration",
    "SourceKind", "TypedValue", "ValueState", "PureOperationMemo", "RELEASE",
    "SCOPE", "_case", "_grant", "_with_frame", "_with_unit_edge", "_literal",
    "_result", "_program", "_goal", "_execute",
]
