"""Unambiguous, versioned numeric prefix codec over catalog token symbols."""
from __future__ import annotations

from ..semantics.core import Apply, Literal
from ..semantics.numeric import (OPERATIONS, SET_SYMBOL, GROUPS_SYMBOL,
                                calculate, evaluate, number, number_set)

DIALECT = "bilqis.finite-number-prefix/v1"
MAX_CONTEXT = 96


def _validate_groups(expression, groups):
    query = expression.arguments[0] if isinstance(expression, Apply) and expression.operator.symbol == "school.op.EQ" else expression
    if not isinstance(query, Apply) or query.operator.symbol not in ("school.op.MUL", "school.op.DIV"):
        raise ValueError("NUMERIC_GROUP_CONTEXT_REQUIRES_PRODUCT_OR_QUOTIENT")
    a, b = (evaluate(child) for child in query.arguments)
    seen = set()
    for group in groups:
        number_set(tuple(group))
        if len(group) != b or seen.intersection(group):
            raise ValueError("NUMERIC_GROUPS_NOT_EQUAL_AND_DISJOINT")
        seen.update(group)
    expected_count = a if query.operator.symbol.endswith("MUL") else evaluate(query)
    if len(groups) != expected_count or seen != set(range(a*b if query.operator.symbol.endswith("MUL") else a)):
        raise ValueError("NUMERIC_GROUPS_NOT_EXHAUSTIVE")


def encode(expression: Literal | Apply, *, groups=None) -> list[str]:
    def visit(node):
        if isinstance(node, Literal):
            value = evaluate(node)
            if node.type_name == "Number":
                return ["school.number." + str(value)]
            import json
            return [SET_SYMBOL, *("school.number." + str(n)
                    for n in json.loads(node.value)), "syntax.end"]
        return [node.operator.symbol, *(symbol for child in node.arguments
                                       for symbol in visit(child))]
    evaluate(expression)
    context = []
    if groups is not None:
        _validate_groups(expression, groups)
        context = [GROUPS_SYMBOL, *(symbol for group in groups
            for symbol in visit(number_set(tuple(group)))), "syntax.end"]
    result = ["school.syntax.math", *context, *visit(expression), "syntax.end"]
    if len(result) > MAX_CONTEXT:
        raise ValueError("NUMERIC_CODEC_CONTEXT_OVERFLOW")
    return result


def decode(symbols: list[str]) -> Literal | Apply:
    if (not isinstance(symbols, list) or not 3 <= len(symbols) <= MAX_CONTEXT or
            symbols[0] != "school.syntax.math"):
        raise ValueError("NUMERIC_CODEC_INVALID_INPUT")
    cursor = 1

    def visit(depth=0):
        nonlocal cursor
        if cursor >= len(symbols) or depth > MAX_CONTEXT:
            raise ValueError("NUMERIC_CODEC_INCOMPLETE")
        symbol = symbols[cursor]
        cursor += 1
        if symbol.startswith("school.number."):
            value = symbol.removeprefix("school.number.")
            if not value.isdecimal() or str(int(value)) != value:
                raise ValueError("NUMERIC_CODEC_LITERAL_INVALID")
            return number(int(value))
        if symbol == SET_SYMBOL:
            members = []
            while cursor < len(symbols) and symbols[cursor] != "syntax.end":
                item = visit(depth+1)
                if not isinstance(item, Literal) or item.type_name != "Number":
                    raise ValueError("NUMERIC_CODEC_SET_MEMBER_TYPE")
                members.append(evaluate(item))
            if cursor >= len(symbols):
                raise ValueError("NUMERIC_CODEC_SET_UNCLOSED")
            cursor += 1
            return number_set(tuple(members))
        name = symbol.removeprefix("school.op.")
        op = OPERATIONS.get(name)
        if op is None or symbol != op.symbol:
            raise ValueError("NUMERIC_CODEC_UNKNOWN_OPERATOR")
        return calculate(name, *(visit(depth+1) for _ in op.signature.inputs))

    groups = None
    if symbols[cursor] == GROUPS_SYMBOL:
        cursor += 1
        groups = []
        while cursor < len(symbols) and symbols[cursor] != "syntax.end":
            group = visit()
            if not isinstance(group, Literal) or group.type_name != "NumberSet":
                raise ValueError("NUMERIC_GROUP_CONTEXT_TYPE")
            import json
            groups.append(tuple(json.loads(group.value)))
        if cursor >= len(symbols):
            raise ValueError("NUMERIC_GROUP_CONTEXT_UNCLOSED")
        cursor += 1
    expression = visit()
    if cursor != len(symbols)-1 or symbols[cursor] != "syntax.end":
        raise ValueError("NUMERIC_CODEC_TRAILING_OR_MISSING_END")
    evaluate(expression)
    if groups is not None:
        _validate_groups(expression, groups)
    return expression


def inspect_record(record):
    """Project actual numerical query operations for the common S4/S5 observer."""
    from .structure import SourceExpressionShape
    if record.get("task") != DIALECT:
        raise ValueError("NUMERIC_WRONG_SOURCE_DIALECT")
    expression = decode(record["symbols"])
    if isinstance(expression, Apply) and expression.operator.symbol == "school.op.EQ":
        expression = expression.arguments[0]

    def visit(node, depth=1):
        if isinstance(node, Literal):
            if node.type_name == "Number":
                return ("school.number."+node.value,), 0, 0
            return (), 0, 0  # literal collection syntax is not an operator
        names, count, deepest = [node.operator.symbol], 1, depth
        for child in node.arguments:
            symbols, child_count, child_depth = visit(child, depth+1)
            names.extend(symbols)
            count += child_count
            deepest = max(deepest, child_depth)
        return tuple(names), count, deepest

    symbols, operations, depth = visit(expression)
    return SourceExpressionShape(symbols[0], symbols, operations, depth)


def check_numeric(row, *, graph, **_):
    """Check codec/gold agreement through the independent arithmetic oracle."""
    from ..verification.numeric import independent_value
    value = independent_value(decode(row["record"]["symbols"]))
    gold = ("TRUE" if value else "FALSE") if type(value) is bool else str(value)
    return (gold == row["gold"] and
            [graph["tokens"][index] for index in row["tokens"]] ==
            row["record"]["symbols"])


def semantic_footprint(row: dict) -> tuple[str, ...]:
    """Canonical query roots, excluding representation and equality wrappers."""
    return tuple(dict.fromkeys(inspect_record(row["record"]).rooted_operators))
