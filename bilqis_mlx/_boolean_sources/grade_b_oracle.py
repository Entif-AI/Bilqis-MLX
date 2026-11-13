"""Independent finite-world truth oracle for six typed Grade B connectives.

Never imports a historical model, interpreter, or student output. This oracle
reconstructs direct Grade A operand truth from serialized facts and applies
its own Boolean definitions. New Ithkuil morphology is NOT claimed here.
"""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SOURCE

VERSION = "bilqis.mlx.grade-b-connective-record-oracle/v1"
CONNECTIVES = ("NOT", "AND", "OR", "XOR", "IMPLIES", "IFF")


def _entity(node):
    if (not isinstance(node, dict) or set(node) != {"kind", "name"} or
            node["kind"] != "entity" or node["name"] not in "ABCDE"):
        raise ValueError("GRADE_B_ORACLE_UNATTESTED_ENTITY")
    return node["name"]


def operand_truth(world: dict, node: dict) -> bool:
    """Interpret only the three admitted micro-world Grade A primitives."""
    if not isinstance(node, dict) or node.get("kind") not in ("compare", "relation"):
        raise ValueError("GRADE_B_ORACLE_UNMASTERED_OPERAND")
    if set(node) != {"kind", "operator", "args"} and set(node) != {"kind", "name", "args"}:
        raise ValueError("GRADE_B_ORACLE_OPERAND_SHAPE")
    if not isinstance(node["args"], list) or len(node["args"]) != 2:
        raise ValueError("GRADE_B_ORACLE_OPERAND_ARITY")
    a, b = [_entity(x) for x in node["args"]]
    if a not in world["entities"] or b not in world["entities"]:
        raise ValueError("GRADE_B_ORACLE_ENTITY_OUTSIDE_WORLD")
    if node["kind"] == "compare" and node["operator"] == "EQ":
        return a == b
    if node["kind"] != "relation":
        raise ValueError("GRADE_B_ORACLE_UNMASTERED_COMPARISON")
    facts = {tuple(f) for f in world["facts"]}
    if node["name"] == "PARENT":
        return ("PARENT", a, b) in facts or ("CHILD", b, a) in facts
    if node["name"] == "LINK":
        return ("LINK", a, b) in facts or ("LINK", b, a) in facts
    raise ValueError("GRADE_B_ORACLE_UNMASTERED_RELATION")



def _direct_truth(node: dict, assignments: dict) -> bool:
    if not isinstance(assignments, dict):
        ErrorBus.raise_legacy(SOURCE.BOOLEAN.ORACLE_ASSIGNMENTS_INVALID)
    kind = node.get("kind") if isinstance(node, dict) else None
    if kind == "literal" and type(node.get("value")) is bool:
        return node["value"]
    if (kind == "variable" and node.get("name") in assignments and
            type(assignments[node["name"]]) is bool):
        return assignments[node["name"]]
    if (kind != "apply" or node.get("operator") not in CONNECTIVES or
            not isinstance(node.get("args"), list)):
        ErrorBus.raise_legacy(SOURCE.BOOLEAN.ORACLE_DIRECT_EXPRESSION_INVALID)
    op = node["operator"]
    expected = 1 if op == "NOT" else 2
    if len(node["args"]) != expected:
        ErrorBus.raise_legacy(SOURCE.BOOLEAN.ORACLE_CONNECTIVE_SHAPE)
    values = [_direct_truth(arg, assignments) for arg in node["args"]]
    if op == "NOT": return not values[0]
    left, right = values
    if op == "AND": return left and right
    if op == "OR": return left or right
    if op == "XOR": return left != right
    if op == "IMPLIES": return (not left) or right
    if op == "IFF": return left == right
    ErrorBus.raise_legacy(SOURCE.BOOLEAN.ORACLE_DIRECT_EXPRESSION_INVALID)

def evaluate(record: dict, capability: str) -> str:
    if (not isinstance(record, dict) or
            capability not in {"B." + name for name in CONNECTIVES}):
        ErrorBus.raise_legacy(SOURCE.BOOLEAN.ORACLE_UNKNOWN_TASK_OR_CAPABILITY)
    operation = capability.split(".", 1)[1]
    if record.get("task") == "evaluate":
        expression = record.get("expression")
        if (not isinstance(expression, dict) or expression.get("kind") != "apply" or
                expression.get("operator") != operation):
            ErrorBus.raise_legacy(SOURCE.BOOLEAN.ORACLE_CONNECTIVE_SHAPE)
        return "TRUE" if _direct_truth(expression, record.get("assignments")) else "FALSE"
    if record.get("task") != "micro":
        ErrorBus.raise_legacy(SOURCE.BOOLEAN.ORACLE_UNKNOWN_TASK_OR_CAPABILITY)
    query = record["query"]
    if (not isinstance(query, dict) or set(query) != {"kind", "operator", "args"} or
            query["kind"] != "apply" or query["operator"] != operation or
            not isinstance(query["args"], list) or
            len(query["args"]) != (1 if operation == "NOT" else 2)):
        ErrorBus.raise_legacy(SOURCE.BOOLEAN.ORACLE_CONNECTIVE_SHAPE)
    values = [operand_truth(record["world"], x) for x in query["args"]]
    if operation == "NOT":
        truth = not values[0]
    else:
        left, right = values
        truth = {
            "AND": lambda: left and right,
            "OR": lambda: left or right,
            "XOR": lambda: left != right,
            "IMPLIES": lambda: (not left) or right,
            "IFF": lambda: left == right,
        }[operation]()
    return "TRUE" if truth else "FALSE"
