"""Read-only semantic release and Akasha materialization projection for Mission Control."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.mission_control import (
    AuthorityClass, CoverageState, DataValue, RecordMeta, SemanticProjectionSnapshot,
    SemanticProjectionState, SemanticReleaseSnapshot, ValueOrigin, ValueState,
)
from bilqis_mlx.runtime.akasha_outbox import (
    AkashaEventKind, read_outbox_read_only,
)
from bilqis_mlx.mission_control.semantic.projection import (
    project_semantic_atlas_records,
)

from ..native_contracts import AuthenticatedGeneration, invalid, run_ref


def _present(value, units=None):
    return DataValue(ValueState.PRESENT, ValueOrigin.SOURCE_AUTHORITATIVE, value, units)


def _missing():
    return DataValue(ValueState.MISSING, None, None)


def _release_meta(generation, snapshot):
    run = run_ref(generation)
    return RecordMeta(
        record_id=f"semantic-release:{run.run_id}:{run.generation}",
        run=run,
        materialized_at=0,
        observed_at=None,
        as_of=None,
        coverage=CoverageState.COMPLETE,
        authority=AuthorityClass.SOURCE_AUTHORITATIVE,
        source_refs=(
            f"atlas-bundle:{snapshot.bundle_id}",
            f"semantic-release:{snapshot.release_sha256}",
            f"source-bundle:{snapshot.source_bundle_id}",
        ),
        receipt_refs=(
            f"bamf-acceptance:{generation.acceptance_sha256}",
            f"bamf-manifest:{generation.manifest_sha256}",
        ),
    )


def _release_record(generation, snapshot):
    run = run_ref(generation)
    if run.semantic_release_sha256 != snapshot.release_sha256:
        invalid("CONTROL_PLANE_SEMANTIC_RELEASE_MISMATCH")
    counts = snapshot.counts
    return SemanticReleaseSnapshot(
        meta=_release_meta(generation, snapshot),
        atlas_bundle_id=snapshot.bundle_id,
        semantic_release_sha256=snapshot.release_sha256,
        source_bundle_id=snapshot.source_bundle_id,
        canonical_rdf_sha256=snapshot.canonical_rdf_sha256,
        coverage_sha256=snapshot.coverage_sha256,
        conformance_sha256=snapshot.conformance_sha256,
        source_rows_sha256=snapshot.source_rows_sha256,
        active_set_sha256=snapshot.active_set_sha256,
        conformance_status="COMPLETE",
        coverage_status=_missing(),
        frontier_debt=_missing(),
        source_rows=counts.source_rows,
        semantic_concepts=counts.semantic_concepts,
        active_abi_indices=counts.active_abi_indices,
        source_held=counts.source_held,
        source_ir_only=counts.source_ir_only,
        implementation_uncovered=counts.implementation_uncovered,
    )


def _projection_meta(generation, *, event=None, coverage=CoverageState.UNKNOWN, receipt_refs=()):
    run = run_ref(generation)
    recorded_at = 0 if event is None or event.recorded_at is None else event.recorded_at
    observed_at = None if event is None else event.observed_at
    effective_time = None if event is None else event.effective_time
    return RecordMeta(
        record_id=f"semantic-projection:{run.run_id}:{run.generation}",
        run=run,
        materialized_at=recorded_at,
        observed_at=observed_at,
        as_of=effective_time,
        coverage=coverage,
        authority=AuthorityClass.DERIVED,
        source_refs=(f"semantic-release:{run.semantic_release_sha256}",),
        evidence_refs=() if event is None else (f"akasha-event:{event.event_id}",),
        receipt_refs=tuple(receipt_refs),
    )


def _empty_projection(generation, state):
    coverage = CoverageState.PARTIAL if state is SemanticProjectionState.ERROR else CoverageState.UNKNOWN
    return SemanticProjectionSnapshot(
        _projection_meta(generation, coverage=coverage), state,
        *(_missing() for _ in range(9)),
    )


def _event_payload(event):
    try:
        payload = json.loads(event.payload_json)
    except (TypeError, json.JSONDecodeError):
        invalid("CONTROL_PLANE_SEMANTIC_MATERIALIZATION_INVALID")
    if not isinstance(payload, dict):
        invalid("CONTROL_PLANE_SEMANTIC_MATERIALIZATION_INVALID")
    return payload


def _projection_record(generation, snapshot, events):
    materializations = tuple(event for event in events if event.kind is AkashaEventKind.MATERIALIZATION)
    if not materializations:
        return _empty_projection(generation, SemanticProjectionState.MISSING)

    exact = []
    for event in materializations:
        payload = _event_payload(event)
        if (payload.get("canonical_rdf_sha256") == snapshot.canonical_rdf_sha256
                and payload.get("semantic_coverage_sha256") == snapshot.coverage_sha256):
            exact.append((event, payload))

    candidates = exact or [(event, _event_payload(event)) for event in materializations]
    event, payload = max(candidates, key=lambda pair: (
        -1 if pair[0].recorded_at is None else pair[0].recorded_at,
        pair[0].event_id,
    ))
    if exact:
        state = (SemanticProjectionState.CURRENT
                 if str(payload.get("coverage_status", "")).lower() == "complete"
                 else SemanticProjectionState.PARTIAL)
    else:
        state = SemanticProjectionState.STALE
    coverage = CoverageState.PARTIAL if state in {
        SemanticProjectionState.PARTIAL, SemanticProjectionState.STALE,
    } else CoverageState.COMPLETE
    receipt = payload["materialization_receipt_sha256"]
    return SemanticProjectionSnapshot(
        meta=_projection_meta(
            generation, event=event, coverage=coverage,
            receipt_refs=(f"materialization-receipt:{receipt}",),
        ),
        state=state,
        graph=_present(payload["graph"]),
        owner=_present(payload["owner"]),
        materialization_receipt_sha256=_present(receipt),
        projection_version=_present(payload["projection_version"]),
        coverage_status=_present(payload["coverage_status"]),
        canonical_rdf_sha256=_present(payload["canonical_rdf_sha256"]),
        semantic_coverage_sha256=_present(payload["semantic_coverage_sha256"]),
        importer_implementation_sha256=_present(payload["importer_implementation_sha256"]),
        smoke_suite_sha256=_present(payload["smoke_suite_sha256"]),
    )


def accepted_semantic_release_records(run_dir: Path, generation: AuthenticatedGeneration):
    """Project the accepted release and durable materialization evidence without mutation."""
    root = Path(run_dir)
    from bilqis_mlx.runtime.bamf_bundle import (
        read_current_accepted_generation_semantic_snapshot,
    )
    try:
        snapshot = read_current_accepted_generation_semantic_snapshot(root)
    except BilqisError:
        return (_empty_projection(generation, SemanticProjectionState.ERROR),)
    release = _release_record(generation, snapshot)
    try:
        events = read_outbox_read_only(root / "akasha-outbox.sqlite3")
        projection = _projection_record(generation, snapshot, events)
    except BilqisError:
        projection = _empty_projection(generation, SemanticProjectionState.ERROR)
    active_indices = tuple(
        entry.index for entry in getattr(snapshot, "abi_entries", ())
        if getattr(entry, "active", False))
    atlas = project_semantic_atlas_records(
        snapshot, run_ref(generation), active_indices, materialized_at=0)
    return release, projection, *atlas


__all__ = ("accepted_semantic_release_records",)
