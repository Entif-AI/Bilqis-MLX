"""Independent recursive truth oracle for the derived B.COMPOSITE capability."""
from __future__ import annotations

VERSION = "bilqis.mlx.grade-b-composite-record-oracle/v1"
CAPABILITY = "B.COMPOSITE"
CONNECTIVES = ("NOT", "AND", "OR", "XOR", "IMPLIES", "IFF")


def _entity(node):
    if (not isinstance(node, dict) or set(node) != {"kind", "name"} or
            node["kind"] != "entity" or node["name"] not in "ABCDE"):
        raise ValueError("GRADE_B_COMPOSITE_ORACLE_UNATTESTED_ENTITY")
    return node["name"]


def _primitive_truth(world: dict, node: dict) -> bool:
    if not isinstance(node, dict) or node.get("kind") not in ("compare", "relation"):
        raise ValueError("GRADE_B_COMPOSITE_ORACLE_UNMASTERED_LEAF")
    if not isinstance(node.get("args"), list) or len(node["args"]) != 2:
        raise ValueError("GRADE_B_COMPOSITE_ORACLE_LEAF_ARITY")
    a, b = [_entity(item) for item in node["args"]]
    if a not in world["entities"] or b not in world["entities"]:
        raise ValueError("GRADE_B_COMPOSITE_ORACLE_ENTITY_OUTSIDE_WORLD")
    if node["kind"] == "compare":
        if node.get("operator") != "EQ":
            raise ValueError("GRADE_B_COMPOSITE_ORACLE_UNMASTERED_COMPARISON")
        return a == b
    facts = {tuple(item) for item in world["facts"]}
    if node.get("name") == "PARENT":
        return ("PARENT", a, b) in facts or ("CHILD", b, a) in facts
    if node.get("name") == "LINK":
        return ("LINK", a, b) in facts or ("LINK", b, a) in facts
    raise ValueError("GRADE_B_COMPOSITE_ORACLE_UNMASTERED_RELATION")


def _truth(world: dict, node: dict) -> bool:
    if node.get("kind") != "apply":
        return _primitive_truth(world, node)
    if set(node) != {"kind", "operator", "args"}:
        raise ValueError("GRADE_B_COMPOSITE_ORACLE_APPLY_SHAPE")
    op = node["operator"]
    if op not in CONNECTIVES or not isinstance(node["args"], list):
        raise ValueError("GRADE_B_COMPOSITE_ORACLE_UNKNOWN_OPERATOR")
    expected = 1 if op == "NOT" else 2
    if len(node["args"]) != expected:
        raise ValueError("GRADE_B_COMPOSITE_ORACLE_CONNECTIVE_ARITY")
    values = [_truth(world, item) for item in node["args"]]
    if op == "NOT":
        return not values[0]
    left, right = values
    if op == "AND": return left and right
    if op == "OR": return left or right
    if op == "XOR": return left != right
    if op == "IMPLIES": return (not left) or right
    if op == "IFF": return left == right
    raise ValueError("GRADE_B_COMPOSITE_ORACLE_UNKNOWN_OPERATOR")


def _operation_count(node: dict) -> int:
    if node.get("kind") != "apply":
        return 0
    return 1 + sum(_operation_count(item) for item in node["args"])


def evaluate(record: dict, capability: str = CAPABILITY) -> str:
    if (not isinstance(record, dict) or record.get("task") != "micro" or
            capability != CAPABILITY):
        raise ValueError("GRADE_B_COMPOSITE_ORACLE_UNKNOWN_TASK_OR_CAPABILITY")
    query = record.get("query")
    if not isinstance(query, dict) or _operation_count(query) not in (2, 3):
        raise ValueError("GRADE_B_COMPOSITE_ORACLE_COMPOSITION_WIDTH")
    return "TRUE" if _truth(record["world"], query) else "FALSE"
