"""DAG memo ownership."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade
from ..cognitive_dag import (
    DAGOperand, DAGProgram, DAGBudget, DAGNode, TaskGoal, DAGResult, DAGReceipt,
    OperatorBinding, TypedValue, PureOperationMemo,
)


def _public():
    return public_facade("bilqis_mlx.semantics.cognitive_dag")


def _memo_get_verified(memo: PureOperationMemo, key: str) -> TypedValue | None:
    """Only executor-computed values have an independent local witness."""
    value = memo.get(key)
    if value is None:
        return None
    if not isinstance(value, _public().TypedValue):
        _public()._invalid("BAMF_DAG_MEMO_VALUE_INVALID")
    with _public()._MEMO_WITNESS_LOCK:
        expected = _public()._MEMO_WITNESSES.get(memo, {}).get(key)
    return value if expected == _public().contract_digest(value) else None


def _memo_put_verified(
    memo: PureOperationMemo, key: str, value: TypedValue,
) -> None:
    memo.put(key, value)
    with _public()._MEMO_WITNESS_LOCK:
        _public()._MEMO_WITNESSES.setdefault(memo, {})[key] = _public().contract_digest(value)


def _grant_record(handle: str, binding: OperatorBinding):
    grant = next(
        (item for item in binding.frontier.grants
         if item.source_handle == handle), None)
    if grant is None:
        _public()._invalid("BAMF_DAG_MEMO_SOURCE_GRANT_MISSING")
    return grant


def _dependency_record(
    ref: DAGOperand, value: TypedValue, binding: OperatorBinding,
    lineage: dict[str, str],
) -> tuple:
    if ref.kind is _public().RefKind.RESULT:
        return (ref.identity, value, lineage[ref.result_node_id])
    if ref.kind is _public().RefKind.LITERAL:
        source = next(
            item for item in binding.operands
            if item.typed.source_handle == ref.source_handle)
        return (ref.identity, value, source,
                _public()._grant_record(ref.source_handle, binding))
    envelope = next(
        item for item in binding.frames
        if item.frame_handle == ref.frame_handle)
    member = next(
        item for item in envelope.members
        if (item.role_id, item.occurrence_index)
        == (ref.role_id, ref.occurrence_index))
    return (
        ref.identity, value, envelope, member,
        _public()._grant_record(envelope.source_handle, binding),
        _public()._grant_record(member.source_handle, binding))


def _consulted_dependencies(
    operator_id: str, inputs: tuple[TypedValue, ...],
    binding: OperatorBinding,
) -> tuple:
    """Memo identity includes source data read *inside* the operator."""
    if operator_id == "UNIT_CONVERT":
        duration, target = (value.value for value in inputs)
        edge = next((
            item for item in binding.operands
            if item.kind is _public().SourceKind.ADMITTED_KNOWLEDGE
            and item.typed.type_name == "UnitConversion"
            and item.typed.state is _public().ValueState.VALUE
            and item.typed.value.from_unit == duration.unit
            and item.typed.value.to_unit == target
        ), None)
        if edge is None:
            return (("unit-edge-absent", duration.unit, target),)
        return (("unit-edge", edge,
                 _public()._grant_record(edge.typed.source_handle, binding)),)
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
                _public()._grant_record(envelope.source_handle, binding),
                tuple(_public()._grant_record(member.source_handle, binding)
                      for member in envelope.members)))
        return tuple(consulted)
    return ()
