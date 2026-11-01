"""Read-only reconstruction of observations admitted by canonical generation outboxes."""
from __future__ import annotations

import json
from pathlib import Path

from ..errors import ErrorBus, SCHOOL
from .. import state_dag
from .checkpoints import _ordinary_outbox_lineage
from .teacher_observation_capture import read_observation


def _observation_events(run_dir, current):
    journal = Path(run_dir) / "events.jsonl"
    if journal.exists():
        if journal.is_symlink() or not journal.is_file():
            ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.CONTENT_MISMATCH)
        with journal.open() as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except ValueError:
                    ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.CONTENT_MISMATCH)
                if isinstance(event, dict) and event.get("teacher_observation") is not None:
                    yield event, True
    for event in current.get("delivery_outbox", ()):
        if event.get("teacher_observation") is not None:
            yield event, False


def _verify_publication(run_dir, event, cache):
    publication = event.get("teacher_observation_publication") or {}
    generation = publication.get("generation")
    if (type(generation) is not int or generation < 1 or
            publication.get("status") != "DURABLE_CHECKPOINT_OUTBOX"):
        ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.INVALID)
    if generation not in cache:
        try:
            cache[generation] = state_dag.read_generation_fields(run_dir, generation,
                ("generation", "run_id", "school", "delivery_outbox"))
        except (OSError, ValueError, KeyError):
            ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.CONTENT_MISMATCH)
    record = cache[generation]
    outbox = record.get("delivery_outbox")
    if (not _ordinary_outbox_lineage(record, outbox) or
            record.get("generation") != generation or
            publication.get("run_id") != record.get("run_id") or
            publication.get("checkpoint") != record.get("school", {}).get("current_student") or
            not any(item == event for item in outbox)):
        ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.INVALID)


def read_committed_observations(run_dir):
    """Join history and durable current intent once, including a pre-emission crash.

    This offline reader never replays training, teacher credit or event delivery.
    Every accepted event must be an exact member of its immutable generation.
    Unpublished sidecars alone do not establish a committed observation.
    """
    run_dir = Path(run_dir)
    current = state_dag.read_current(run_dir)
    generations, attempts, event_payloads = {}, {}, {}
    result = []
    for event, emitted in _observation_events(run_dir, current):
        _verify_publication(run_dir, event, generations)
        identity = event.get("event_id")
        prior = event_payloads.get(identity)
        if prior is not None:
            if prior != event:
                ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.CONTENT_MISMATCH)
            continue
        event_payloads[identity] = event
        observation = read_observation(run_dir, event)
        attempt = observation["attempt_id"]
        if attempt in attempts:
            ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.DUPLICATE_ATTEMPT)
        attempts[attempt] = identity
        observation["ledger_delivery"] = "EMITTED" if emitted else "OUTBOX_COMMITTED_NOT_EMITTED"
        result.append(observation)
    return result
