"""Partition, acquisition replay and exposed-stage checks."""
from .contracts import STAGE_ORDER, REQUIRES

def _validate_structure(plan: dict):
    if (plan.get("training_authorized") is not False or
            plan.get("qualification_authorized") is not False or
            plan.get("sealed_exam_policy") != "RESERVED_NOT_USED_FOR_SELECTION"):
        raise ValueError("PARITY_UNAUTHORIZED_LESSON_OR_EXAM_ADMISSION")
    ids = {}
    for partition, pairs in plan["pairs"].items():
        for pair in pairs:
            source_id = pair["source_id"]
            if source_id in ids:
                raise ValueError("PARITY_SOURCE_PARTITION_LEAK")
            ids[source_id] = partition
            native=pair["rows"][0].get("native_output") if pair["rows"] else None
            heads=plan["heads"]
            expect="school.number."+str(pair["value"])
            if (len(pair["rows"]) != 3 or
                    [r["answer_kind"] for r in pair["rows"]] !=
                    ["numeric_0_3", "evidence", "evidence"] or
                    [r["gold"] for r in pair["rows"]] !=
                    [str(pair["value"]), "TRUE", "FALSE"] or
                    any(r["source_id"] != source_id for r in pair["rows"]) or
                    native != {"identity": expect,
                               "token_id": heads["semantic_token"]["values"].index(expect)}):
                raise ValueError("PARITY_INCOMPLETE_DIRECT_TRUTH_NEGATIVE_PAIR")
    if len(ids) != 20:
        raise ValueError("PARITY_MISSING_PREDECESSOR_EXPRESSIONS")
    for name in STAGE_ORDER:
        stage = plan["stages"][name]
        if stage["requires"] != list(REQUIRES[name]):
            raise ValueError("PARITY_UNTAUGHT_STAGE_PREREQUISITES")
        train = {r["id"] for r in stage["train"]}
        if len(train) != len(stage["train"]):
            raise ValueError("PARITY_COLLIDING_TEACHING_EXAMPLES")
        if not {r["id"] for r in stage["replay"]} <= train:
            raise ValueError("PARITY_ACQUISITION_NOT_ACTUALLY_TAUGHT")


def eligible_stage(plan: dict, stage: str, receipts: dict) -> bool:
    """Exposed acquisition gates never certify independent generalization."""
    if stage not in STAGE_ORDER:
        raise ValueError("PARITY_UNKNOWN_STAGE")
    for earlier in REQUIRES[stage]:
        evidence = receipts.get(earlier) or {}
        known = [r["id"] for r in plan["stages"][earlier]["replay"]]
        sha = evidence.get("student_sha256")
        if (evidence.get("status") != "ACQUIRED_ON_EXPOSED_REPLAY" or
                evidence.get("source_sha256") != plan["source_sha256"] or
                evidence.get("probe_ids") != known or
                evidence.get("total") != len(known) or
                evidence.get("correct") != len(known) or
                type(evidence.get("optimizer_step")) is not int or
                not isinstance(sha, str) or len(sha) != 64 or
                any(ch not in "0123456789abcdef" for ch in sha)):
            return False
    return True
