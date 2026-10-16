"""Independent finite-set witnesses and inverse arithmetic on the shared AST."""
from __future__ import annotations

import json
from ..semantics.core import Apply, Literal


def independent_value(expression: Literal | Apply):
    if isinstance(expression, Literal):
        if expression.type_name == "Number":
            return int(expression.value)
        return tuple(json.loads(expression.value))
    name = expression.operator.symbol.rsplit(".", 1)[-1]
    values = tuple(independent_value(child) for child in expression.arguments)
    if name == "COUNT":
        # Enumerating distinct witnesses implements cardinality independently.
        result = 0
        seen = set()
        for member in values[0]:
            if member in seen:
                raise ValueError("NUMERIC_ORACLE_DUPLICATE_SET_MEMBER")
            seen.add(member)
            result += 1
        return result
    if name == "SUCC":
        return len((*range(values[0]), values[0]))
    a, b = values
    if name == "ADD": return len((*range(a), *range(b)))
    if name == "SUB":
        if b > a: raise ValueError("NUMERIC_ORACLE_NEGATIVE_RESULT")
        return len(range(b, a))
    if name == "MUL": return sum(a for _ in range(b))
    if name == "DIV":
        if b <= 0: raise ValueError("NUMERIC_ORACLE_EXACT_DIVISION_UNDEFINED")
        quotient, remainder = 0, a
        while remainder >= b:
            quotient, remainder = quotient+1, remainder-b
        if remainder: raise ValueError("NUMERIC_ORACLE_EXACT_DIVISION_UNDEFINED")
        return quotient
    if name == "EQ": return not (a < b or b < a)
    if name == "LT": return a in range(b)
    if name == "LE": return a in range(b+1)
    if name == "MOD":
        if b <= 0: raise ValueError("NUMERIC_ORACLE_MODULO_UNDEFINED")
        while a >= b: a -= b
        return a
    raise ValueError("NUMERIC_ORACLE_UNSUPPORTED_OPERATOR")
