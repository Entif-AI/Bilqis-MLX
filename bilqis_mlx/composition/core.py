"""A compact, pure algebra for typed, inspectable functional composition.

This file contains no semantic definitions and knows no grade names. All
semantic identities and signatures must be supplied by the canonical catalog.
Source-specific interpreters and learning policy are separate adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Callable, Protocol


_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")


class TypedError(ValueError):
    """A stable, diagnosable composition-contract failure."""


def _type_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise TypedError("COMPOSITION_INVALID_TYPE_NAME")
    return name


@dataclass(frozen=True)
class Signature:
    inputs: tuple[str, ...]
    output: str

    def __post_init__(self) -> None:
        if not self.inputs:
            raise TypedError("COMPOSITION_ARITY_ZERO_UNSUPPORTED")
        for name in (*self.inputs, self.output):
            _type_name(name)

    @classmethod
    def parse(cls, text: str) -> "Signature":
        if not isinstance(text, str) or text.count("->") != 1:
            raise TypedError("COMPOSITION_INVALID_SIGNATURE")
        left, right = text.split("->")
        return cls(tuple(left.split("*")), right)


@dataclass(frozen=True)
class Operation:
    """A token index is assigned by the catalog, never this module."""

    token_index: int
    symbol: str
    signature: Signature
    contract_sha256: str
    world_contract: str | None = None

    def __post_init__(self) -> None:
        if type(self.token_index) is not int or self.token_index < 0:
            raise TypedError("COMPOSITION_INVALID_CATALOG_ID")
        if not self.symbol or not isinstance(self.symbol, str):
            raise TypedError("COMPOSITION_INVALID_SYMBOL")
        if (not re.fullmatch(r"[0-9a-f]{64}", self.contract_sha256) or
                self.world_contract == ""):
            raise TypedError("COMPOSITION_INVALID_SOURCE_CONTRACT")


@dataclass(frozen=True)
class Literal:
    value: str | bool
    type_name: str
    world_contract: str | None = None

    def __post_init__(self) -> None:
        _type_name(self.type_name)
        if not isinstance(self.value, (str, bool)) or self.world_contract == "":
            raise TypedError("COMPOSITION_INVALID_LITERAL")
        if self.type_name == "Boolean" and type(self.value) is not bool:
            raise TypedError("COMPOSITION_BOOLEAN_LITERAL_TYPE_DRIFT")


@dataclass(frozen=True)
class Apply:
    operator: Operation
    arguments: tuple["Expression", ...]
    type_name: str
    world_contract: str | None

    def __post_init__(self) -> None:
        if (len(self.arguments) != len(self.operator.signature.inputs) or
                self.type_name != self.operator.signature.output):
            raise TypedError("COMPOSITION_INVALID_APPLICATION")
        if any(arg.type_name != required
               for arg, required in zip(self.arguments, self.operator.signature.inputs)):
            raise TypedError("COMPOSITION_INVALID_APPLICATION_TYPES")
        if self.world_contract != _world(self.operator, self.arguments):
            raise TypedError("COMPOSITION_INVALID_APPLICATION_WORLD")


Expression = Literal | Apply


class Catalog:
    """Read-only binding of upstream/canonical-assigned ID to typed operator."""

    def __init__(self, definitions: tuple[Operation, ...]):
        ids = [item.token_index for item in definitions]
        symbols = [item.symbol for item in definitions]
        if len(set(ids)) != len(ids) or len(set(symbols)) != len(symbols):
            raise TypedError("COMPOSITION_DUPLICATE_CATALOG_BINDING")
        self._by_id = {item.token_index: item for item in definitions}
        self._by_symbol = {item.symbol: item.token_index for item in definitions}

    def get(self, original_token_id: int) -> Operation:
        if type(original_token_id) is not int:
            raise TypedError("COMPOSITION_INVALID_CATALOG_ID")
        try:
            return self._by_id[original_token_id]
        except KeyError as exc:
            raise TypedError("COMPOSITION_UNKNOWN_CATALOG_ID") from exc

    def resolve_external_name(self, original_symbol: str) -> Operation:
        """For ingress only. Internals use original catalog-assigned token ID."""
        try:
            return self.get(self._by_symbol[original_symbol])
        except KeyError as exc:
            raise TypedError("COMPOSITION_UNKNOWN_EXTERNAL_ALIAS") from exc


def literal(value: str | bool, type_name: str,
            *, world_contract: str | None = None) -> Literal:
    return Literal(value, type_name, world_contract)


def _world(operation: Operation, arguments: tuple[Expression, ...]) -> str | None:
    worlds = {arg.world_contract for arg in arguments
              if arg.world_contract is not None}
    if operation.world_contract is not None:
        worlds.add(operation.world_contract)
    if len(worlds) > 1:
        raise TypedError("COMPOSITION_INCOMPATIBLE_WORLD_CONTRACT")
    return next(iter(worlds)) if worlds else None


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


def _canonical(expression: Expression) -> dict:
    if isinstance(expression, Literal):
        return {"kind": "literal", "type": expression.type_name,
                "value": expression.value, "world": expression.world_contract}
    return {"kind": "apply", "token_index": expression.operator.token_index,
            "source_contract": expression.operator.contract_sha256,
            "result": expression.type_name, "world": expression.world_contract,
            "arguments": [_canonical(child) for child in expression.arguments]}


def expression_digest(expression: Expression) -> str:
    payload = json.dumps(_canonical(expression), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


class Backend(Protocol):
    identity: str

    def invoke(self, operation: Operation, values: tuple[str | bool, ...],
               world_contract: str | None) -> str | bool: ...


def _evaluate(expression: Expression, backend: Backend) -> str | bool:
    if isinstance(expression, Literal):
        return expression.value
    values = tuple(_evaluate(child, backend) for child in expression.arguments)
    return backend.invoke(expression.operator, values, expression.world_contract)


@dataclass(frozen=True)
class Proof:
    expression_sha256: str
    source_backend: str
    independent_backend: str
    result: str | bool
    world_contract: str | None
    status: str = "VERIFIED"


def verify(expression: Expression, *, source: Backend,
           independent: Backend) -> Proof:
    """Check two independently identified interpreters, never assume gold."""
    if (not isinstance(expression, Apply) or
            source.identity == independent.identity or
            not source.identity or not independent.identity):
        raise TypedError("COMPOSITION_INDEPENDENT_PROOF_REQUIRED")
    result = _evaluate(expression, source)
    other = _evaluate(expression, independent)
    if type(result) is not type(other) or result != other:
        raise TypedError("COMPOSITION_ORACLE_DISAGREEMENT")
    if expression.type_name == "Boolean" and type(result) is not bool:
        raise TypedError("COMPOSITION_ANSWER_TYPE_DRIFT")
    return Proof(expression_digest(expression), source.identity,
                 independent.identity, result, expression.world_contract)
