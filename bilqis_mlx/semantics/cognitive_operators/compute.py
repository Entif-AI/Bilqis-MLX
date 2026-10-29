"""Deterministic source-owned operator evaluation after authorization."""
from __future__ import annotations
from fractions import Fraction
from .. import numeric as released_numeric
from ..frame_schema import BindingState
from .authorization import _frame
from .common import _NATIVE_NUMERIC, _SOURCE_INAPPLICABLE, _invalid
from .registry import OperatorBinding
from .types import Duration, SourceKind, ValueState

_UNSUPPORTED = object()
_UNKNOWN = object()
_NONE = object()


def _evaluate_native_numeric(expression) -> object:
    """Use the pure source implementation, not evaluator-owned memoization."""
    source_function = getattr(released_numeric, "evaluate_pure", None)
    if (not callable(source_function)
            or source_function.__module__ != "bilqis_mlx.semantics.numeric"
            or source_function.__qualname__ != "evaluate_pure"):
        _invalid("BAMF_OPERATOR_NATIVE_RUNTIME_UNAVAILABLE")
    return source_function(expression)


def _compute(operator_id: str, values: tuple[object, ...],
             binding: OperatorBinding) -> object:
    if operator_id == "ROLE_LOOKUP":
        handle, role, index = values
        frame = _frame(handle, binding)
        if frame is None:
            return _UNSUPPORTED
        occupant = next((item for item in frame.bindings
                         if item.key == (role, index)), None)
        if (occupant is None or occupant.state in (
                BindingState.UNKNOWN, BindingState.ALTERNATIVES)):
            return _UNKNOWN
        if occupant.state is BindingState.NONE:
            return _NONE
        return occupant.concept if occupant.concept is not None else _UNSUPPORTED
    if operator_id == "SAME_IDENTITY":
        left, right = values
        return (left.semantic_id, left.semantic_release, left.abi_index) == (
            right.semantic_id, right.semantic_release, right.abi_index)
    if operator_id == "TYPE_OF":
        return values[0].type_ids
    if operator_id == "HAS_TYPE":
        return values[1] in values[0].type_ids
    if operator_id == "MEMBER_OF":
        return values[0] in values[1]
    if operator_id == "BOOL_NOT":
        return not values[0]
    if operator_id == "BOOL_AND":
        return values[0] and values[1]
    if operator_id == "BOOL_OR":
        return values[0] or values[1]
    if operator_id == "BOOL_XOR":
        return values[0] != values[1]
    if operator_id == "BOOL_IMPLIES":
        return not values[0] or values[1]
    if operator_id == "BOOL_IFF":
        return values[0] == values[1]
    if operator_id == "IS_OCCURRED":
        return values[0] == "OCCURRED"
    if operator_id == "PARENT_OF":
        parent, child = (_frame(handle, binding) for handle in values)
        return (child.parent_occurrence_id == parent.occurrence_id
                if parent is not None and child is not None else _UNSUPPORTED)
    if operator_id == "BEFORE":
        left, right = (_frame(handle, binding) for handle in values)
        return (left.source_span.end <= right.source_span.start
                if left is not None and right is not None else _UNSUPPORTED)
    if operator_id == "UNIT_CONVERT":
        duration, target = values
        edge = next((
            item.typed.value for item in binding.operands
            if item.kind is SourceKind.ADMITTED_KNOWLEDGE
            and item.typed.type_name == "UnitConversion"
            and item.typed.state is ValueState.VALUE
            and item.typed.value.from_unit == duration.unit
            and item.typed.value.to_unit == target
        ), None)
        if edge is None:
            return _UNSUPPORTED
        quantity = (Fraction(duration.numerator, duration.denominator)
                    * Fraction(edge.numerator, edge.denominator))
        return Duration(quantity.numerator, quantity.denominator, target)
    if operator_id == "COUNT":
        return len(values[0])
    if operator_id in _NATIVE_NUMERIC:
        try:
            expression = released_numeric.calculate(
                operator_id, *(released_numeric.number(value) for value in values))
            return _evaluate_native_numeric(expression)
        except ValueError as exc:
            if str(exc) in _SOURCE_INAPPLICABLE:
                return _UNSUPPORTED
            _invalid("BAMF_OPERATOR_SOURCE_EXECUTION_DRIFT")
    if operator_id in {"ADD", "SUB", "MUL", "DIV", "MOD", "EQ", "LT", "LE"}:
        left, right = values
        if operator_id == "ADD":
            return left + right
        if operator_id == "SUB":
            return left - right
        if operator_id == "MUL":
            return left * right
        if operator_id == "EQ":
            return left == right
        if operator_id == "LT":
            return left < right
        if operator_id == "LE":
            return left <= right
        if right == 0:
            return _UNSUPPORTED
        if operator_id == "MOD":
            return left % right
        return left // right if left % right == 0 else _UNSUPPORTED
    _invalid("BAMF_OPERATOR_UNIMPLEMENTED")


