"""Private-safe staging construction, bounded reads and verification."""
from __future__ import annotations
from dataclasses import dataclass
from .akasha_outbox import AkashaEventKind
from .bamf_projection import BamfProjectionEvent, ProjectionDomainContract
from .akasha_staging_contracts import (
    StagingProjection, PublicEvent, STAGING_PROJECTION_SCHEMA,
    _invalid, _sha, _time, _digest, _public_event, _public_payload,
)

VERIFIED_STAGE_SCHEMA = "bilqis.c10.verified-stage/v1"


MAX_PUBLIC_QUERY_LIMIT = 100


def build_staging_projection(
    events: tuple[BamfProjectionEvent, ...],
    domain: ProjectionDomainContract,
) -> StagingProjection:
    if (not isinstance(events, tuple)
            or any(not isinstance(item, BamfProjectionEvent)
                   for item in events)
            or not isinstance(domain, ProjectionDomainContract)):
        _invalid("BAMF_C10_STAGING_ARGUMENT_INVALID")
    # Durable queued events cannot be rebound by a caller-created wrapper.
    from .bamf_projection import read_projection_outbox
    if domain.outbox_path.exists():
        stored = {item.event.event_id: item for item in read_projection_outbox(domain.outbox_path)}
        for event in events:
            if event.event.event_id in stored and stored[event.event.event_id] != event:
                _invalid("BAMF_C10_STAGING_DURABLE_BINDING_DRIFT")
    for event in events:
        if (event.source_id != domain.source_id
                or event.release_digest != domain.release_digest
                or event.model_digest != domain.model_digest
                or event.evaluator_digest != domain.evaluator_digest
                or event.rights_digest != domain.rights_digest
                or event.as_of != domain.as_of):
            _invalid("BAMF_C10_STAGING_DOMAIN_DRIFT")
    public = tuple(sorted(
        (_public_event(item) for item in events),
        key=lambda item: item.event_id))
    if len({item.event_id for item in public}) != len(public):
        _invalid("BAMF_C10_STAGING_EVENT_DUPLICATE")
    counts = {}
    for event in public:
        counts[event.kind.value] = counts.get(event.kind.value, 0) + 1
    census = tuple(sorted(counts.items()))
    identity = {
        "schema_version": STAGING_PROJECTION_SCHEMA,
        "domain_digest": domain.digest,
        "census": census,
        "public_events": tuple(_public_payload(item) for item in public),
    }
    return StagingProjection(
        public, census, domain.digest, _digest(identity))


def query_public_projection(
    stage: StagingProjection, *, limit: int,
    kind: AkashaEventKind | None = None, as_of: int | None = None,
) -> tuple[PublicEvent, ...]:
    if (not isinstance(stage, StagingProjection)
            or type(limit) is not int
            or not 1 <= limit <= MAX_PUBLIC_QUERY_LIMIT
            or (kind is not None and not isinstance(kind, AkashaEventKind))
            or (as_of is not None and not _time(as_of))):
        _invalid("BAMF_C10_PUBLIC_QUERY_INVALID")
    StagingProjection.__post_init__(stage)
    return tuple(
        event for event in stage.public_events
        if (kind is None or event.kind is kind)
        and (as_of is None or event.recorded_at <= as_of)
        and (as_of is None or event.effective_time <= as_of)
    )[:limit]


@dataclass(frozen=True)
class VerifiedStage:
    stage: StagingProjection
    census_digest: str
    bounded_query_digest: str
    proof_digest: str
    schema_version: str = VERIFIED_STAGE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.stage, StagingProjection)
                or not all(_sha(item) for item in (
                    self.census_digest, self.bounded_query_digest,
                    self.proof_digest))
                or self.census_digest != _digest(self.stage.census)
                or self.bounded_query_digest != _query_digest(self.stage)
                or self.proof_digest != _digest({
                    "stage_digest": self.stage.stage_digest,
                    "census_digest": self.census_digest,
                    "bounded_query_digest": self.bounded_query_digest,
                })
                or self.schema_version != VERIFIED_STAGE_SCHEMA):
            _invalid("BAMF_C10_STAGING_PROOF_INVALID")


def _query_digest(stage: StagingProjection) -> str:
    queries = tuple(
        (kind.value, tuple(item.event_id for item in
            query_public_projection(
                stage, limit=MAX_PUBLIC_QUERY_LIMIT, kind=kind)))
        for kind in AkashaEventKind
    )
    return _digest(queries)


def verify_staging_projection(stage: StagingProjection) -> VerifiedStage:
    if not isinstance(stage, StagingProjection):
        _invalid("BAMF_C10_STAGING_ARGUMENT_INVALID")
    StagingProjection.__post_init__(stage)
    census_digest = _digest(stage.census)
    query_digest = _query_digest(stage)
    return VerifiedStage(
        stage, census_digest, query_digest,
        _digest({
            "stage_digest": stage.stage_digest,
            "census_digest": census_digest,
            "bounded_query_digest": query_digest,
        }))


VerifiedStage.__module__ = "bilqis_mlx.runtime.akasha_staging"
