from unittest import TestCase
from bilqis_mlx.semantics.tests._cognitive_dag_fixtures import *  # noqa: F403

class MemoTests(TestCase):
    def test_remaining_compute_limit_allows_only_verified_memo_at_zero(self):
        binding, values = _case(("Number", 2), ("Number", 3))
        goal = _goal(_program(DAGNode(
            "answer", "ADD", (_literal(values[0]), _literal(values[1])),
            "Number", SCOPE)), binding)
        memo = PureOperationMemo()
        missed = execute_dag(goal, binding, memo=memo, operation_limit=0)
        self.assertEqual(missed.answer.state, ValueState.UNRESOLVED)
        self.assertEqual(missed.receipt.operation_count, 0)
        self.assertEqual(execute_dag(goal, binding, memo=memo).answer.value, 5)
        hit = execute_dag(goal, binding, memo=memo, operation_limit=0)
        self.assertEqual(hit.answer.value, 5)
        self.assertEqual((hit.receipt.operation_count, hit.receipt.memo_hit_count),
                         (0, 1))
        with self.assertRaises(BilqisError):
            execute_dag(None, binding, operation_limit=0)
        for invalid in (-1, True, 1.5, 65):
            with self.subTest(limit=invalid), self.assertRaises(BilqisError):
                execute_dag(goal, binding, operation_limit=invalid)

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

