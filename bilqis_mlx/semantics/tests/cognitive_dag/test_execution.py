from unittest import TestCase
from bilqis_mlx.semantics.tests._cognitive_dag_fixtures import *  # noqa: F403

class ExecutionTests(TestCase):
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
            "bilqis_mlx.semantics._cognitive_dag.execution._compute_after_authorization",
            side_effect=AssertionError("computed before source validation"),
        ):
            with self.assertRaises(BilqisError):
                _execute(program, revoked)

