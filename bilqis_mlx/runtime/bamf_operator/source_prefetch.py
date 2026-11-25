"""CPU-only source preparation for the persistent BAMF operator."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time
from typing import TYPE_CHECKING

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.factory.teaching import optional_teaching_rows
from bilqis_mlx.runtime.source_prefetch import (
    ImmutableSourcePacket,
    SCHEMA,
    SOURCE_WORKER_COUNTS,
    thaw_source_packet,
)
from .session_parts.rehearsal import materialize_rehearsal_rows
from .session_parts.fresh_support import materialize_fresh_support
from .source_prefetch_contracts import (
    REQUEST_SCHEMA, prepare_priority_source_packet, priority_source_request,
)

if TYPE_CHECKING:
    from bilqis_mlx.runtime.retention.local_preflight import ExactMissInstruction


SERIAL_SOURCE_WORKERS = 0
NATIVE_SOURCE_WORKER_COUNTS = (SERIAL_SOURCE_WORKERS, *SOURCE_WORKER_COUNTS)


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_RESOURCES.INVALID, reason=reason)


@dataclass
class SourcePrefetchMetrics:
    submitted_steps: int = 0
    prepared_steps: int = 0
    serial_steps: int = 0
    wait_seconds: float = 0.0
    overlap_seconds: float = 0.0
    pipeline_submitted_steps: int = 0
    pipeline_prepared_steps: int = 0
    pipeline_discarded_steps: int = 0
    pipeline_discarded_preparation_seconds: float = 0.0
    pipeline_host_preparation_seconds: float = 0.0
    pipeline_host_overlap_seconds: float = 0.0
    pipeline_host_wait_seconds: float = 0.0
    pipeline_accelerator_wait_for_host_seconds: float = 0.0


@dataclass(frozen=True)
class CandidateLessonRows:
    direct: tuple
    prior: tuple = ()
    preservation: tuple = ()
    retention_support: tuple = ()
    enrichment: tuple = ()
    rehearsal_bindings: tuple = ()
    rehearsal_authorities: tuple = ()
    fresh_support: tuple = ()
    fresh_support_binding: dict | None = None
    fresh_support_authority: object = None
    fresh_support_unavailable_reason: str | None = None
    fresh_support_depth_control: str | None = None
    prefetch_identity: str | None = None
    weakness_unavailable: tuple[tuple[str, str], ...] = ()
    source_seed: int | None = None
    primary_lesson: object = None
    exact_miss_instruction: ExactMissInstruction | None = None

    @property
    def delivered(self) -> tuple:
        return (
            *self.direct, *self.prior, *self.preservation,
            *self.retention_support, *self.enrichment, *self.fresh_support)

    @property
    def rehearsal_by_id(self) -> dict[str, str]:
        return {
            **{row["id"]: "prior" for row in self.prior},
            **{row["id"]: "preservation" for row in self.preservation},
            **{row["id"]: "retention_support" for row in self.retention_support},
        }

    @property
    def rehearsal_bindings_by_id(self) -> dict[str, dict]:
        return {item["row_id"]: item for item in self.rehearsal_bindings}

    @property
    def rehearsal_authorities_by_id(self) -> dict[str, object]:
        return dict(self.rehearsal_authorities)

    @property
    def fresh_support_by_id(self) -> dict[str, str]:
        return {row["id"]: "fresh_support" for row in self.fresh_support}


class CandidateSourceLane:
    """Schedule exact future source packets without owning neural state."""

    def __init__(self, selection, source_context, parent, horizon: int, *,
                 rehearsal_plan=None,
                 policy_support_enabled: bool = False,
                 workers: int, executor, metrics: SourcePrefetchMetrics):
        if (type(workers) is not int or workers not in NATIVE_SOURCE_WORKER_COUNTS
                or (workers == SERIAL_SOURCE_WORKERS) != (executor is None)
                or type(policy_support_enabled) is not bool):
            _invalid("BAMF_SOURCE_PREFETCH_WORKER_CONFIGURATION_INVALID")
        self.selection = selection
        self.source_context = source_context
        self.parent = parent
        self.horizon = horizon
        self.workers = workers
        self.executor = executor
        self.metrics = metrics
        self.rehearsal_plan = rehearsal_plan
        self.policy_support_enabled = policy_support_enabled
        self.pending = {}
        self.rehearsal_custody = {}
        self.weakness_unavailable = {}
        self.primary_lessons = {}
        # The ordered preparation prefix projects exposure for subsequent
        # packets. Only executed steps enter the durable outcome.
        self.weakness_exposures = dict(
            getattr(rehearsal_plan, "weakness_exposures", ()))
        self.fresh_support_custody = {}
        source_registry = getattr(source_context, "source_registry", None)
        graph = getattr(source_context, "graph", None)
        self.enrichment_rows = (
            () if source_registry is None or graph is None else
            optional_teaching_rows(
                getattr(source_context, "source_root", None), graph,
                source_context.release, source_registry,
                capability=selection.offer.capability_id,
                seed=selection.offer.source_seed, enabled=True))
        if workers:
            for ordinal in range(1, min(workers, horizon) + 1):
                self._submit(ordinal)

    def _target_batch(self, ordinal):
        offer = self.selection.offer
        if not self.policy_support_enabled or ordinal == 1:
            return offer.rows(), offer.source_authority, offer.source_seed
        identity = self.selection.visit.identity.visit_id
        seed = int(hashlib.sha256(
            f"{identity}|{offer.source_seed}|target|{ordinal}".encode()
        ).hexdigest()[:16], 16)
        if (getattr(self.selection, "metadata", None) or {}).get("primary_lesson") is not None:
            from bilqis_mlx.runtime.priority_lesson import prepare_step_primary_lesson
            lesson = prepare_step_primary_lesson(
                self.source_context, self.parent, self.selection, ordinal, seed)
            self.primary_lessons[ordinal] = lesson
            offer = lesson.offer
            return offer.rows(), offer.source_authority, offer.source_seed
        rows, authority = self.source_context.draw_bound_rows(
            seed=seed, capability=offer.capability_id, each=offer.source_each)
        return rows, authority, seed

    def _request(self, ordinal):
        target_batch = self._target_batch(ordinal)
        rehearsal = (
            None if self.rehearsal_plan is None else
            materialize_rehearsal_rows(
                self.source_context, self.rehearsal_plan, ordinal,
                reserved_rows=(*target_batch[0], *self.enrichment_rows),
                exposure_counts=self.weakness_exposures))
        if rehearsal is not None:
            self.weakness_unavailable[ordinal] = rehearsal.weakness_unavailable
            for binding in rehearsal.bindings:
                key = binding.get("weakness_debt_key")
                if key is not None:
                    self.weakness_exposures[key] = self.weakness_exposures.get(key, 0) + 1
        self.rehearsal_custody[ordinal] = (
            () if rehearsal is None else rehearsal.authorities)
        fresh_support = None
        if self.policy_support_enabled:
            rehearsal_rows = () if rehearsal is None else (
                *rehearsal.prior, *rehearsal.preservation,
                *rehearsal.retention_support)
            fresh_support = materialize_fresh_support(
                self.source_context, self.selection, self.rehearsal_plan, ordinal,
                reserved_rows=(
                    *target_batch[0], *rehearsal_rows,
                    *self.enrichment_rows))
            self.fresh_support_custody[ordinal] = fresh_support.authority
        return priority_source_request(
            self.selection, self.source_context, self.parent, ordinal,
            enrichment_rows=self.enrichment_rows,
            rehearsal_plan=self.rehearsal_plan, rehearsal=rehearsal,
            fresh_support=fresh_support, target_batch=target_batch)

    def _submit(self, ordinal):
        request = self._request(ordinal)
        self.pending[ordinal] = (
            request, time.monotonic(),
            self.executor.submit(prepare_priority_source_packet, request))
        self.metrics.submitted_steps += 1

    def lesson(self, ordinal: int) -> CandidateLessonRows:
        if self.workers:
            request, submitted_at, future = self.pending.pop(ordinal)
            wait_started = time.monotonic()
            packet = future.result()
            self.metrics.wait_seconds += time.monotonic() - wait_started
            self.metrics.overlap_seconds += max(0.0, wait_started - submitted_at)
            next_ordinal = ordinal + self.workers
            if next_ordinal <= self.horizon:
                self._submit(next_ordinal)
            self.metrics.prepared_steps += 1
        else:
            request = self._request(ordinal)
            wait_started = time.monotonic()
            packet = prepare_priority_source_packet(request)
            self.metrics.wait_seconds += time.monotonic() - wait_started
            self.metrics.serial_steps += 1
        if (type(packet) is not ImmutableSourcePacket
                or packet.identity != request["identity"]):
            _invalid("BAMF_SOURCE_PREFETCH_PACKET_IDENTITY_DRIFT")
        payload = thaw_source_packet(packet)
        if (not isinstance(payload, dict) or payload.get("schema") != SCHEMA
                or payload.get("identity") != request["identity"]
                or not isinstance(payload.get("prior"), list)
                or not isinstance(payload.get("preservation"), list)
                or not isinstance(payload.get("retention_support"), list)):
            _invalid("BAMF_SOURCE_PREFETCH_PACKET_INVALID")
        rows = payload.get("fresh")
        enrichment = payload.get("teaching_enrichment_rows")
        if not isinstance(rows, list) or len(rows) != self.selection.offer.source_each:
            _invalid("BAMF_SOURCE_PREFETCH_PACKET_INVALID")
        if (not isinstance(enrichment, list)
                or any(type(row) is not dict for row in enrichment)):
            _invalid("BAMF_SOURCE_PREFETCH_PACKET_INVALID")
        fresh_support = payload.get("fresh_support", [])
        fresh_binding = payload.get("fresh_support_binding")
        fresh_control = payload.get("fresh_support_depth_control")
        fresh_reason = payload.get("fresh_support_unavailable_reason")
        if (not isinstance(fresh_support, list)
                or any(type(row) is not dict for row in fresh_support)):
            _invalid("BAMF_SOURCE_PREFETCH_PACKET_INVALID")
        fresh_authority = self.fresh_support_custody.pop(ordinal, None)
        if fresh_support and fresh_authority is None:
            _invalid("BAMF_SOURCE_PREFETCH_FRESH_SUPPORT_AUTHORITY_MISSING")
        return CandidateLessonRows(
            tuple(rows), tuple(payload["prior"]), tuple(payload["preservation"]),
            tuple(payload["retention_support"]), tuple(enrichment),
            tuple(request.get("rehearsal_bindings", ())),
            tuple(self.rehearsal_custody.pop(ordinal, ())),
            tuple(fresh_support), fresh_binding, fresh_authority,
            fresh_reason, fresh_control, request["identity"],
            self.weakness_unavailable.pop(ordinal, ()), request["source_seed"],
            self.primary_lessons.pop(ordinal, None),
            getattr(self.rehearsal_plan, "exact_miss_instruction", None))

    def rows(self, ordinal: int):
        return self.lesson(ordinal).direct
