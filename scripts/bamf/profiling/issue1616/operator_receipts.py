"""Compare behavior without conflating process-local evidence with model bytes."""
from copy import deepcopy
import json


TERMINAL = frozenset(("BAMF_C16_3_ACCEPTED", "BAMF_CANDIDATE_REJECTED"))


def outcomes(run, offset):
    result = []
    with (run / "events.jsonl").open("rb") as stream:
        stream.seek(offset)
        for line in stream:
            event = json.loads(line)
            if event.get("event") not in TERMINAL:
                continue
            evidence = event.get("evidence", event)
            how = evidence["how_outcome"]
            result.append({
                "event": event["event"], "capability": evidence.get("capability"),
                "option": evidence.get("selected_option_id"),
                "teacher": how.get("selected_teacher_sha256"),
                "policy": evidence.get("selected_policy_key"),
                "steps": how["attempted_steps"], "retained": how["retained_steps"],
                "reason": how["decision"]["reason"], "scores": how["scores"],
                "how_outcome": how,
            })
    return result


def behavioral_outcome(attempt):
    """Keep all observed HOW fields except explicitly local custody digests.

    Ordinary rejected C05 candidate identity is a process-local step token,
    while an accepted candidate identity is canonical numerical content.
    Retain the complete raw record separately, including teacher and decision
    fingerprints; a behavioral match is not full teacher-state equality.
    """
    result = deepcopy(attempt)
    result.pop("teacher")
    how = result["how_outcome"]
    how.pop("selected_teacher_sha256", None)
    how.pop("outcome_sha256", None)
    decision = how["decision"]
    decision.pop("decision_sha256", None)
    decision.pop("evidence_sha256", None)
    if result["event"] == "BAMF_CANDIDATE_REJECTED":
        decision.pop("candidate_generation", None)
    return result


def compare(stock, compiled):
    keys = ("initial_manifest", "initial_optimizer_sha256", "source_release",
            "attempted_steps", "generation", "optimizer_step",
            "final_optimizer_sha256", "exam", "exam_cohort_sha256", "exam_overlap")
    equal = {k: stock[k] == compiled[k] for k in keys}
    equal["attempts"] = (
        [behavioral_outcome(x) for x in stock["attempts"]]
        == [behavioral_outcome(x) for x in compiled["attempts"]])
    for key in ("loss", "rows", "source_coordinates"):
        equal["step_" + key] = (
            [s[key] for s in stock["steps"]] == [s[key] for s in compiled["steps"]])
    return {
        "schema": "bilqis.issue1616.matched-operator/v2",
        "behavioral_parity": equal,
        "raw_attempt_receipts_equal": stock["attempts"] == compiled["attempts"],
        "selected_teacher_fingerprints_equal": (
            [x["teacher"] for x in stock["attempts"]]
            == [x["teacher"] for x in compiled["attempts"]]),
        "wall_ratio": compiled["wall_seconds"] / stock["wall_seconds"],
        "memory_ratio": compiled["peak_mlx_bytes"] / stock["peak_mlx_bytes"],
        "authorizing": False, "stock": stock, "compiled": compiled,
    }


def exam_inventory(context, capabilities, seed, each, observations):
    from bilqis_mlx.runtime.source_execution import _source_family

    coordinates = {tuple(row) for step in observations
                   for row in step["source_coordinates"]}
    families = {row[1] for row in coordinates}
    episodes = {row[2] for row in coordinates}
    inventory = {}
    for cap in capabilities:
        cases = []
        for row in context.draw_rows(seed=seed, capability=cap, each=each):
            family = row.get("source_family_id") or _source_family(
                context.release.execution_plan.capability_map[cap])
            episode = row.get("episode_id") or row["id"]
            cases.append({"id": row["id"], "source_family_id": family,
                          "episode_id": episode})
        inventory[cap] = {
            "cases": cases,
            "family_overlap": sum(c["source_family_id"] in families for c in cases),
            "episode_overlap": sum(c["episode_id"] in episodes or c["id"] in episodes
                                   for c in cases),
        }
    return inventory, families, episodes


def exam_overlap(context, h, observations):
    caps = tuple(x.capability_id for x in context.release.execution_plan.capabilities
                 if x.grade_id == "A")
    inventory, families, episodes = exam_inventory(context, caps, h.SEED, 12, observations)
    rows = [c for item in inventory.values() for c in item["cases"]]
    return {
        "training_episode_overlap": sorted(
            ({c["id"] for c in rows} | {c["episode_id"] for c in rows}) & episodes),
        "known_source_family_overlap": sorted({c["source_family_id"] for c in rows} & families),
    }
