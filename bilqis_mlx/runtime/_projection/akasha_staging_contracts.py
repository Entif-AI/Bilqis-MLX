"""Immutable public event and staging identities for C10.3."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
import re
from ..errors import ErrorBus, SCHOOL
from .akasha_outbox import AkashaEventKind, OWNER_FIXTURE_KINDS
from .bamf_projection import BamfProjectionEvent

PUBLIC_EVENT_SCHEMA = "bilqis.c10.public-event/v1"


STAGING_PROJECTION_SCHEMA = "bilqis.c10.staging-projection/v1"


PROMOTION_RECEIPT_SCHEMA = "bilqis.c10.promotion-receipt/v1"


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_AKASHA.INVALID, reason=reason)


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _time(value: object) -> bool:
    return type(value) is int and value >= 0


def _canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PublicEvent:
    event_id: str
    kind: AkashaEventKind
    subject_digest: str
    payload_digest: str
    source_receipt_sha256: str
    release_digest: str
    model_digest: str
    evaluator_digest: str
    rights_digest: str
    source_time: int
    effective_time: int
    observed_at: int
    recorded_at: int
    schema_version: str = PUBLIC_EVENT_SCHEMA

    def __post_init__(self) -> None:
        if self.kind in OWNER_FIXTURE_KINDS:
            _invalid("BAMF_C10_FIXTURE_PUBLIC_SCHEMA_REQUIRED")
        if (not isinstance(self.kind, AkashaEventKind)
                or not all(_sha(value) for value in (
                    self.event_id, self.subject_digest,
                    self.payload_digest, self.source_receipt_sha256,
                    self.release_digest, self.model_digest,
                    self.evaluator_digest, self.rights_digest))
                or not all(_time(value) for value in (
                    self.source_time, self.effective_time,
                    self.observed_at, self.recorded_at))
                or self.observed_at > self.recorded_at
                or self.schema_version != PUBLIC_EVENT_SCHEMA):
            _invalid("BAMF_C10_PUBLIC_EVENT_INVALID")


def _public_event(event: BamfProjectionEvent) -> PublicEvent:
    return PublicEvent(
        event_id=event.event.event_id,
        kind=event.event.kind,
        subject_digest=_digest(event.event.subject_id),
        payload_digest=event.event.payload_digest,
        source_receipt_sha256=event.event.source_receipt_sha256,
        release_digest=event.release_digest,
        model_digest=event.model_digest,
        evaluator_digest=event.evaluator_digest,
        rights_digest=event.rights_digest,
        source_time=event.event.source_time,
        effective_time=event.event.effective_time,
        observed_at=event.event.observed_at,
        recorded_at=event.event.recorded_at,
    )


def _public_payload(event: PublicEvent) -> dict:
    return {**asdict(event), "kind": event.kind.value}


@dataclass(frozen=True)
class StagingProjection:
    public_events: tuple[PublicEvent, ...]
    census: tuple[tuple[str, int], ...]
    domain_digest: str
    stage_digest: str
    schema_version: str = STAGING_PROJECTION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.public_events, tuple)
                or any(not isinstance(item, PublicEvent)
                       for item in self.public_events)
                or self.public_events != tuple(sorted(
                    self.public_events, key=lambda item: item.event_id))
                or len({item.event_id for item in self.public_events})
                != len(self.public_events)
                or not isinstance(self.census, tuple)
                or not _sha(self.domain_digest)
                or not _sha(self.stage_digest)
                or self.schema_version != STAGING_PROJECTION_SCHEMA):
            _invalid("BAMF_C10_STAGING_PROJECTION_INVALID")
        counts = {}
        for event in self.public_events:
            counts[event.kind.value] = counts.get(event.kind.value, 0) + 1
        if self.census != tuple(sorted(counts.items())):
            _invalid("BAMF_C10_STAGING_CENSUS_DRIFT")
        if self.stage_digest != _digest(self._identity_payload()):
            _invalid("BAMF_C10_STAGING_DIGEST_DRIFT")

    def _identity_payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "domain_digest": self.domain_digest,
            "census": self.census,
            "public_events": tuple(
                _public_payload(item) for item in self.public_events),
        }

    @property
    def canonical_json(self) -> str:
        return _canonical({
            **self._identity_payload(),
            "stage_digest": self.stage_digest,
        })

    @classmethod
    def from_canonical_json(cls, value: str) -> "StagingProjection":
        try:
            raw = json.loads(value)
            events = tuple(PublicEvent(
                **{**item, "kind": AkashaEventKind(item["kind"])})
                for item in raw["public_events"])
            return cls(
                public_events=events,
                census=tuple(tuple(item) for item in raw["census"]),
                domain_digest=raw["domain_digest"],
                stage_digest=raw["stage_digest"],
                schema_version=raw["schema_version"])
        except (TypeError, ValueError, KeyError):
            _invalid("BAMF_C10_STAGING_STORED_INVALID")


@dataclass(frozen=True)
class PromotionReceipt:
    previous_digest: str | None
    active_digest: str
    census_digest: str
    schema_version: str = PROMOTION_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if ((self.previous_digest is not None
             and not _sha(self.previous_digest))
                or not _sha(self.active_digest)
                or not _sha(self.census_digest)
                or self.schema_version != PROMOTION_RECEIPT_SCHEMA):
            _invalid("BAMF_C10_PROMOTION_RECEIPT_INVALID")


PublicEvent.__module__ = "bilqis_mlx.runtime.akasha_staging"

StagingProjection.__module__ = "bilqis_mlx.runtime.akasha_staging"

PromotionReceipt.__module__ = "bilqis_mlx.runtime.akasha_staging"
