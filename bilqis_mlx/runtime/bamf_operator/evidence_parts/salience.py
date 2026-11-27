"""Read the strict producer's already verified signed C06 history."""
from bilqis_mlx.learning.salience_history import SalienceHistory

MAX_OBSERVED_SALIENCE_EVENTS = 8
MAX_OBSERVED_SALIENCE_ID_LENGTH = 256


def issued_salience_observations(history):
    if not isinstance(history, SalienceHistory):
        return ()
    return tuple({
        "event_id": event.event_id,
        "event_sha256": event.digest(),
        "receipt_sha256": event.source_receipt_sha256,
        "capability_id": event.evidence.scope.capability_id,
        "kind": event.kind.value,
        **{axis: getattr(event.evidence, axis).ordinal.name
           for axis in ("impact", "exigency", "novelty")},
    } for event in history.events[-MAX_OBSERVED_SALIENCE_EVENTS:])
