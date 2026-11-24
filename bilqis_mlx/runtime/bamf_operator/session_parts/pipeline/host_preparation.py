"""Overlap only generation-independent host preparation with neural execution."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass
import time

from bilqis_mlx.errors import ErrorBus, SCHOOL


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_RESOURCES.INVALID, reason=reason)


@dataclass(frozen=True)
class PreparedHostStep:
    """One exact future lesson plus generation-independent prepared inputs."""

    ordinal: int
    # Exact source-packet transport identity already validated by CandidateSourceLane.
    # It is retained here as provenance; prepared_source_inputs carries the separately
    # recomputed semantic invalidation identity consumed by Factory preparation.
    source_identity: str
    lesson: object
    prepared_source_inputs: object
    preparation_wall_seconds: float
    overlap_wall_seconds: float
    host_wait_wall_seconds: float




def learning_first_prepare_step(execute_candidate, selection, context):
    """Return the ahead-preparation callback only for ordinary learning-first."""
    keywords = getattr(execute_candidate, "keywords", None)
    if not isinstance(keywords, dict) or keywords.get("learning_first_cache") is None:
        return None
    from bilqis_mlx.runtime.factory_training_preparation import (
        prepare_learning_first_source_inputs_ahead,
    )
    authenticated = selection.offer._planning_generation._authenticated_features

    def prepare(_ordinal, lesson):
        seed = getattr(lesson, "source_seed", None)
        return prepare_learning_first_source_inputs_ahead(
            context, authenticated, lesson.delivered,
            source_seed=selection.offer.source_seed if seed is None else seed,
            source_each=len(lesson.direct) + len(lesson.enrichment),
            source_identity=getattr(lesson, "prefetch_identity", None))

    return prepare


class CandidateHostPreparationPipeline:
    """Keep one future CPU preparation unit ahead of the sovereign optimizer."""

    def __init__(self, source_lane, horizon: int, prepare_step, metrics):
        if (source_lane is None or type(horizon) is not int or horizon < 1
                or not callable(prepare_step) or metrics is None):
            _invalid("BAMF_HOST_PREPARATION_PIPELINE_INVALID")
        self.source_lane = source_lane
        self.horizon = horizon
        self.prepare_step = prepare_step
        self.metrics = metrics
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="bamf-host-prepare")
        self.pending: dict[int, tuple[float, object]] = {}

    def _prepare(self, ordinal: int):
        started = time.monotonic()
        lesson = self.source_lane.lesson(ordinal)
        source_identity = getattr(lesson, "prefetch_identity", None)
        if not isinstance(source_identity, str) or not source_identity:
            _invalid("BAMF_HOST_PREPARATION_SOURCE_IDENTITY_REQUIRED")
        prepared = self.prepare_step(ordinal, lesson)
        if prepared is None:
            _invalid("BAMF_HOST_PREPARATION_RESULT_REQUIRED")
        finished = time.monotonic()
        return source_identity, lesson, prepared, started, finished

    def submit(self, ordinal: int) -> None:
        if ordinal > self.horizon:
            return
        if type(ordinal) is not int or ordinal < 1 or ordinal in self.pending:
            _invalid("BAMF_HOST_PREPARATION_STEP_INVALID")
        context = copy_context()
        self.pending[ordinal] = (
            time.monotonic(), self.executor.submit(context.run, self._prepare, ordinal))
        self.metrics.pipeline_submitted_steps += 1

    def take(self, ordinal: int) -> PreparedHostStep:
        pending = self.pending.pop(ordinal, None)
        if pending is None:
            _invalid("BAMF_HOST_PREPARATION_STEP_MISSING")
        _submitted_at, future = pending
        wait_started = time.monotonic()
        source_identity, lesson, prepared, started, finished = future.result()
        wait_seconds = max(0.0, time.monotonic() - wait_started)
        preparation_seconds = max(0.0, finished - started)
        overlap_seconds = max(0.0, min(finished, wait_started) - started)
        self.metrics.pipeline_prepared_steps += 1
        self.metrics.pipeline_host_preparation_seconds += preparation_seconds
        self.metrics.pipeline_host_overlap_seconds += overlap_seconds
        self.metrics.pipeline_host_wait_seconds += wait_seconds
        # Until the future resolves, the next Metal launch cannot begin. This is
        # host-clocked accelerator-idle wall, not a fabricated device timestamp.
        self.metrics.pipeline_accelerator_wait_for_host_seconds += wait_seconds
        return PreparedHostStep(
            ordinal, source_identity, lesson, prepared,
            preparation_seconds, overlap_seconds, wait_seconds)

    def discard_pending(self) -> None:
        close_started = time.monotonic()
        pending = tuple(self.pending.items())
        self.pending.clear()
        for _ordinal, (_submitted_at, future) in pending:
            self.metrics.pipeline_discarded_steps += 1
            if future.cancel():
                continue
            _identity, _lesson, _prepared, started, finished = future.result()
            preparation_seconds = max(0.0, finished - started)
            overlap_seconds = max(0.0, min(finished, close_started) - started)
            self.metrics.pipeline_host_preparation_seconds += preparation_seconds
            self.metrics.pipeline_host_overlap_seconds += overlap_seconds
            self.metrics.pipeline_discarded_preparation_seconds += preparation_seconds

    def close(self) -> None:
        self.discard_pending()
        self.executor.shutdown(wait=True, cancel_futures=True)


__all__ = (
    "CandidateHostPreparationPipeline", "PreparedHostStep",
    "learning_first_prepare_step",
)
