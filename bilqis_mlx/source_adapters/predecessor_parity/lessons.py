"""Oracle-checked direct numeric and truth-contrast lesson views."""
from copy import deepcopy
from .contracts import _digest

def _row(arithmetic, mapping, expression, *, source_id, source,
         partition, kind, expected):
    arithmetic.verify(expression)
    value = arithmetic.evaluate(expression)
    actual = ("TRUE" if value else "FALSE") if type(value) is bool else str(value)
    if expected != actual:
        raise ValueError("PARITY_GOLD_NOT_ORACLE_EVALUATION")
    record = {"task": arithmetic.VERSION, "expression": deepcopy(expression)}
    ids = arithmetic.encode(record, mapping)
    if (not ids or len(ids) > 96 or
            any(type(i) is not int or i < 0 or i >= len(mapping) for i in ids)):
        raise ValueError("PARITY_UNKNOWN_SOURCE_TOKEN_OR_CONTEXT")
    native = _native_output(kind, expected, mapping)
    return {"id": _digest(record), "source_id": source_id,
            "source": list(source), "partition": partition,
            "answer_kind": kind, "gold": expected,
            **({"native_output": native} if native else {}),
            "record": record, "tokens": ids,
            "oracle": "bilqis_school.arithmetic.evaluate+independent_evaluate"}


def _native_output(kind: str, gold: str, mapping: dict[str, int]):
    """Bind an oracle-checked number answer to its full-catalog token ID."""
    if kind != "numeric_0_3":
        return None
    identity = "school.number." + gold
    if gold not in ("0", "1", "2", "3") or identity not in mapping:
        raise ValueError("PARITY_DIRECT_NUMBER_NOT_IN_MODEL_SEMANTIC_ABI")
    return {"identity": identity, "token_id": mapping[identity]}


def _pair(source, arithmetic, mapping, assignment, partition):
    expr = source.expression(assignment)
    actual = arithmetic.evaluate(expr)
    if (type(actual) is not int or actual not in range(4) or
            assignment not in source.SOURCES[partition]):
        raise ValueError("PARITY_UNBOUNDED_OR_UNOWNED_ARITHMETIC")
    owner = source._source_id(expr)
    positive = source._eq(expr, actual)
    negative = source._eq(expr, source._wrong(actual))
    rows = [
        _row(arithmetic, mapping, expr, source_id=owner, source=assignment,
             partition=partition, kind="numeric_0_3", expected=str(actual)),
        _row(arithmetic, mapping, positive, source_id=owner, source=assignment,
             partition=partition, kind="evidence", expected="TRUE"),
        _row(arithmetic, mapping, negative, source_id=owner, source=assignment,
             partition=partition, kind="evidence", expected="FALSE"),
    ]
    if len({row["id"] for row in rows}) != 3:
        raise ValueError("PARITY_COLLIDING_ANSWER_VIEWS")
    return {"source": list(assignment), "source_id": owner,
            "value": actual, "partition": partition, "rows": rows}
