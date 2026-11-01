"""Checkpoint-bound event outbox construction and idempotent replay."""
from __future__ import annotations

from pathlib import Path
from bilqis_mlx.errors import ErrorBus, SCHOOL

import bilqis_mlx.data_plane as _data_plane
import bilqis_mlx.learning.grade_soup as _learning_grade_soup
import bilqis_mlx.runtime.state as _runtime_state


def boundary_delivery_events(record, pending, roles, exam_event):
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
                 frontier[key]["checkpoint"]["sha256"] == school["current_student"]["sha256"]]
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


def with_delivery_outbox(record: dict, events) -> dict:
    """Commit event intent atomically with the immutable student generation."""
    if not record.get("run_id") or type(record.get("generation")) is not int:
        raise ValueError("HUMAN_TRAINER_OUTBOX_MISSING_LINEAGE")
    prepared = dict(record)
    prepared.pop("_pending_visit_events", None)
    if not events:
        raise ValueError("HUMAN_TRAINER_OUTBOX_REQUIRES_EVENT")
    outbox = []
    for index, event in enumerate(events):
        if not isinstance(event, dict) or not event.get("event") or "event_id" in event:
            raise ValueError("HUMAN_TRAINER_OUTBOX_UNTRUSTED_EVENT")
        copy = __import__("json").loads(_runtime_state._canonical(event))
        copy["event_id"] = _runtime_state._fingerprint([
            "school-generation-event/v1", record["run_id"], record["generation"], index, copy])
        outbox.append(copy)
    prepared["delivery_outbox"] = outbox
    return prepared


def ordinary_outbox_lineage(record: dict, outbox) -> bool:
    if not isinstance(outbox, list):
        return False
    source_generation = record.get("generation")
    run_id = record.get("run_id")
    return type(source_generation) is int and bool(run_id) and all(
        isinstance(event, dict) and "event_id" in event and
        event["event_id"] == _runtime_state._fingerprint([
            "school-generation-event/v1", run_id, source_generation,
            index, {k: v for k, v in event.items() if k != "event_id"}])
        for index, event in enumerate(outbox))


def _require_outbox_lineage(condition: bool) -> None:
    if not condition:
        ErrorBus.raise_legacy(SCHOOL.CHECKPOINT_CUSTODY.OUTBOX_LINEAGE_DRIFT)


def _source_generation(run_dir: Path, record: dict, outbox: list):
    source_generation = record["generation"]
    inherited = None
    if not ordinary_outbox_lineage(record, outbox):
        from bilqis_mlx.runtime.outbox_lineage import verified_inherited_v1_generation
        inherited = verified_inherited_v1_generation(run_dir, record)
        if inherited is not None:
            source_generation = inherited
    return source_generation, inherited


def _expected_events(record: dict, outbox: list, source_generation: int):
    expected = {}
    for index, event in enumerate(outbox):
        if not isinstance(event, dict) or "event_id" not in event:
            raise ValueError("HUMAN_TRAINER_OUTBOX_EVENT_ID_MISSING")
        payload = {k: v for k, v in event.items() if k != "event_id"}
        identity = _runtime_state._fingerprint([
            "school-generation-event/v1", record["run_id"], source_generation, index, payload])
        _require_outbox_lineage(event["event_id"] == identity and identity not in expected)
        expected[identity] = event
    return expected


def _observed_events(run_dir: Path, expected: dict):
    observed = set()
    observed_counts = {}
    journal = run_dir / "events.jsonl"
    if not journal.exists():
        return observed, observed_counts
    if journal.is_symlink() or not journal.is_file():
        raise ValueError("HUMAN_TRAINER_OUTBOX_UNSAFE_LEDGER")
    indexed = _data_plane.event_observations(run_dir, expected)
    for identity, (digest, count, conflicted) in indexed.items():
        if conflicted or digest != _data_plane.event_payload_digest(expected[identity]):
            raise ValueError("HUMAN_TRAINER_OUTBOX_LEDGER_CONTENT_DRIFT")
        observed.add(identity)
        observed_counts[identity] = count
    return observed, observed_counts


def reconcile_delivery_outbox(
        run_dir: Path, record: dict, *, publish_missing: bool = True, record_event):
    """Replay missing events; never duplicate or amend prior ledger history."""
    outbox = record.get("delivery_outbox")
    if outbox is None:
        return False
    if not isinstance(outbox, list) or not outbox:
        raise ValueError("HUMAN_TRAINER_OUTBOX_INVALID")
    source_generation, inherited = _source_generation(run_dir, record, outbox)
    expected = _expected_events(record, outbox, source_generation)
    observed, observed_counts = _observed_events(run_dir, expected)
    if inherited is not None:
        _require_outbox_lineage(
            observed == set(expected) and all(count == 1 for count in observed_counts.values()))
        return True
    if not publish_missing:
        return observed == set(expected)
    for event in outbox:
        if event["event_id"] not in observed:
            record_event(run_dir, event)
    return True
