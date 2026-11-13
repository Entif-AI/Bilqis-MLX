"""Immutable typed semantic expression AST; no source, oracle or grade policy."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

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
