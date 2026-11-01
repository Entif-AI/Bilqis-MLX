"""Semantic-frame numeric decoder equivalent to frozen source ABI codec."""
from __future__ import annotations
from .core import Apply, Literal
from . import source_numeric_errors as errors
from .numeric import (OPERATIONS, SET_SYMBOL, GROUPS_SYMBOL, calculate, evaluate, number, number_set)
MAX_CONTEXT = 96
MIN_CONTEXT = 3
MAX_INSPECTION_DEPTH = MAX_CONTEXT

def _validate_groups(expression, groups):
    query = expression.arguments[0] if isinstance(expression, Apply) and expression.operator.symbol == "school.op.EQ" else expression
    if not isinstance(query, Apply) or query.operator.symbol not in ("school.op.MUL", "school.op.DIV"):
        raise ValueError(errors.NUMERIC_GROUP_CONTEXT_REQUIRES_PRODUCT_OR_QUOTIENT)
    a, b = (evaluate(child) for child in query.arguments)
    seen = set()
    for group in groups:
        number_set(tuple(group))
        if len(group) != b or seen.intersection(group):
            raise ValueError(errors.NUMERIC_GROUPS_NOT_EQUAL_AND_DISJOINT)
        seen.update(group)
    expected_count = a if query.operator.symbol.endswith("MUL") else evaluate(query)
    if len(groups) != expected_count or seen != set(range(a*b if query.operator.symbol.endswith("MUL") else a)):
        raise ValueError(errors.NUMERIC_GROUPS_NOT_EXHAUSTIVE)


def decode(symbols: list[str]) -> Literal | Apply:
    if (not isinstance(symbols, list) or not MIN_CONTEXT <= len(symbols) <= MAX_CONTEXT or
            symbols[0] != "school.syntax.math"):
        raise ValueError(errors.NUMERIC_CODEC_INVALID_INPUT)
    cursor = 1

    def visit(depth=0):
        nonlocal cursor
        if cursor >= len(symbols) or depth > MAX_INSPECTION_DEPTH:
            raise ValueError(errors.NUMERIC_CODEC_INCOMPLETE)
        symbol = symbols[cursor]
        cursor += 1
        if symbol.startswith("school.number."):
            value = symbol.removeprefix("school.number.")
            if not value.isdecimal() or str(int(value)) != value:
                raise ValueError(errors.NUMERIC_CODEC_LITERAL_INVALID)
            return number(int(value))
        if symbol == SET_SYMBOL:
            members = []
            while cursor < len(symbols) and symbols[cursor] != "syntax.end":
                item = visit(depth+1)
                if not isinstance(item, Literal) or item.type_name != "Number":
                    raise ValueError(errors.NUMERIC_CODEC_SET_MEMBER_TYPE)
                members.append(evaluate(item))
            if cursor >= len(symbols):
                raise ValueError(errors.NUMERIC_CODEC_SET_UNCLOSED)
            cursor += 1
            return number_set(tuple(members))
        name = symbol.removeprefix("school.op.")
        op = OPERATIONS.get(name)
        if op is None or symbol != op.symbol:
            raise ValueError(errors.NUMERIC_CODEC_UNKNOWN_OPERATOR)
        return calculate(name, *(visit(depth+1) for _ in op.signature.inputs))

    groups = None
    if symbols[cursor] == GROUPS_SYMBOL:
        cursor += 1
        groups = []
        while cursor < len(symbols) and symbols[cursor] != "syntax.end":
            group = visit()
            if not isinstance(group, Literal) or group.type_name != "NumberSet":
                raise ValueError(errors.NUMERIC_GROUP_CONTEXT_TYPE)
            import json
            groups.append(tuple(json.loads(group.value)))
        if cursor >= len(symbols):
            raise ValueError(errors.NUMERIC_GROUP_CONTEXT_UNCLOSED)
        cursor += 1
    expression = visit()
    if cursor != len(symbols)-1 or symbols[cursor] != "syntax.end":
        raise ValueError(errors.NUMERIC_CODEC_TRAILING_OR_MISSING_END)
    evaluate(expression)
    if groups is not None:
        _validate_groups(expression, groups)
    return expression
