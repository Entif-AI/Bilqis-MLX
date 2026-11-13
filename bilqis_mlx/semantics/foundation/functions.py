"""Inspectable higher-order functional composition over typed ASTs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .core import Apply, Expression, Literal, Operation, TypedError, _world

@dataclass(frozen=True)
class Curried:
    operation: Operation
    bound: tuple[tuple[int, Expression], ...] = ()

    def __post_init__(self) -> None:
        slots = [slot for slot, _ in self.bound]
        if (slots != sorted(set(slots)) or
                any(type(slot) is not int or slot < 0 or
                    slot >= len(self.operation.signature.inputs)
                    for slot in slots)):
            raise TypedError("COMPOSITION_INVALID_CURRIED_BINDINGS")
        for slot, expression in self.bound:
            if (not isinstance(expression, (Literal, Apply)) or
                    expression.type_name != self.operation.signature.inputs[slot]):
                raise TypedError("COMPOSITION_ARGUMENT_TYPE_MISMATCH")
        _world(self.operation, tuple(expr for _, expr in self.bound))

    def __call__(self, *expressions: Expression) -> "Curried | Apply":
        if not expressions:
            return self
        mapping = dict(self.bound)
        for expression in expressions:
            open_slots = (slot for slot in range(len(self.operation.signature.inputs))
                          if slot not in mapping)
            slot = next(open_slots, None)
            if slot is None:
                raise TypedError("COMPOSITION_TOO_MANY_ARGUMENTS")
            if not isinstance(expression, (Apply, Literal)):
                raise TypedError("COMPOSITION_NOT_TYPED_EXPRESSION")
            if expression.type_name != self.operation.signature.inputs[slot]:
                raise TypedError("COMPOSITION_ARGUMENT_TYPE_MISMATCH")
            mapping[slot] = expression
        bound = tuple(sorted(mapping.items()))
        if len(bound) < len(self.operation.signature.inputs):
            return Curried(self.operation, bound)
        arguments = tuple(expression for _, expression in bound)
        return Apply(self.operation, arguments,
                     self.operation.signature.output, _world(self.operation, arguments))


def curry(operation: Operation) -> Curried:
    return Curried(operation)


def partial_apply(operation: Operation, *, bound: dict[int, Expression]) -> Curried | Apply:
    """Bind arbitrary argument positions without changing their AST identity."""
    if not isinstance(bound, dict) or not bound:
        raise TypedError("COMPOSITION_PARTIAL_BINDINGS_REQUIRED")
    if any(type(slot) is not int or slot not in range(len(operation.signature.inputs))
           for slot in bound):
        raise TypedError("COMPOSITION_PARTIAL_SLOT_OUT_OF_RANGE")
    for slot, expression in bound.items():
        if not isinstance(expression, (Apply, Literal)) or (
                expression.type_name != operation.signature.inputs[slot]):
            raise TypedError("COMPOSITION_ARGUMENT_TYPE_MISMATCH")
    ordered = tuple(sorted(bound.items()))
    if len(ordered) == len(operation.signature.inputs):
        args = tuple(expr for _, expr in ordered)
        return Apply(operation, args, operation.signature.output, _world(operation, args))
    return Curried(operation, ordered)


def lift2(operation: Operation) -> Callable[[Expression], Callable[[Expression], Apply]]:
    """Curried binary lift. Each application yields inspectable typed nodes."""
    if len(operation.signature.inputs) != 2:
        raise TypedError("COMPOSITION_LIFT_REQUIRES_BINARY_OPERATOR")

    def first(left: Expression) -> Callable[[Expression], Apply]:
        part = curry(operation)(left)
        if not isinstance(part, Curried):
            raise TypedError("COMPOSITION_INTERNAL_LIFT_CONTRACT")

        def second(right: Expression) -> Apply:
            result = part(right)
            if not isinstance(result, Apply):
                raise TypedError("COMPOSITION_INTERNAL_LIFT_CONTRACT")
            return result

        return second

    return first


def compose(outer: Operation, inner: Operation):
    """Function composition, with immutable application AST at invocation."""
    if len(outer.signature.inputs) != 1 or (
            outer.signature.inputs[0] != inner.signature.output):
        raise TypedError("COMPOSITION_UNIFICATION_FAILED")

    def composed(*arguments: Expression) -> Apply:
        inside = curry(inner)(*arguments)
        if not isinstance(inside, Apply):
            raise TypedError("COMPOSITION_INNER_NOT_FULLY_APPLIED")
        outside = curry(outer)(inside)
        if not isinstance(outside, Apply):
            raise TypedError("COMPOSITION_OUTER_NOT_FULLY_APPLIED")
        return outside

    return composed
