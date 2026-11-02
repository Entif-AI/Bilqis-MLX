"""Freeze source-scored boundary event payloads before publication."""
from __future__ import annotations

import bilqis_mlx.learning.grade_soup as _learning_grade_soup


def _boundary_delivery_events(record, pending, roles, exam_event):
    """Freeze truthful source-scored events before publishing state.json."""
    school = record["school"]
    completed_grade = (exam_event["grade"] if exam_event is not None else
                       school["active_grades"][school["grade_index"]])
    events = []
    for provisional in pending:
        event = dict(provisional)
        event["recovered_at_student_sha256"] = school["current_student"]["sha256"]
        event["checkpoint_status"] = "RECORDED_AT_BOUNDARY"
        if event.get("teacher_observation") is not None:
            event["teacher_observation_publication"] = {
                "status": "DURABLE_CHECKPOINT_OUTBOX", "generation": record["generation"],
                "run_id": record["run_id"], "checkpoint": school["current_student"]}
        events.append(event)
    if roles:
        frontier = record["capability_best"]
        slots = [frontier[key] for key in sorted(frontier)
                 if frontier[key]["capability"] in roles and
                 frontier[key]["checkpoint"]["sha256"] ==
                 school["current_student"]["sha256"]]
        if ({slot["capability"] for slot in slots} != set(roles) or
                len({slot["rubric"] for slot in slots}) != 1):
            raise ValueError("HUMAN_TRAINER_CAPABILITY_BEST_RECEIPT_DRIFT")
        events.append({"event": "SCHOOL_CAPABILITY_BEST_COMMITTED",
                       "grade": completed_grade, "generation": record["generation"],
                       "capabilities": list(roles), "rubric": slots[0]["rubric"],
                       "scores": {entry["capability"]: {
                           "correct": entry["correct"], "total": entry["total"]}
                           for entry in slots},
                       "evaluation_ids": {entry["capability"]: entry["evaluation_id"]
                                          for entry in slots},
                       "student_sha256": school["current_student"]["sha256"],
                       "optimizer_step": school["current_student"]["optimizer_step"]})
    if exam_event is not None:
        # A freshly enrolled numeric staircase intentionally has no prior
        # grade examination. A stop-boundary candidate comparison is valid.
        active_soups = (record["mentor_epoch"].get("active_grade_soups", {})
                        if record.get("mentor_epoch") is not None
                        else record.get("grade_soups", {}))
        for grade in (record.get("last_exam") or {}).get("grade_soups_refreshed", ()):
            snapshot = active_soups[grade]
            for shard in _learning_grade_soup.soup_shards(snapshot):
                event = {
                    "event": "SCHOOL_GRADE_SOUP_FROZEN",
                    "generation": record["generation"], "grade": grade,
                    "filename": shard["filename"], "sha256": shard["sha256"],
                    "recipe_sha256": shard["recipe_sha256"],
                    "vote_count": shard["vote_count"],
                    "covered_capabilities": shard.get(
                        "covered_capabilities", shard["perfect_capabilities"]),
                    "source_champion_shas": [item["checkpoint"]["sha256"]
                                              for item in shard["members"]],
                    "frozen_source_weights_only": True,
                }
                if snapshot.get("schema") == _learning_grade_soup.PARTITIONED_SCHEMA:
                    event.update({
                        "logical_grade_recipe_sha256": snapshot["recipe_sha256"],
                        "logical_grade_vote_count": snapshot["vote_count"],
                        "source_graph_sha256": shard["source_graph_sha256"],
                    })
                events.append(event)
        events.append(dict(exam_event))
    return tuple(events)
