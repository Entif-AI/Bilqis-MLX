"""Scoped finite-number semantics on the shared, inspectable typed AST.

NumberSet contains Number identities; it never reinterprets legacy Entity.
Teaching bounds belong to a release, separate from this preserved number ABI.
"""
from __future__ import annotations

import json
from pathlib import Path

from .core import Apply, Literal, Operation, Signature, literal
from .functions import curry


CONTRACT_PATH = Path(__file__).with_name("numeric_v1.json")
CONTRACT = json.loads(CONTRACT_PATH.read_text())
OPERATIONS = {row["symbol"].removeprefix("school.op."): Operation(
    row["token_index"], row["symbol"], Signature.parse(row["signature"]),
    row["contract_sha256"]) for row in CONTRACT["operators"]
    if "->" in row["signature"] and row["symbol"] != "school.op.MOD"}
SET_SYMBOL = "school.syntax.number_set"
GROUPS_SYMBOL = "school.syntax.number_groups"
NUMBER_MAX = 100  # scalar domain of the historical school.number catalog


def number(value: int) -> Literal:
    if type(value) is not int or not 0 <= value <= NUMBER_MAX:
        raise ValueError("NUMERIC_LITERAL_OUTSIDE_SOURCE_ABI")
    return literal(str(value), "Number")


def number_set(members: tuple[int, ...]) -> Literal:
    if not isinstance(members, tuple) or len(set(members)) != len(members):
        raise ValueError("NUMERIC_SET_DUPLICATE_OR_UNTYPED_MEMBERS")
    for member in members:
        number(member)
    return literal(json.dumps(members, separators=(",", ":")), "NumberSet")


def calculate(name: str, *arguments: Literal | Apply) -> Apply:
    if name not in OPERATIONS:
        raise ValueError("NUMERIC_OPERATOR_NOT_IN_RELEASE")
    result = curry(OPERATIONS[name])(*arguments)
    if not isinstance(result, Apply):
        raise ValueError("NUMERIC_OPERATOR_INCOMPLETE")
    return result


def evaluate(expression: Literal | Apply):
    if isinstance(expression, Literal):
        if expression.type_name == "Number":
            value = int(expression.value)
            if number(value) != expression:
                raise ValueError("NUMERIC_NONCANONICAL_LITERAL")
            return value
        if expression.type_name == "NumberSet":
            members = tuple(json.loads(expression.value))
            if number_set(members) != expression:
                raise ValueError("NUMERIC_NONCANONICAL_SET")
            return frozenset(members)
        raise ValueError("NUMERIC_UNSUPPORTED_LITERAL_TYPE")
    name = expression.operator.symbol.removeprefix("school.op.")
    if expression.operator != OPERATIONS.get(name):
        raise ValueError("NUMERIC_OPERATOR_CONTRACT_DRIFT")
    args = tuple(evaluate(child) for child in expression.arguments)
    if name == "COUNT":
        result = len(args[0])
    elif name == "SUCC":
        result = args[0] + 1
    elif name == "DIV":
        a, b = args
        if b == 0 or a % b:
            raise ValueError("NUMERIC_EXACT_DIVISION_UNDEFINED")
        result = a // b
    else:
        a, b = args
        if name == "ADD": result = a + b
        elif name == "SUB": result = a - b
        elif name == "MUL": result = a * b
        elif name == "EQ": return a == b
        elif name == "LT": return a < b
        elif name == "LE": return a <= b
        elif name == "MOD":
            if b == 0:
                raise ValueError("NUMERIC_MODULO_UNDEFINED")
            result = a % b
        else:
            raise ValueError("NUMERIC_OPERATOR_NOT_IMPLEMENTED")
    number(result)
    return result
