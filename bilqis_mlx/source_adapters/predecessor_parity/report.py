"""Safe historical teaching reports and copied head bindings."""
from copy import deepcopy

def head_bindings(plan: dict) -> dict:
    return deepcopy(plan["heads"])


def audit_summary(plan: dict) -> dict:
    """Safe operator-facing counts and teaching samples, no sealed answer leak."""
    sample = next(pair for pair in plan["pairs"]["train"]
                  if pair["source"] == ["ADD", 1, 2])
    return {
        "schema": plan["schema"],
        "source_sha256": plan["source_sha256"],
        "original_student_graph_sha256": plan["graph_sha256"],
        "source_partitions": {k: len(v) for k, v in plan["pairs"].items()},
        "stage_rows": {k: {name: len(value) for name, value in stage.items()
                           if name in ("train", "replay", "development", "sealed")}
                       for k, stage in plan["stages"].items()},
        "answer_classes": {k: len(h["values"]) for k, h in plan["heads"].items()},
        "example": {"source": "ADD(1,2)", "direct": sample["rows"][0]["gold"],
                    "native_output_identity": sample["rows"][0]["native_output"]["identity"],
                    "native_output_token_id": sample["rows"][0]["native_output"]["token_id"],
                    "correct_claim": sample["rows"][1]["gold"],
                    "incorrect_claim": sample["rows"][2]["gold"]},
        "first_training_gate": "NUMERAL_IDENTITY_EXPOSED_REPLAY_NOT_YET_MEASURED",
        "sealed_exam_policy": plan["sealed_exam_policy"],
        "training_authorized": plan["training_authorized"],
        "qualification_authorized": plan["qualification_authorized"],
    }
