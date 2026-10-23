"""Independent inverse oracle for the reduced AND/IFF identification task."""
from __future__ import annotations

from .boolean_identification_oracle import TASK, evaluate as evaluate_full

VERSION = "bilqis.mlx.grade-b-minimal-idboolops-record-oracle/v1"
CAPABILITY = "B.IDBOOLOPS"
OPERATORS = ("AND", "IFF")


def evaluate(record: dict, capability: str = CAPABILITY) -> str:
    if (not isinstance(record, dict) or record.get("task") != TASK or
            capability != CAPABILITY or tuple(record.get("options", ())) != OPERATORS):
        raise ValueError("GRADE_B_MINIMAL_IDBOOLOPS_UNKNOWN_TASK_OR_CAPABILITY")
    result = evaluate_full(record, capability)
    if result not in OPERATORS:
        raise ValueError("GRADE_B_MINIMAL_IDBOOLOPS_NOT_UNIQUE")
    return result
