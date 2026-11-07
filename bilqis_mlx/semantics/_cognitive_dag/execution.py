"""Source-bound DAG execution, memo lineage and provenance closure."""
from __future__ import annotations

from threading import RLock
from weakref import WeakKeyDictionary

from ..cognitive_operators.authorization import (
    _check_grant, _independent_applicability, _number_domain,
)
from ..cognitive_operators.execution import _compute_after_authorization
from ..cognitive_operators.registry import OperatorBinding, operator_grant_digest
from ..cognitive_operators.types import SourceKind, TypedValue, ValueState
from ..foundation.domains import contract_digest
from ..foundation.memo import PureOperationMemo
from .contracts import DAGOperand, RefKind, _invalid
from .goals import DAGReceipt, DAGResult, TaskGoal
from .prepare import _prepare

_MEMO_WITNESS_LOCK = RLock()
_MEMO_WITNESSES: WeakKeyDictionary[PureOperationMemo, dict[str, str]] = WeakKeyDictionary()


def _memo_get_verified(memo: PureOperationMemo, key: str) -> TypedValue | None:
    """Only executor-computed values have an independent local witness."""
    value = memo.get(key)
    if value is None:
        return None
    if not isinstance(value, TypedValue):
        _invalid("BAMF_DAG_MEMO_VALUE_INVALID")
    with _MEMO_WITNESS_LOCK:
        expected = _MEMO_WITNESSES.get(memo, {}).get(key)
    return value if expected == contract_digest(value) else None


def _memo_put_verified(
    memo: PureOperationMemo, key: str, value: TypedValue,
) -> None:
    memo.put(key, value)
    with _MEMO_WITNESS_LOCK:
        _MEMO_WITNESSES.setdefault(memo, {})[key] = contract_digest(value)

def _grant_record(handle: str, binding: OperatorBinding):
    grant = next(
        (item for item in binding.frontier.grants
         if item.source_handle == handle), None)
    if grant is None:
        _invalid("BAMF_DAG_MEMO_SOURCE_GRANT_MISSING")
    return grant


def _dependency_record(
    ref: DAGOperand, value: TypedValue, binding: OperatorBinding,
    lineage: dict[str, str],
) -> tuple:
    if ref.kind is RefKind.RESULT:
        return (ref.identity, value, lineage[ref.result_node_id])
    if ref.kind is RefKind.LITERAL:
        source = next(
            item for item in binding.operands
            if item.typed.source_handle == ref.source_handle)
        return (ref.identity, value, source,
                _grant_record(ref.source_handle, binding))
    envelope = next(
        item for item in binding.frames
        if item.frame_handle == ref.frame_handle)
    member = next(
        item for item in envelope.members
        if (item.role_id, item.occurrence_index)
        == (ref.role_id, ref.occurrence_index))
    return (
        ref.identity, value, envelope, member,
        _grant_record(envelope.source_handle, binding),
        _grant_record(member.source_handle, binding))


def _consulted_dependencies(
    operator_id: str, inputs: tuple[TypedValue, ...],
    binding: OperatorBinding,
) -> tuple:
    """Memo identity includes source data read *inside* the operator."""
    if operator_id == "UNIT_CONVERT":
        duration, target = (value.value for value in inputs)
        edge = next((
            item for item in binding.operands
            if item.kind is SourceKind.ADMITTED_KNOWLEDGE
            and item.typed.type_name == "UnitConversion"
            and item.typed.state is ValueState.VALUE
            and item.typed.value.from_unit == duration.unit
            and item.typed.value.to_unit == target
        ), None)
        if edge is None:
            return (("unit-edge-absent", duration.unit, target),)
        return (("unit-edge", edge,
                 _grant_record(edge.typed.source_handle, binding)),)
    if operator_id in {"ROLE_LOOKUP", "PARENT_OF", "BEFORE"}:
        handles = (
            (inputs[0].value,) if operator_id == "ROLE_LOOKUP"
            else tuple(value.value for value in inputs))
        consulted = []
        for handle in handles:
            envelope = next((
                item for item in binding.frames
                if item.frame_handle == handle
            ), None)
            if envelope is None:
                consulted.append(("frame-absent", handle))
                continue
            consulted.append((
                "frame", envelope,
                _grant_record(envelope.source_handle, binding),
                tuple(_grant_record(member.source_handle, binding)
                      for member in envelope.members)))
        return tuple(consulted)
    return ()


def execute_dag(
    goal: TaskGoal,
    binding: OperatorBinding,
    *,
    memo: PureOperationMemo | None = None,
    operation_limit: int | None = None,
) -> DAGResult:
    """Run one fully source-validated typed DAG without neural or gold inputs."""
    if memo is not None and not isinstance(memo, PureOperationMemo):
        _invalid("BAMF_DAG_MEMO_INVALID")
    order, prepared, visible, selected, unresolved = _prepare(goal, binding)
    if operation_limit is not None and (
            type(operation_limit) is not int
            or not 0 <= operation_limit <= goal.budget.max_operations):
        _invalid("BAMF_DAG_OPERATION_LIMIT_INVALID")
    program = goal.expression_or_holes
    compute_limit = (goal.budget.max_operations if operation_limit is None
                     else operation_limit)
    release = binding.task.semantic_release
    source_digest = contract_digest(binding)
    output_type = next(
        node.expected_output_type for node in program.nodes
        if node.node_id == program.output_node_id)
    computed = 0
    lookups = 0
    hits = 0
    executed: list[str] = []

    def finish(answer: TypedValue, reason: str | None = None) -> DAGResult:
        return DAGResult(answer, DAGReceipt(
            release, source_digest, computed, lookups, hits,
            selected, tuple(executed), reason))

    def unresolved_answer(node_id: str, type_name: str) -> DAGResult:
        return finish(
            TypedValue(output_type, None, release, state=ValueState.UNRESOLVED),
            node_id + ":" + type_name)

    if unresolved is not None:
        return finish(
            TypedValue(output_type, None, release, state=ValueState.UNRESOLVED),
            unresolved)

    results: dict[str, TypedValue] = {}
    lineage: dict[str, str] = {}
    for node in order:
        spec, refs = prepared[node.node_id]
        _check_grant(
            "source:operator:" + spec.operator_id,
            operator_grant_digest(spec), binding)
        numeric = (
            _number_domain(binding)
            if spec.applicability == "FINITE_NUMBER" else None)
        inputs = tuple(
            results[ref.result_node_id] if ref.kind is RefKind.RESULT
            else visible[ref.identity]
            for ref in refs)
        if any(value.state is not ValueState.VALUE for value in inputs):
            return unresolved_answer(node.node_id, node.expected_output_type)
        if (node.operator_id is None
                and _independent_applicability(
                    spec, inputs, binding) is False):
            return unresolved_answer(node.node_id, node.expected_output_type)
        dependencies = tuple(
            _dependency_record(ref, value, binding, lineage)
            for ref, value in zip(refs, inputs)) + _consulted_dependencies(
                spec.operator_id, inputs, binding)
        authority = (
            binding.task, binding.policy,
            binding.frontier.rights_epoch,
            binding.frontier.correction_generation,
            _grant_record("source:operator:" + spec.operator_id, binding),
            numeric,
            _grant_record(binding.numeric_source_handle, binding)
            if numeric is not None else None,
        )
        key = PureOperationMemo.key(
            operator=spec, dependencies=dependencies, authority=authority)
        cached = None
        if memo is not None:
            lookups += 1
            cached = _memo_get_verified(memo, key)
        if cached is None and computed >= compute_limit:
            return unresolved_answer(node.node_id, node.expected_output_type)
        if memo is None:
            lookups += 1
        if cached is not None:
            if (not isinstance(cached, TypedValue)
                    or cached.type_name != node.expected_output_type
                    or cached.semantic_release != release
                    or cached.state not in (
                        ValueState.VALUE, ValueState.NONE)
                    or cached.source_handle is not None):
                _invalid("BAMF_DAG_MEMO_VALUE_INVALID")
            hits += 1
            value = cached
        else:
            computed += 1
            value = _compute_after_authorization(spec, inputs, binding)
            if memo is not None and value.state in (
                    ValueState.VALUE, ValueState.NONE):
                _memo_put_verified(memo, key, value)
        results[node.node_id] = value
        lineage[node.node_id] = key
        executed.append(node.node_id)
        if value.state is not ValueState.VALUE and (
                node.node_id != program.output_node_id):
            return unresolved_answer(node.node_id, node.expected_output_type)
    return finish(results[program.output_node_id])
