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
    def test_receipt_and_answer_boundary_rejects_forged_state(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        program = _program(DAGNode(
            "sum", "ADD", (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE))
        valid = _execute(program, binding)
        for changes in (
            {"source_binding_digest": "z" * 64},
            {"executed_nodes": ("other",)},
            {"lookup_count": 0},
            {"selected_bindings": (("bad", "ADD", ()),)},
            {"unresolved_signature": "sum:Number"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(BilqisError):
                    DAGResult(valid.answer, replace(valid.receipt, **changes))
        foreign = TypedValue("Number", 5, "b" * 64)
        with self.assertRaises(BilqisError):
            DAGResult(foreign, valid.receipt)
