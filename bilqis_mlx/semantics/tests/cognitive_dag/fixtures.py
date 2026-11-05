"""A07.3 bounded source-qualified compositional DAG execution witnesses."""
from __future__ import annotations

from dataclasses import replace
import ast
import importlib.util
from pathlib import Path
import socket
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.cognitive_dag import (
    DAGBudget, DAGNode, DAGOperand, DAGProgram, DAGResult, RefKind,
    TaskGoal, execute_dag,
)
from bilqis_mlx.semantics.cognitive_operators import (
    Duration, SourceKind, TypedValue, ValueState,
)
from bilqis_mlx.semantics.memo import PureOperationMemo
from bilqis_mlx.semantics.tests.test_cognitive_operators import (
    RELEASE, SCOPE, _case, _grant, _with_frame, _with_unit_edge,
)


def _literal(value):
    return DAGOperand(RefKind.LITERAL, value.type_name,
                      source_handle=value.source_handle)

def _result(node_id: str, type_name: str = "Number"):
    return DAGOperand(RefKind.RESULT, type_name, result_node_id=node_id)

def _program(*nodes, output=None):
    return DAGProgram(tuple(nodes), output or nodes[-1].node_id, SCOPE)

def _goal(program, binding, budget=None):
    refs = tuple(
        ref for node in program.nodes
        for ref in (
            tuple(ref for ref in node.operands if ref is not None)
            + tuple(ref for group in node.candidate_operand_refs for ref in group)
        )
        if ref.kind is not RefKind.RESULT)
    operators = tuple(sorted(set(
        operator_id for node in program.nodes
        for operator_id in (
            (node.operator_id,) if node.operator_id is not None
            else node.candidate_operator_ids))))
    output_type = next(
        node.expected_output_type for node in program.nodes
        if node.node_id == program.output_node_id)
    return TaskGoal(
        "synthetic:goal", output_type,
        tuple(sorted(set(ref.identity for ref in refs))),
        program, operators, budget or DAGBudget(),
        binding.task.semantic_release, program.scope)

def _execute(program, binding, *, memo=None, budget=None):
    return execute_dag(
        _goal(program, binding, budget), binding, memo=memo)

for _helper in (_literal, _result, _program, _goal, _execute):
    _helper.__module__ = "bilqis_mlx.semantics.tests.test_cognitive_dag"
del _helper
