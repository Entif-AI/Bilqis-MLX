"""C10.2 source/release/model/evaluator/rights-bound local outbox views.

This boundary never calls SKOS, Akasha or a graph client. It enqueues
immutable internal-only events and lets the trainer continue during outages.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re

from ..errors import ErrorBus, SCHOOL
from .akasha_outbox import AkashaEvent, append_outbox_batch, pending_events


PROJECTION_DOMAIN_SCHEMA = "bilqis.c10.projection-domain/v1"
BAMF_PROJECTION_EVENT_SCHEMA = "bilqis.c10.bamf-projection-event/v1"
PROJECTION_RECEIPT_SCHEMA = "bilqis.c10.projection-receipt/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_AKASHA.INVALID, reason=reason)


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _time(value: object) -> bool:
    return type(value) is int and value >= 0


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ProjectionDomainContract:
    outbox_path: Path
    source_id: str
    release_digest: str
    model_digest: str
    evaluator_digest: str
    rights_digest: str
    as_of: int
    schema_version: str = PROJECTION_DOMAIN_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.outbox_path, Path)
                or not _name(self.source_id)
                or not all(_sha(item) for item in (
                    self.release_digest, self.model_digest,
                    self.evaluator_digest, self.rights_digest))
                or not _time(self.as_of)
                or self.schema_version != PROJECTION_DOMAIN_SCHEMA):
            _invalid("BAMF_C10_PROJECTION_DOMAIN_INVALID")

    @property
    def digest(self) -> str:
        return _digest({
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "release_digest": self.release_digest,
            "model_digest": self.model_digest,
            "evaluator_digest": self.evaluator_digest,
            "rights_digest": self.rights_digest,
            "as_of": self.as_of,
        })


@dataclass(frozen=True)
class BamfProjectionEvent:
    event: AkashaEvent
    source_id: str
    release_digest: str
    model_digest: str
    evaluator_digest: str
    rights_digest: str
    as_of: int
    schema_version: str = BAMF_PROJECTION_EVENT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.event, AkashaEvent)
                or not _name(self.source_id)
                or not all(_sha(item) for item in (
                    self.release_digest, self.model_digest,
                    self.evaluator_digest, self.rights_digest))
                or not _time(self.as_of)
                or self.as_of < self.event.recorded_at
                or self.schema_version != BAMF_PROJECTION_EVENT_SCHEMA):
            _invalid("BAMF_C10_PROJECTION_EVENT_INVALID")
        self.event.validate()


@dataclass(frozen=True)
class ProjectionReceipt:
    event_ids: tuple[str, ...]
    payload_digests: tuple[str, ...]
    appended_count: int
    duplicate_count: int
    pending_count: int
    domain_digest: str
    schema_version: str = PROJECTION_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.event_ids, tuple)
                or any(not _sha(item) for item in self.event_ids)
                or len(set(self.event_ids)) != len(self.event_ids)
                or not isinstance(self.payload_digests, tuple)
                or len(self.payload_digests) != len(self.event_ids)
                or any(not _sha(item) for item in self.payload_digests)
                or any(type(item) is not int or item < 0 for item in (
                    self.appended_count, self.duplicate_count,
                    self.pending_count))
                or not _sha(self.domain_digest)
                or self.schema_version != PROJECTION_RECEIPT_SCHEMA):
            _invalid("BAMF_C10_PROJECTION_RECEIPT_INVALID")


def project_generation_outbox(
    events: tuple[BamfProjectionEvent, ...],
    domain_contract: ProjectionDomainContract,
) -> ProjectionReceipt:
    """Preflight the whole batch, then enqueue; never contact the graph."""
    if (not isinstance(events, tuple)
            or any(not isinstance(item, BamfProjectionEvent)
                   for item in events)
            or not isinstance(domain_contract, ProjectionDomainContract)):
        _invalid("BAMF_C10_PROJECTION_ARGUMENT_INVALID")
    for item in events:
        if (item.source_id != domain_contract.source_id
                or item.release_digest != domain_contract.release_digest
                or item.model_digest != domain_contract.model_digest
                or item.evaluator_digest != domain_contract.evaluator_digest
                or item.rights_digest != domain_contract.rights_digest
                or item.as_of != domain_contract.as_of):
            _invalid("BAMF_C10_PROJECTION_DOMAIN_DRIFT")
    unique = {}
    for item in events:
        prior = unique.get(item.event.event_id)
        if prior is not None and prior != item:
            _invalid("BAMF_C10_EVENT_ID_CONFLICT")
        unique[item.event.event_id] = item
    appended = append_outbox_batch(domain_contract.outbox_path, tuple(
        (item.event, {key: value for key, value in asdict(item).items() if key != "event"})
        for item in unique.values()))
    return ProjectionReceipt(
        event_ids=tuple(unique),
        payload_digests=tuple(
            item.event.payload_digest for item in unique.values()),
        appended_count=appended,
        duplicate_count=len(events) - appended,
        pending_count=len(pending_events(domain_contract.outbox_path)),
        domain_digest=domain_contract.digest,
    )


def read_projection_outbox(path: Path) -> tuple[BamfProjectionEvent, ...]:
    """Cold-read complete bound envelopes; bare historical rows remain unbound."""
    from .akasha_outbox import _outbox_connection, _read_event
    if not path.exists():
        return ()
    with _outbox_connection(path) as connection:
        rows = connection.execute(
            'SELECT envelope_json, projection_binding_json FROM akasha_events ORDER BY seq').fetchall()
    result = []
    for envelope, binding in rows:
        if binding is None:
            _invalid('BAMF_C10_UNBOUND_HISTORICAL_EVENT')
        try:
            result.append(BamfProjectionEvent(event=_read_event((envelope,)), **json.loads(binding)))
        except (ValueError, TypeError):
            _invalid('BAMF_C10_STORED_DOMAIN_BINDING_INVALID')
    return tuple(result)
