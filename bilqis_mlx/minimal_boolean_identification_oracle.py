"""Independent inverse oracle for the reduced AND/IFF identification task."""
from __future__ import annotations

from .boolean_identification_oracle import (
    TASK,
    _apply,
    _primitive_truth,
)


VERSION = "bilqis.mlx.grade-b-minimal-idboolops-record-oracle/v1"
CAPABILITY = "B.IDBOOLOPS"
OPERATORS = ("AND", "IFF")


def evaluate(record: dict, capability: str = CAPABILITY) -> str:
    if (not isinstance(record, dict) or record.get("task") != TASK or
            capability != CAPABILITY or
            set(record) != {"task", "world", "observations", "options"}):
        raise ValueError("GRADE_B_MINIMAL_IDBOOLOPS_UNKNOWN_TASK_OR_CAPABILITY")
    options = record["options"]
    if tuple(options) != OPERATORS or len(set(options)) != len(options):
        raise ValueError("GRADE_B_MINIMAL_IDBOOLOPS_OPTION_DRIFT")
    observations = record["observations"]
    if not isinstance(observations, list) or not observations:
        raise ValueError("GRADE_B_MINIMAL_IDBOOLOPS_OBSERVATIONS_MISSING")
    parsed = []
    truth_patterns = set()
    for observation in observations:
        if (not isinstance(observation, dict) or
                set(observation) != {"operands", "result"} or
                not isinstance(observation["operands"], list) or
                len(observation["operands"]) != 2 or
                type(observation["result"]) is not bool):
            raise ValueError("GRADE_B_MINIMAL_IDBOOLOPS_OBSERVATION_SHAPE")
        values = tuple(_primitive_truth(record["world"], operand)
                       for operand in observation["operands"])
        truth_patterns.add(values)
        parsed.append((values, observation["result"]))
    required = {(False, False), (False, True), (True, False), (True, True)}
    if truth_patterns != required or len(observations) != len(required):
        raise ValueError("GRADE_B_MINIMAL_IDBOOLOPS_SIGNATURE_INCOMPLETE")
    matches = [operator for operator in options
               if all(_apply(operator, values) == result for values, result in parsed)]
    if len(matches) != 1:
        raise ValueError("GRADE_B_MINIMAL_IDBOOLOPS_NOT_UNIQUE")
    return matches[0]
