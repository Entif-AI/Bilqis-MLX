"""Project genuine strict C06 events; absent evidence is unavailable, not zero."""
from dataclasses import replace

from bilqis_mlx.mission_control.contracts.events import SalienceEventV2
from bilqis_mlx.mission_control.contracts.envelopes import (
    UnavailableEnvelope, UnavailableReason,
)
from bilqis_mlx.mission_control.contracts.model import (
    CoverageState, DataValue, ValueOrigin, ValueState, is_name, is_sha256,
)
from ..native_contracts import record_meta, run_ref


def unavailable_salience(generation):
    run = run_ref(generation)
    return UnavailableEnvelope(
        record_meta(f"salience-unavailable:{run.run_id}:{run.generation}",
                    run, generation, coverage=CoverageState.UNKNOWN),
        f"salience:{run.run_id}", UnavailableReason.UNAVAILABLE,
        "c06:signed-event-history-not-in-accepted-custody")


def _axis(value):
    if not isinstance(value, str) or value not in {"LOW", "MODERATE", "HIGH", "CRITICAL"}:
        return DataValue(ValueState.UNKNOWN, None, None)
    return DataValue(ValueState.PRESENT, ValueOrigin.DERIVED, value, "ordinal")


def observed_salience_records(observation, events):
    if not isinstance(events, list) or len(events) > 8:
        return ()
    result = {}
    for event in events:
        if (not isinstance(event, dict)
                or not all(is_name(event.get(key)) and len(event[key]) <= 256
                           for key in ("event_id", "capability_id", "kind"))
                or event["kind"] not in {"OBSERVATION", "ACCEPTED_LESSON", "CORRECTION_APPLIED", "FOLLOWUP"}
                or not all(is_sha256(event.get(key))
                           for key in ("event_sha256", "receipt_sha256"))):
            continue
        event_id = event["event_id"]
        meta = replace(
            observation.meta,
            record_id=f"{observation.meta.record_id}:salience:{event_id}",
            coverage=CoverageState.PARTIAL,
            # The C06 issued-at counter is logical, not a Unix timestamp.
            observed_at=None,
            evidence_refs=(f"c06-salience-event:{event['event_sha256']}",),
            receipt_refs=(f"c06-source-receipt:{event['receipt_sha256']}",),
        )
        record = SalienceEventV2(
            meta, event_id, event["capability_id"],
            *(_axis(event.get(axis)) for axis in ("impact", "exigency", "novelty")),
            "UNKNOWN", event["kind"])
        if event_id in result and result[event_id] != record:
            return ()
        result[event_id] = record
    return tuple(result.values())
