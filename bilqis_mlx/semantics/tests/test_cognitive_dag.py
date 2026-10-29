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

    def test_dag_transitive_runtime_imports_exclude_assessment_and_gold(self):
        root = Path(__file__).resolve().parents[3]
        seen = set()
        pending = ["bilqis_mlx.semantics.cognitive_dag"]

        def local_path(name):
            stem = root.joinpath(*name.split("."))
            if stem.with_suffix(".py").is_file():
                return stem.with_suffix(".py"), False
            if (stem / "__init__.py").is_file():
                return stem / "__init__.py", True
            return None, False

        while pending:
            name = pending.pop()
            if name in seen:
                continue
            path, is_package = local_path(name)
            if path is None:
                continue
            seen.add(name)
            package = name if is_package else name.rpartition(".")[0]
            for node in ast.walk(ast.parse(path.read_text())):
                imports = []
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    base = importlib.util.resolve_name(
                        "." * node.level + (node.module or ""), package)
                    imports.append(base)
                    imports.extend(base + "." + alias.name for alias in node.names)
                pending.extend(
                    candidate for candidate in imports
                    if candidate.startswith("bilqis_mlx.")
                    and local_path(candidate)[0] is not None)
        self.assertIn("bilqis_mlx.semantics.cognitive_operators", seen)
        forbidden = (
            "bilqis_mlx.verification", "bilqis_mlx.source_adapters",
            "bilqis_mlx.generated_assessment", "bilqis_mlx.assessment",
            "bilqis_mlx.factory", "bilqis_mlx.runtime",
        )
        self.assertFalse(
            [name for name in seen
             if name.startswith(forbidden) or name.endswith("_oracle")],
            seen)

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

    def test_memo_depends_on_consulted_sources_not_unrelated_grants(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        program = _program(DAGNode(
            "sum", "ADD", (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE))
        memo = PureOperationMemo()
        first = _execute(program, binding, memo=memo)
        self.assertEqual(first.answer.value, 5)
        self.assertEqual(first.receipt.operation_count, 1)
        extra = _grant("source:unrelated", "f" * 64)
        frontier = replace(
            binding.frontier,
            grants=tuple(sorted((*binding.frontier.grants, extra),
                                key=lambda grant: grant.source_handle)))
        with_extra = replace(binding, frontier=frontier)
        replay = _execute(program, with_extra, memo=memo)
        self.assertEqual(replay.answer.value, 5)
        self.assertEqual((replay.receipt.operation_count,
                          replay.receipt.memo_hit_count), (0, 1))
        changed, changed_values = _case(("Number", 2), ("Number", 4))
        changed_program = _program(DAGNode(
            "sum", "ADD",
            (_literal(changed_values[0]), _literal(changed_values[1])),
            "Number", SCOPE))
        miss = _execute(changed_program, changed, memo=memo)
        self.assertEqual(miss.answer.value, 6)
        self.assertEqual((miss.receipt.operation_count,
                          miss.receipt.memo_hit_count), (1, 0))

    def test_caller_poisoned_memo_never_becomes_source_truth(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        program = _program(DAGNode(
            "sum", "ADD", (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE))
        memo = PureOperationMemo()
        first = _execute(program, binding, memo=memo)
        self.assertEqual(first.answer.value, 5)
        key = next(iter(memo._values))
        forged = TypedValue("Number", 7, RELEASE)
        memo.put(key, forged)
        replay = _execute(program, binding, memo=memo)
        self.assertEqual(replay.answer.value, 5)
        self.assertEqual((replay.receipt.operation_count,
                          replay.receipt.memo_hit_count), (1, 0))
        new_memo = PureOperationMemo()
        new_memo.put(key, forged)
        untrusted = _execute(program, binding, memo=new_memo)
        self.assertEqual(untrusted.answer.value, 5)
        self.assertEqual((untrusted.receipt.operation_count,
                          untrusted.receipt.memo_hit_count), (1, 0))

    def test_source_attested_none_can_be_cached_without_becoming_zero(self):
        from bilqis_mlx.semantics.frame_schema import BindingState
        binding, values = _case(
            ("FrameHandle", "frame:one"), ("RoleId", "subject"),
            ("Index", 0), numbers=False)
        binding, _, _ = _with_frame(binding, state=BindingState.NONE)
        program = _program(DAGNode(
            "lookup", "ROLE_LOOKUP",
            tuple(_literal(value) for value in values),
            "ConceptRef", SCOPE))
        memo = PureOperationMemo()
        first = _execute(program, binding, memo=memo)
        second = _execute(program, binding, memo=memo)
        self.assertEqual(first.answer.state, ValueState.NONE)
        self.assertIsNone(first.answer.value)
        self.assertEqual(first.receipt.operation_count, 1)
        self.assertEqual(second.answer.state, ValueState.NONE)
        self.assertEqual((second.receipt.operation_count,
                          second.receipt.memo_hit_count), (0, 1))

    def test_memo_tracks_consulted_unit_edge_not_just_explicit_operands(self):
        binding, values = _case(
            ("Duration", Duration(1, 4, "h")),
            ("UnitName", "min"), numbers=False)
        admitted = _with_unit_edge(binding, "h", "min", 60, 1)
        program = _program(DAGNode(
            "convert", "UNIT_CONVERT",
            tuple(_literal(value) for value in values), "Duration", SCOPE))
        memo = PureOperationMemo()
        first = _execute(program, admitted, memo=memo)
        self.assertEqual(first.answer.value, Duration(15, 1, "min"))
        without_edge = replace(
            admitted,
            operands=tuple(item for item in admitted.operands
                           if item.kind is not SourceKind.ADMITTED_KNOWLEDGE),
            frontier=replace(
                admitted.frontier,
                grants=tuple(
                    item for item in admitted.frontier.grants
                    if not item.source_handle.startswith("source:unit:"))))
        replay = _execute(program, without_edge, memo=memo)
        self.assertEqual(replay.answer.state, ValueState.UNSUPPORTED)
        self.assertEqual((replay.receipt.operation_count,
                          replay.receipt.memo_hit_count), (1, 0))

    def test_memo_tracks_frame_content_and_member_rights(self):
        from bilqis_mlx.semantics.frame_schema import BindingState
        base, values = _case(
            ("FrameHandle", "frame:one"), ("RoleId", "subject"),
            ("Index", 0), numbers=False)
        occupied, _, _ = _with_frame(base, state=BindingState.VALUE)
        empty, _, _ = _with_frame(base, state=BindingState.NONE)
        program = _program(DAGNode(
            "lookup", "ROLE_LOOKUP",
            tuple(_literal(value) for value in values), "ConceptRef", SCOPE))
        memo = PureOperationMemo()
        first = _execute(program, occupied, memo=memo)
        self.assertEqual(first.answer.state, ValueState.VALUE)
        second = _execute(program, empty, memo=memo)
        self.assertEqual(second.answer.state, ValueState.NONE)
        self.assertEqual((second.receipt.operation_count,
                          second.receipt.memo_hit_count), (1, 0))

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

    def test_task_goal_limits_visible_sources_and_operator_choices(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        program = _program(DAGNode(
            "answer", "ADD", (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE))
        goal = _goal(program, binding)
        for restricted in (
            replace(goal, source_visible_bindings=(
                _literal(values[0]).identity,)),
            replace(goal, allowed_operator_ids=("MUL",)),
            replace(goal, output_signature="Boolean"),
        ):
            with self.subTest(goal=restricted):
                with self.assertRaises(BilqisError):
                    execute_dag(restricted, binding)

    def test_missing_source_literal_and_scope_drift_fail_before_compute(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        valid = DAGNode(
            "answer", "ADD", (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE)
        forged = replace(valid, operands=(
            DAGOperand(RefKind.LITERAL, "Number",
                       source_handle="source:forged"), _literal(values[1])))
        foreign_scope = "synthetic:other"
        foreign = replace(valid, scope=foreign_scope)
        for program in (_program(forged),
                        DAGProgram((foreign,), "answer", foreign_scope)):
            with self.subTest(program=program):
                with self.assertRaises(BilqisError):
                    _execute(program, binding)

    def test_cycle_orphan_and_result_type_drift_fail_closed(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        first = DAGNode(
            "first", "ADD", (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE)
        orphan = DAGNode("orphan", "ADD",
                         (_literal(values[0]), _literal(values[1])),
                         "Number", SCOPE)
        cycle_first = replace(
            first, operands=(_result("second"), _literal(values[0])))
        cycle_second = DAGNode(
            "second", "ADD", (_result("first"), _literal(values[1])),
            "Number", SCOPE)
        bad_type = DAGNode(
            "not", "BOOL_NOT",
            (DAGOperand(
                RefKind.RESULT, "Boolean", result_node_id="first"),),
            "Boolean", SCOPE)
        for program, reason in (
            (_program(cycle_first, cycle_second), "BAMF_DAG_CYCLE"),
            (_program(orphan, first, output="first"), "BAMF_DAG_ORPHAN_NODES"),
            (_program(first, bad_type), "BAMF_DAG_RESULT_TYPE_INVALID"),
        ):
            with self.subTest(program=program):
                with self.assertRaises(BilqisError) as caught:
                    _execute(program, binding)
                self.assertEqual(caught.exception.context["reason"], reason)

    def test_approved_frame_role_input_and_operation_budget(self):
        binding, _ = _case()
        binding, frame, _ = _with_frame(binding)
        input_ref = DAGOperand(
            RefKind.INPUT, "ConceptRef", frame_handle="frame:one",
            frame_occurrence_id=frame.occurrence_id,
            role_id="subject", occurrence_index=0)
        program = _program(
            DAGNode("types", "TYPE_OF", (input_ref,), "TypeSet", SCOPE))
        result = _execute(program, binding)
        self.assertEqual(result.answer.value, ("Entity",))
        self.assertEqual(result.receipt.operation_count, 1)
        forged = replace(
            input_ref, frame_occurrence_id="forged:occurrence")
        with self.assertRaises(BilqisError):
            _execute(_program(DAGNode(
                "types", "TYPE_OF", (forged,), "TypeSet", SCOPE)), binding)

        numeric, values = _case(
            ("Number", 2), ("Number", 3), ("Number", 4))
        two = _program(
            DAGNode("mul", "MUL", (_literal(values[0]), _literal(values[1])),
                    "Number", SCOPE),
            DAGNode("add", "ADD", (_result("mul"), _literal(values[2])),
                    "Number", SCOPE))
        limited = _execute(two, numeric, budget=DAGBudget(max_operations=1))
        self.assertEqual(limited.answer.state, ValueState.UNRESOLVED)
        self.assertEqual(limited.receipt.operation_count, 1)
        self.assertEqual(limited.receipt.unresolved_signature, "add:Number")

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

    def test_depth_node_and_decision_limits_reject_before_compute(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        first = DAGNode(
            "first", "ADD", (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE)
        second = DAGNode(
            "second", "ADD", (_result("first"), _literal(values[1])),
            "Number", SCOPE)
        program = _program(first, second)
        for budget in (
            DAGBudget(max_depth=1), DAGBudget(max_nodes=1)):
            with self.subTest(budget=budget):
                with self.assertRaises(BilqisError):
                    _execute(program, binding, budget=budget)
        holes = _program(
            DAGNode(
                "first", None, (_literal(values[0]), _literal(values[1])),
                "Number", SCOPE, candidate_operator_ids=("ADD", "SUB")),
            DAGNode(
                "second", None, (_result("first"), _literal(values[1])),
                "Number", SCOPE, candidate_operator_ids=("ADD", "SUB")),
        )
        with self.assertRaises(BilqisError):
            _execute(holes, binding, budget=DAGBudget(max_decisions=1))

    def test_nonvalue_frame_binding_never_becomes_a_computed_value(self):
        from bilqis_mlx.semantics.frame_schema import BindingState
        for state in (BindingState.NONE, BindingState.UNKNOWN,
                      BindingState.ALTERNATIVES):
            with self.subTest(state=state):
                binding, _ = _case()
                binding, frame, _ = _with_frame(binding, state=state)
                ref = DAGOperand(
                    RefKind.INPUT, "ConceptRef", frame_handle="frame:one",
                    frame_occurrence_id=frame.occurrence_id,
                    role_id="subject", occurrence_index=0)
                program = _program(DAGNode(
                    "types", "TYPE_OF", (ref,), "TypeSet", SCOPE))
                result = _execute(program, binding)
                self.assertEqual(result.answer.state, ValueState.UNRESOLVED)
                self.assertEqual(result.receipt.operation_count, 0)
                self.assertEqual(result.receipt.unresolved_signature,
                                 "types:TypeSet")

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
