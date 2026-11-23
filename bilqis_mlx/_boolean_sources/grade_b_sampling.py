"""Pure sampling and truth helpers for live Grade B Boolean construction."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SOURCE

MINIMUM_BOOLEAN_SAMPLE_ROWS = len((False, True)) ** 2

def _truth_expressions(logic, truth: bool, operator: str) -> tuple[tuple[dict, dict], ...]:
    result = []
    if operator == "NOT":
        for source in ("literal", "P", "Q"):
            for depth in range(7):
                base_truth = truth if depth % 2 == 0 else not truth
                if source == "literal":
                    expression, env = logic.literal(base_truth), {}
                else:
                    expression, env = logic.variable(source), {source: base_truth}
                for _ in range(depth):
                    expression = logic.apply("NOT", expression)
                result.append((expression, env))
        return tuple(result)
    wrappers = {
        "AND": lambda x: logic.apply("AND", x, logic.literal(True)),
        "OR": lambda x: logic.apply("OR", x, logic.literal(False)),
        "XOR": lambda x: logic.apply("XOR", x, logic.literal(False)),
        "IFF": lambda x: logic.apply("IFF", x, logic.literal(True)),
        "IMPLIES": lambda x: logic.apply("IMPLIES", logic.literal(True), x),
    }
    wrap = wrappers[operator]
    for source in ("literal", "P", "Q"):
        if source == "literal":
            base, env = logic.literal(truth), {}
        else:
            base, env = logic.variable(source), {source: truth}
        expression = base
        for _ in range(6):
            result.append((expression, dict(env)))
            expression = wrap(expression)
    return tuple(result)


def _u7c_pattern_counts(op: str, each: int) -> dict[tuple[bool, ...], int]:
    half = each // 2
    def split(total, patterns):
        low, remainder = divmod(total, len(patterns))
        return {
            pattern: low + (index < remainder)
            for index, pattern in enumerate(patterns)
        }
    if op == "NOT":
        return {(False,): half, (True,): half}
    if each == MINIMUM_BOOLEAN_SAMPLE_ROWS:
        return {
            (False, False): 1, (False, True): 1,
            (True, False): 1, (True, True): 1,
        }
    if op == "AND":
        return {(True, True): half, **split(
            half, ((False, False), (True, False), (False, True)))}
    if op == "OR":
        return {(False, False): half, **split(
            half, ((True, True), (True, False), (False, True)))}
    if op == "IMPLIES":
        return {(True, False): half, **split(
            half, ((True, True), (False, False), (False, True)))}
    if op == "XOR":
        return {**split(half, ((False, True), (True, False))),
                **split(half, ((False, False), (True, True)))}
    if op == "IFF":
        return {**split(half, ((False, False), (True, True))),
                **split(half, ((False, True), (True, False)))}
    raise ErrorBus.legacy_error(SOURCE.BOOLEAN.UNKNOWN_OPERATOR)

def independent_truth(op: str, values: tuple[bool, ...]) -> bool:
    """Pure generator-side classification used only to choose balanced cases."""
    if op == "NOT": return not values[0]
    a, b = values
    if op == "AND": return a and b
    if op == "OR": return a or b
    if op == "XOR": return a != b
    if op == "IMPLIES": return not a or b
    if op == "IFF": return a == b
    raise ErrorBus.legacy_error(SOURCE.BOOLEAN.UNKNOWN_OPERATOR)
