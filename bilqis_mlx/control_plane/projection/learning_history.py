"""Derived bounded Home evidence over the authenticated cumulative episode rows."""
from __future__ import annotations

from bilqis_mlx.mission_control import (
    CandidateDecision, CandidateOutcome, CoverageState, LearningEpisode,
    LearningHistorySummary, PartialEnvelope, StaleEnvelope, UnavailableEnvelope,
    UnavailableReason,
    encode_record,
)
from bilqis_mlx.mission_control.query_selection import record_sort_key
from ..native_contracts import canonical, record_meta, run_ref, sha


def _episode_inputs(records, run):
    rows = tuple(sorted((row for row in records
                        if type(row) in (LearningEpisode, CandidateDecision)
                        and row.meta.run.run_id == run.run_id),
                        key=record_sort_key, reverse=True))
    ids = {row.meta.record_id for row in rows}
    markers = tuple(sorted((row for row in records if (
        (isinstance(row, PartialEnvelope) and row.partial_record_id in ids)
        or (isinstance(row, StaleEnvelope) and row.stale_record_id in ids)
        or (isinstance(row, UnavailableEnvelope)
            and row.resource in ("episode", f"episode:{run.run_id}")
            and (row.meta.run is None or row.meta.run.run_id == run.run_id)))),
        key=record_sort_key))
    return rows, markers


def _summary(tip, run, rows, markers):
    # A stale or denied family must retain its CP03 posture, not become a
    # seemingly fresh aggregate. Let the consumer query the detailed family.
    if any(isinstance(marker, StaleEnvelope) or (
            isinstance(marker, UnavailableEnvelope)
            and marker.reason is UnavailableReason.DENIED) for marker in markers):
        return None
    episodes = tuple(row for row in rows if isinstance(row, LearningEpisode))
    decisions = tuple(row for row in rows if isinstance(row, CandidateDecision))
    recent = tuple(sorted(decisions, key=lambda row: (
        row.meta.observed_at if row.meta.observed_at is not None
        else row.meta.materialized_at), reverse=True)[:8])
    active = next((row for row in episodes if row.state != "COMPLETED"), None)
    digest = sha(canonical([encode_record(row) for row in (*rows, *markers)]))
    complete = not markers and all(row.meta.coverage is CoverageState.COMPLETE for row in rows)
    meta = record_meta(
        f"learning-history:{run.generation_manifest_sha256}:{digest}", run, tip,
        native={"recorded_at": max((row.meta.materialized_at for row in rows), default=0)},
        evidence_refs=(f"episode-evidence:{digest}",),
        coverage=CoverageState.COMPLETE if complete else CoverageState.PARTIAL,
    )
    return LearningHistorySummary(
        meta, digest, len(episodes), len(decisions),
        sum(row.outcome is CandidateOutcome.ACCEPTED for row in decisions),
        sum(row.outcome is CandidateOutcome.REJECTED for row in decisions),
        recent, active)


class LearningHistoryProjection:
    """Reuse a summary until the accepted tip or exact episode evidence changes."""

    def __init__(self):
        self.inputs = self.summary = None

    def __call__(self, tip, records):
        run = run_ref(tip)
        rows, markers = _episode_inputs(records, run)
        inputs = (run, rows, markers)
        if inputs != self.inputs:
            self.summary = _summary(tip, run, rows, markers)
            self.inputs = inputs
        return self.summary


def learning_history_summary(tip, records):
    return LearningHistoryProjection()(tip, records)
