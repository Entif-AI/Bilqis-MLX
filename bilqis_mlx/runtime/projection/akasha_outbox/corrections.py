"""C09 correction intent projection into the local outbox."""
from pathlib import Path

from .contracts import AkashaEventKind, _invalid
from .events import AkashaEvent
from .store import append_outbox

def events_from_c09_intent(intent, correction, ledger, authority_registry):
    """Bridge signed C09 source invalidations into C10's durable event IDs."""
    from ...atlas_revalidation import CorrectionEvent, SourceAuthorityRegistry
    from ...atlas_requalification import (
        C10InvalidationIntent, RequalificationLedger,
        RequalificationStatus,
    )

    if (not isinstance(intent, C10InvalidationIntent)
            or not isinstance(correction, CorrectionEvent)
            or not isinstance(ledger, RequalificationLedger)
            or not isinstance(authority_registry, SourceAuthorityRegistry)):
        _invalid("BAMF_C10_C09_INTENT_ARGUMENT_INVALID")
    authority_registry.verify_correction(correction)
    if (intent.correction_event_id != correction.event_id
            or intent.source_receipt_sha256
            != correction.source_receipt_sha256
            or intent.delivery_state != "PENDING_C10"):
        _invalid("BAMF_C10_C09_INTENT_SOURCE_DRIFT")
    events = []
    for capability_id in intent.capability_ids:
        support = ledger.capability(capability_id)
        if support.status is not RequalificationStatus.REQUALIFICATION_REQUIRED:
            _invalid("BAMF_C10_C09_INTENT_CAPABILITY_NOT_HELD")
        events.append(AkashaEvent.from_payload(
            kind=AkashaEventKind.REQUALIFICATION,
            subject_id=capability_id,
            source_receipt_sha256=correction.source_receipt_sha256,
            payload={
                "capability_id": capability_id,
                "retained_generation_sha256":
                    support.retained_generation_sha256,
                "status": "REQUALIFICATION_REQUIRED",
                "source_intent_event_id": intent.event_id,
                "affected_artifact_ids": list(intent.affected_artifact_ids),
            },
            source_time=correction.source_time,
            effective_time=correction.effective_time,
            observed_at=correction.observed_at,
            recorded_at=correction.recorded_at,
        ))
    return tuple(events)


def append_c09_intent(
    path: Path, intent, correction, ledger, authority_registry,
) -> int:
    """Idempotent C09->C10 outbox enqueue; external Akasha send is separate."""
    events = events_from_c09_intent(
        intent, correction, ledger, authority_registry)
    return sum(append_outbox(path, event) for event in events)
