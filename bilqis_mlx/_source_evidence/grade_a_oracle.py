"""Independent source-record oracle for the six proposed direct Grade A predicates.

This module reads only the *serialized* symbolic world and query. It does not
call either historical evaluation implementation or their internal helpers.
It is intentionally restricted to the six observed Grade A AST shapes.
"""
from __future__ import annotations

VERSION = "bilqis.mlx.grade-a-record-oracle/v2"
CAPABILITIES = frozenset(("A.IDENTITY", "A.PARENT", "A.LINK",
                          "A.MEMBER", "A.EDGE", "A.MAPS"))


def _entity(node: dict) -> str:
    if not isinstance(node, dict) or node.get("kind") != "entity":
        raise ValueError("GRADE_A_ORACLE_EXPECTS_ENTITY")
    return node["name"]


def _typed(node: dict, kind: str) -> str:
    if (not isinstance(node, dict) or node.get("kind") != "const"
            or node.get("type") != kind):
        raise ValueError("GRADE_A_ORACLE_EXPECTS_TYPED_" + kind.upper())
    return node["name"]


def evaluate(record: dict, capability: str) -> str:
    """Return TRUE/FALSE from a separate, literal finite-world interpretation."""
    if capability not in CAPABILITIES or not isinstance(record, dict):
        raise ValueError("GRADE_A_ORACLE_UNKNOWN_CAPABILITY")
    world = record["world"]
    query = record["query"]
    if capability.startswith("A.") and capability in ("A.IDENTITY", "A.PARENT", "A.LINK"):
        if record.get("task") != "micro":
            raise ValueError("GRADE_A_ORACLE_WRONG_TASK")
        if capability == "A.IDENTITY":
            if query.get("kind") != "compare" or query.get("operator") != "EQ":
                raise ValueError("GRADE_A_ORACLE_WRONG_QUERY")
            result = _entity(query["args"][0]) == _entity(query["args"][1])
        else:
            relation = capability.removeprefix("A.")
            if query.get("kind") != "relation" or query.get("name") != relation:
                raise ValueError("GRADE_A_ORACLE_WRONG_QUERY")
            a, b = (_entity(node) for node in query["args"])
            facts = world["facts"]
            if relation == "PARENT":
                result = (["PARENT", a, b] in facts or
                          ["CHILD", b, a] in facts)
            else:
                result = (["LINK", a, b] in facts or
                          ["LINK", b, a] in facts)
    else:
        if record.get("task") != "development":
            raise ValueError("GRADE_A_ORACLE_WRONG_TASK")
        if query.get("kind") != "op" or query.get("op") != capability.removeprefix("A."):
            raise ValueError("GRADE_A_ORACLE_WRONG_QUERY")
        args = query["args"]
        if capability == "A.MEMBER":
            element = _typed(args[0], "Entity")
            name = _typed(args[1], "Set")
            result = element in world["sets"][name]
        elif capability == "A.EDGE":
            a, b = (_typed(node, "Entity") for node in args)
            # Intentionally implemented through a positional scan rather than
            # the legacy kernel's list-membership expression.
            result = any(pair[0] == a and pair[1] == b
                         for pair in world["edges"])
        elif capability == "A.MAPS":
            function = _typed(args[0], "Function")
            source = _typed(args[1], "Entity")
            target = _typed(args[2], "Entity")
            result = any(pair[0] == source and pair[1] == target
                         for pair in world["functions"][function])
        else:
            raise ValueError("GRADE_A_ORACLE_UNREACHABLE")
    return "TRUE" if result else "FALSE"
