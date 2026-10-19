"""Independent inverse oracle for B.IDBOOLOPS Boolean primitive identification."""
from __future__ import annotations

from .curriculum import BOOLEAN_OPERATORS


VERSION = "bilqis.mlx.grade-b-idboolops-record-oracle/v1"
CAPABILITY = "B.IDBOOLOPS"
TASK = "identify_boolean_operator"


def _entity(node):
    if (not isinstance(node, dict) or set(node) != {"kind", "name"} or
            node["kind"] != "entity" or node["name"] not in "ABCDE"):
        raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_UNATTESTED_ENTITY")
    return node["name"]


def _primitive_truth(world: dict, node: dict) -> bool:
    if not isinstance(node, dict) or node.get("kind") not in ("compare", "relation"):
        raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_UNMASTERED_OPERAND")
    if not isinstance(node.get("args"), list) or len(node["args"]) != 2:
        raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_OPERAND_ARITY")
    a, b = [_entity(item) for item in node["args"]]
    if a not in world["entities"] or b not in world["entities"]:
        raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_ENTITY_OUTSIDE_WORLD")
    if node["kind"] == "compare":
        if node.get("operator") != "EQ":
            raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_UNMASTERED_COMPARISON")
        return a == b
    facts = {tuple(item) for item in world["facts"]}
    if node.get("name") == "PARENT":
        return ("PARENT", a, b) in facts or ("CHILD", b, a) in facts
    if node.get("name") == "LINK":
        return ("LINK", a, b) in facts or ("LINK", b, a) in facts
    raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_UNMASTERED_RELATION")


def _apply(operator: str, values: tuple[bool, ...]) -> bool:
    expected = 1 if operator == "NOT" else 2
    if len(values) != expected:
        raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_OPERATOR_ARITY")
    if operator == "NOT":
        return not values[0]
    left, right = values
    return {
        "AND": lambda: left and right,
        "OR": lambda: left or right,
        "XOR": lambda: left != right,
        "IMPLIES": lambda: (not left) or right,
        "IFF": lambda: left == right,
    }[operator]()


def evaluate(record: dict, capability: str = CAPABILITY) -> str:
    """Return the one admitted operator compatible with every shown observation."""
    if (not isinstance(record, dict) or record.get("task") != TASK or
            capability != CAPABILITY or set(record) != {"task", "world", "observations", "options"}):
        raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_UNKNOWN_TASK_OR_CAPABILITY")
    options = record["options"]
    if (not isinstance(options, list) or tuple(options) != BOOLEAN_OPERATORS or
            len(set(options)) != len(options)):
        raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_OPTION_DRIFT")
    observations = record["observations"]
    if not isinstance(observations, list) or not observations:
        raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_OBSERVATIONS_MISSING")
    arities = set()
    truth_patterns = set()
    parsed = []
    for observation in observations:
        if (not isinstance(observation, dict) or set(observation) != {"operands", "result"} or
                not isinstance(observation["operands"], list) or
                len(observation["operands"]) not in (1, 2) or
                type(observation["result"]) is not bool):
            raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_OBSERVATION_SHAPE")
        values = tuple(_primitive_truth(record["world"], operand)
                       for operand in observation["operands"])
        arities.add(len(values))
        truth_patterns.add(values)
        parsed.append((values, observation["result"]))
    if len(arities) != 1:
        raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_MIXED_ARITY")
    arity = next(iter(arities))
    required = ({(False,), (True,)} if arity == 1 else
                {(False, False), (False, True), (True, False), (True, True)})
    if truth_patterns != required or len(observations) != len(required):
        raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_SIGNATURE_INCOMPLETE")
    matches = []
    for operator in options:
        expected_arity = 1 if operator == "NOT" else 2
        if expected_arity != arity:
            continue
        if all(_apply(operator, values) == result for values, result in parsed):
            matches.append(operator)
    if len(matches) != 1:
        raise ValueError("GRADE_B_IDBOOLOPS_ORACLE_NOT_UNIQUE")
    return matches[0]
