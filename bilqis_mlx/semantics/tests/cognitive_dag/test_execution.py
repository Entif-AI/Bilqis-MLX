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
from bilqis_mlx.semantics.tests.cognitive_dag.fixtures import (
    _literal, _result, _program, _goal, _execute,
)


class CognitiveDAGTests(TestCase):
    def test_two_node_add_mul_returns_ten_and_counts_compute(self):
        binding, values = _case(
            ("Number", 2), ("Number", 3), ("Number", 4))
        program = _program(
            DAGNode("mul", "MUL", (_literal(values[0]), _literal(values[1])),
                    "Number", SCOPE),
            DAGNode("add", "ADD", (_result("mul"), _literal(values[2])),
                    "Number", SCOPE),
        )
        memo = PureOperationMemo()
        with patch.object(
            socket, "socket", side_effect=AssertionError("network reached")
        ):
            first = _execute(program, binding, memo=memo)
        self.assertEqual((first.answer.state, first.answer.value),
                         (ValueState.VALUE, 10))
        self.assertEqual((first.receipt.operation_count,
                          first.receipt.lookup_count,
                          first.receipt.memo_hit_count), (2, 2, 0))
        self.assertEqual(first.receipt.executed_nodes, ("mul", "add"))
        second = _execute(program, binding, memo=memo)
        self.assertEqual(second.answer.value, 10)
        self.assertEqual((second.receipt.operation_count,
                          second.receipt.lookup_count,
                          second.receipt.memo_hit_count), (0, 2, 2))

    def test_budget_exhaustion_counts_actual_memo_get_without_compute(self):
        class CountingMemo(PureOperationMemo):
            def __init__(self):
                super().__init__()
                self.get_calls = 0

            def get(self, key):
                self.get_calls += 1
                return super().get(key)

        binding, values = _case(
            ("Number", 2), ("Number", 3), ("Number", 4))
        program = _program(
            DAGNode("mul", "MUL", (_literal(values[0]), _literal(values[1])),
                    "Number", SCOPE),
            DAGNode("add", "ADD", (_result("mul"), _literal(values[2])),
                    "Number", SCOPE))
        memo = CountingMemo()
        limited = _execute(
            program, binding, memo=memo,
            budget=DAGBudget(max_operations=1))
        self.assertEqual(limited.answer.state, ValueState.UNRESOLVED)
        self.assertEqual(memo.get_calls, 2)
        self.assertEqual((limited.receipt.lookup_count,
                          limited.receipt.operation_count,
                          limited.receipt.memo_hit_count), (2, 1, 0))
        self.assertEqual(limited.receipt.executed_nodes, ("mul",))
        self.assertEqual(limited.receipt.unresolved_signature, "add:Number")

    def test_failed_applicability_costs_one_operation(self):
        binding, values = _case(("Number", 2), ("Number", 0))
        program = _program(DAGNode(
            "divide", "DIV", (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE))
        result = _execute(program, binding)
        self.assertEqual(result.answer.state, ValueState.UNSUPPORTED)
        self.assertEqual(result.receipt.operation_count, 1)
        self.assertEqual(result.receipt.lookup_count, 1)
