"""Bind event identity to immutable generations and reconcile delivery idempotently."""
from __future__ import annotations

import bilqis_mlx.data_plane as _data_plane
import bilqis_mlx.runtime.state as _runtime_state
import json as _json
import pathlib as _pathlib

from .journal import _record

def _with_delivery_outbox(record: dict, events) -> dict:
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
        copy = _json.loads(_runtime_state._canonical(event))
        copy["event_id"] = _runtime_state._fingerprint(["school-generation-event/v1",
                                         record["run_id"], record["generation"],
                                         index, copy])
        outbox.append(copy)
    prepared["delivery_outbox"] = outbox
    return prepared


def _require_outbox_lineage(condition: bool) -> None:
    if not condition:
        raise ValueError("HUMAN_TRAINER_OUTBOX_LINEAGE_DRIFT")


def _ordinary_outbox_lineage(record: dict, outbox) -> bool:
    if not isinstance(outbox, list):
        return False
    source_generation = record.get("generation")
    run_id = record.get("run_id")
    return type(source_generation) is int and bool(run_id) and all(
        isinstance(event, dict) and "event_id" in event and
        event["event_id"] == _runtime_state._fingerprint([
            "school-generation-event/v1", run_id, source_generation,
            index, {k: v for k, v in event.items() if k != "event_id"}])
        for index, event in enumerate(outbox)
    )


def _outbox_source_generation(run_dir: _pathlib.Path, record: dict, outbox: list):
    source_generation = record["generation"]
    inherited = None
    if not _ordinary_outbox_lineage(record, outbox):
        from bilqis_mlx.runtime.outbox_lineage import verified_inherited_v1_generation
        inherited = verified_inherited_v1_generation(run_dir, record)
        if inherited is not None:
            source_generation = inherited
    return source_generation, inherited


def _expected_outbox_events(record: dict, outbox: list, source_generation: int):
    expected = {}
    for index, event in enumerate(outbox):
        if not isinstance(event, dict) or "event_id" not in event:
            raise ValueError("HUMAN_TRAINER_OUTBOX_EVENT_ID_MISSING")
        payload = {k: v for k, v in event.items() if k != "event_id"}
        identity = _runtime_state._fingerprint([
            "school-generation-event/v1", record["run_id"],
            source_generation, index, payload])
        _require_outbox_lineage(
            event["event_id"] == identity and identity not in expected)
        expected[identity] = event
    return expected


def _observed_outbox_events(run_dir: _pathlib.Path, expected: dict):
    observed = set()
    observed_counts = {}
    journal = run_dir / "events.jsonl"
    if not journal.exists():
        return observed, observed_counts
    if journal.is_symlink() or not journal.is_file():
        raise ValueError("HUMAN_TRAINER_OUTBOX_UNSAFE_LEDGER")
    indexed = _data_plane.event_observations(run_dir, expected)
    for identity, (digest, count, conflicted) in indexed.items():
        if (conflicted or
                digest != _data_plane.event_payload_digest(expected[identity])):
            raise ValueError("HUMAN_TRAINER_OUTBOX_LEDGER_CONTENT_DRIFT")
        observed.add(identity)
        observed_counts[identity] = count
    return observed, observed_counts


def _reconcile_delivery_outbox(
        run_dir: _pathlib.Path, record: dict, *, publish_missing: bool = True):
    """Replay missing events; never duplicate or amend prior ledger history.

    Caller must hold the exclusive operator lock. JSONL write+fsync can succeed
    even if the process dies before acknowledging it, so dedupe by the exact
    immutable generation event ID *and* payload rather than a stale boolean.
    """
    outbox = record.get("delivery_outbox")
    if outbox is None:
        return False
    if not isinstance(outbox, list) or not outbox:
        raise ValueError("HUMAN_TRAINER_OUTBOX_INVALID")
    # Ordinarily all outbox IDs are bound to the current generation. A single
    # historical v1->v2 migration erroneously copied the previous outbox into
    # an otherwise valid immutable successor; accept that *only* with proven
    # signed predecessor identity and fully published, unmodified journal rows.
    # Most valid generations are not compatibility migrations. Avoid rereading
    # a 47 MB immutable predecessor when the ordinary current-generation IDs
    # already validate; verify an inherited predecessor only upon actual drift.
    source_generation, inherited = _outbox_source_generation(
        run_dir, record, outbox)
    expected = _expected_outbox_events(record, outbox, source_generation)
    observed, observed_counts = _observed_outbox_events(run_dir, expected)
    if inherited is not None:
        _require_outbox_lineage(
            observed == set(expected) and
            all(count == 1 for count in observed_counts.values()))
        return True
    if not publish_missing:
        # Neural-inert operator preflight may inspect custody, but must never
        # replay missing events or alter the append-only journal.
        return observed == set(expected)
    for event in outbox:
        if event["event_id"] not in observed:
            _record(run_dir, event)
    return True
