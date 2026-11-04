from unittest import TestCase
from bilqis_mlx.semantics.tests._cognitive_dag_fixtures import *  # noqa: F403

class ContractsTests(TestCase):
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
