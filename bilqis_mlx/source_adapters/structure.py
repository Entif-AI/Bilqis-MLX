"""Read-only structure projection of already source-validated lesson queries.

Extracts original source-root symbols without assigning Bilqis identities.
The owning Course maps those source roots to admitted semantic capabilities.
No gold calculation or neural inference occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass


_SOURCE_NODES = {
    "compare": ("micro.compare.", "operator"),
    "relation": ("micro.relation.", "name"),
    "apply": ("cogal.operator.", "operator"),
    "op": ("development.op.", "op"),
}
_TERMINALS = frozenset(("entity", "const", "literal"))
MAX_INSPECTION_DEPTH = 64  # bounded parsing, not a curriculum complexity rule


@dataclass(frozen=True)
class SourceExpressionShape:
    root: str
    rooted_operators: tuple[str, ...]
    semantic_operations: int
    operator_depth: int


def inspect_source_query(query: dict) -> SourceExpressionShape:
    """Return rooted operation references and minimal observable complexity."""
    def visit(node, depth):
        if not isinstance(node, dict) or depth > MAX_INSPECTION_DEPTH:
            raise ValueError("LESSON_SOURCE_STRUCTURE_INVALID")
        kind = node.get("kind")
        if kind in _TERMINALS:
            return (), 0
        if kind not in _SOURCE_NODES:
            raise ValueError("LESSON_SOURCE_STRUCTURE_UNSUPPORTED")
        prefix, key = _SOURCE_NODES[kind]
        symbol = node.get(key)
        children = node.get("args")
        if (not isinstance(symbol, str) or not symbol or
                not isinstance(children, list)):
            raise ValueError("LESSON_SOURCE_OPERATOR_SHAPE_INVALID")
        names = [prefix + symbol]
        maximum_depth = depth
        for child in children:
            child_names, child_depth = visit(child, depth + 1)
            names.extend(child_names)
            maximum_depth = max(maximum_depth, child_depth)
        return tuple(names), maximum_depth

    operators, deepest = visit(query, 1)
    if not operators:
        raise ValueError("LESSON_SOURCE_NO_SEMANTIC_OPERATOR")
    return SourceExpressionShape(operators[0], operators, len(operators), deepest)


def inspect_boolean_identification(record: dict, root: str) -> SourceExpressionShape:
    """Project inverse-Boolean evidence without placing its hidden operator in tokens."""
    from ..boolean_identification_oracle import TASK
    if (not isinstance(record, dict) or record.get("task") != TASK or
            not isinstance(root, str) or not root.startswith("cogal.operator.")):
        raise ValueError("LESSON_SOURCE_IDENTIFICATION_STRUCTURE_INVALID")
    observations = record.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("LESSON_SOURCE_IDENTIFICATION_OBSERVATIONS_MISSING")
    rooted = [root]
    operations = 1
    deepest = 1
    for observation in observations:
        operands = observation.get("operands") if isinstance(observation, dict) else None
        if not isinstance(operands, list) or not operands:
            raise ValueError("LESSON_SOURCE_IDENTIFICATION_OPERANDS_MISSING")
        for operand in operands:
            shape = inspect_source_query(operand)
            rooted.extend(shape.rooted_operators)
            operations += shape.semantic_operations
            deepest = max(deepest, shape.operator_depth + 1)
    return SourceExpressionShape(root, tuple(rooted), operations, deepest)
