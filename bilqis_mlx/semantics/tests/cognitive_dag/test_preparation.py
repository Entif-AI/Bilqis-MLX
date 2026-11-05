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
    def test_hole_candidate_fanout_is_bounded_before_registry_or_compute(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        candidates = tuple(f"synthetic:operator:{i:03d}" for i in range(65))
        with self.assertRaises(BilqisError):
            DAGNode(
                "answer", None, (_literal(values[0]), _literal(values[1])),
                "Number", SCOPE, candidate_operator_ids=candidates)
        refs = tuple(
            DAGOperand(RefKind.LITERAL, "Number",
                       source_handle=f"source:choice:{i:03d}")
            for i in range(65))
        with self.assertRaises(BilqisError):
            DAGNode(
                "answer", None, (None, _literal(values[1])),
                "Number", SCOPE, candidate_operator_ids=("ADD",),
                candidate_operand_refs=(refs, ()))

    def test_single_legal_operator_hole_binds_without_neural_guess(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        hole = DAGNode(
            "answer", None, (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE, candidate_operator_ids=("ADD",))
        result = _execute(_program(hole), binding)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.receipt.operation_count, 1)
        self.assertEqual(result.receipt.selected_bindings[0][1], "ADD")

    def test_ambiguous_hole_is_unresolved_not_answer_leak(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        hole = DAGNode(
            "answer", None, (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE, candidate_operator_ids=("ADD", "SUB"))
        result = _execute(_program(hole), binding)
        self.assertEqual(result.answer.state, ValueState.UNRESOLVED)
        self.assertIsNone(result.answer.value)
        self.assertEqual(result.receipt.operation_count, 0)
        self.assertEqual(result.receipt.unresolved_signature, "answer:Number")

    def test_ungranted_hole_candidate_cannot_create_false_ambiguity(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        hole = DAGNode(
            "answer", None, (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE, candidate_operator_ids=("ADD", "SUB"))
        frontier = replace(
            binding.frontier,
            grants=tuple(
                grant for grant in binding.frontier.grants
                if grant.source_handle != "source:operator:SUB"))
        ungranted = replace(binding, frontier=frontier)
        with patch(
            "bilqis_mlx.semantics.cognitive_dag._compute_after_authorization",
            side_effect=AssertionError("computed before grant validation"),
        ):
            with self.assertRaises(BilqisError) as caught:
                _execute(_program(hole), ungranted)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_OPERATOR_SOURCE_GRANT_MISSING")

    def test_hole_with_one_source_visible_operand_choice_binds(self):
        binding, values = _case(
            ("Number", 2), ("Number", 3), ("Number", 4))
        hole = DAGNode(
            "answer", None, (_literal(values[0]), None),
            "Number", SCOPE, candidate_operator_ids=("ADD",),
            candidate_operand_refs=((), (_literal(values[1]),)),
            constraints=("APPLICABLE", "SOURCE_VISIBLE", "TYPE_COMPATIBLE"))
        result = _execute(_program(hole), binding)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.receipt.operation_count, 1)
        ambiguous = replace(hole, candidate_operand_refs=(
            (), (_literal(values[1]), _literal(values[2]))))
        unresolved = _execute(_program(ambiguous), binding)
        self.assertEqual(unresolved.answer.state, ValueState.UNRESOLVED)
        self.assertEqual(unresolved.receipt.operation_count, 0)

    def test_hole_joint_operator_output_and_operand_types_bind_one_solution(self):
        binding, values = _case(
            ("Number", 2), ("Number", 3), ("Boolean", True))
        hole = DAGNode(
            "answer", None, (_literal(values[0]), None),
            "Number", SCOPE, candidate_operator_ids=("ADD", "BOOL_AND"),
            candidate_operand_refs=(
                (), (_literal(values[1]), _literal(values[2]))))
        result = _execute(_program(hole), binding)
        self.assertEqual(result.answer.value, 5)
        self.assertEqual(result.receipt.operation_count, 1)
        self.assertEqual(result.receipt.selected_bindings[0][1], "ADD")

    def test_holes_filter_source_inapplicable_division_before_binding(self):
        binding, values = _case(
            ("Number", 2), ("Number", 0), ("Number", 4))
        add_or_div = DAGNode(
            "answer", None, (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE, candidate_operator_ids=("ADD", "DIV"))
        selected = _execute(_program(add_or_div), binding)
        self.assertEqual(selected.answer.value, 2)
        self.assertEqual(selected.receipt.selected_bindings[0][1], "ADD")
        div_only = replace(add_or_div, candidate_operator_ids=("DIV",))
        unresolved = _execute(_program(div_only), binding)
        self.assertEqual(unresolved.answer.state, ValueState.UNRESOLVED)
        self.assertEqual(unresolved.receipt.operation_count, 0)
        divisor_hole = DAGNode(
            "answer", None, (_literal(values[2]), None),
            "Number", SCOPE, candidate_operator_ids=("DIV",),
            candidate_operand_refs=(
                (), (_literal(values[0]), _literal(values[1]))))
        exact = _execute(_program(divisor_hole), binding)
        self.assertEqual(exact.answer.value, 2)
        self.assertEqual(exact.receipt.operation_count, 1)
        zero_fixed = DAGNode(
            "answer", None, (None, None),
            "Number", SCOPE, candidate_operator_ids=("ADD", "DIV"),
            candidate_operand_refs=(
                (_literal(values[2]),), (_literal(values[1]),)))
        selected = _execute(_program(zero_fixed), binding)
        self.assertEqual(selected.answer.value, 4)
        self.assertEqual(selected.receipt.selected_bindings[0][1], "ADD")

    def test_two_operand_holes_bind_unique_jointly_applicable_pair(self):
        binding, values = _case(
            ("Number", 4), ("Number", 5),
            ("Number", 2), ("Number", 0))
        hole = DAGNode(
            "answer", None, (None, None), "Number", SCOPE,
            candidate_operator_ids=("DIV",),
            candidate_operand_refs=(
                (_literal(values[0]), _literal(values[1])),
                (_literal(values[2]), _literal(values[3]))))
        result = _execute(_program(hole), binding)
        self.assertEqual(result.answer.value, 2)
        self.assertEqual(result.receipt.operation_count, 1)
        self.assertEqual(result.receipt.selected_bindings, (
            ("answer", "DIV", (
                _literal(values[0]).identity,
                _literal(values[2]).identity)),))

    def test_late_node_operator_grant_fails_before_first_computation(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        program = _program(
            DAGNode(
                "sum", "ADD", (_literal(values[0]), _literal(values[1])),
                "Number", SCOPE),
            DAGNode(
                "product", "MUL", (_result("sum"), _literal(values[1])),
                "Number", SCOPE),
        )
        grants = tuple(
            replace(grant, revoked=True)
            if grant.source_handle == "source:operator:MUL" else grant
            for grant in binding.frontier.grants)
        revoked = replace(
            binding, frontier=replace(binding.frontier, grants=grants))
        with patch(
            "bilqis_mlx.semantics.cognitive_dag._compute_after_authorization",
            side_effect=AssertionError("computed before source validation"),
        ):
            with self.assertRaises(BilqisError):
                _execute(program, revoked)
