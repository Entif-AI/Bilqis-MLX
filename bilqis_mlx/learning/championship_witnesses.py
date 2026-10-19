"""Immutable question obligations inherited from championship decisions."""
from __future__ import annotations

from bilqis_mlx.generated_assessment import digest
from .championship_policy import CONTEXT_KEYS


SCHEMA = "bilqis.mlx.championship-questions/v1"


def earning_witness(exam: dict, capabilities) -> dict:
    """Preserve the complete question sets used to earn this title."""
    questions, perfect = [], []
    for capability in sorted(set(capabilities)):
        score = exam["scores"][capability]
        correct = exam["correct_questions"][capability]
        offered = exam["questions"][capability]
        if (len(offered) != score["total"] or len(correct) != score["correct"] or
                not {q["id"] for q in correct} <= {q["id"] for q in offered} or
                not 0 <= len(correct) <= score["total"] or score["total"] < 1):
            raise ValueError("CHAMPIONSHIP_QUESTION_SCORE_DRIFT")
        questions.extend({**question, "capability": capability} for question in offered)
        if len(correct) == score["total"]:
            perfect.append(capability)
    if (len({q["id"] for q in questions}) != len(questions) or
            any(not q.get("id") or not isinstance(q.get("gold"), str) for q in questions)):
        raise ValueError("CHAMPIONSHIP_QUESTION_IDENTITY_DRIFT")
    payload = {"schema": SCHEMA,
               **{key: exam[key] for key in CONTEXT_KEYS},
               "questions": sorted(questions, key=lambda q: q["id"]),
               "capabilities": sorted(set(capabilities)),
               "perfect_capabilities": perfect}
    return {**payload, "sha256": digest(payload)}


def verified_witnesses(role: dict) -> tuple[dict, ...]:
    witnesses = tuple(role.get("qualification_witnesses", ()))
    for witness in witnesses:
        payload = {k: v for k, v in witness.items() if k != "sha256"}
        if (payload.get("schema") != SCHEMA or digest(payload) != witness.get("sha256") or
                any(not isinstance(payload.get(key), str) or len(payload[key]) != 64
                    for key in CONTEXT_KEYS)):
            raise ValueError("CHAMPIONSHIP_QUESTION_WITNESS_DRIFT")
    return witnesses


def preserves_witnesses(role: dict, correct_by_witness: dict) -> bool:
    """Every inherited question must be correct, including foreign grades."""
    witnesses = verified_witnesses(role)
    if not witnesses:
        return False
    return all(witness["sha256"] in correct_by_witness and
               {q["id"] for q in witness["questions"]} <=
               set(correct_by_witness[witness["sha256"]]) for witness in witnesses)


def maxed_role(role: dict) -> bool:
    """Saved perfect-question proof entitles a role to its direct advisory vote."""
    witnesses = verified_witnesses(role)
    if witnesses:
        return any(role["capability"] in witness["perfect_capabilities"] or
                   (witness["sha256"] in role.get("cleared_witnesses", ()) and
                    role["capability"] in witness["capabilities"])
                   for witness in witnesses)
    return role.get("correct") == role.get("total") and role.get("total", 0) > 0
