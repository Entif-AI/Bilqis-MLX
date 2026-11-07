"""Accepted-generation C09 correction and revalidation ingress."""
from __future__ import annotations

from pathlib import Path

from .accepted_correction_ledger import (
    accepted_correction_id, accepted_corrections, append_record,
    correction_record, revalidation_record,
)
from .accepted_correction_runtime import (
    _RUNTIME_OWNER, bind_accepted_registry, register_accepted_target,
    register_compiled_batch, register_solve_context, runtime,
)
from .atlas_revalidation_common import _invalid
from .atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from .atlas_source_authority import SourceAuthorityRegistry


def record_accepted_correction(
    run_dir: Path, event: CorrectionEvent,
    registry: SourceAuthorityRegistry,
) -> str:
    """Persist and synchronously deliver one signed correction to live owners."""
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache

    if not isinstance(event, CorrectionEvent):
        _invalid("BAMF_C09_CORRECTION_EVENT_REQUIRED")
    registry.verify_correction(event)
    run_dir = Path(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    record = correction_record(cache.accepted_manifest_sha256, event)
    append_record(run_dir, cache.accepted_manifest_sha256, record)
    runtime(run_dir, cache.accepted_manifest_sha256).deliver(
        record["event_id"], event, registry)
    object.__setattr__(cache, "_correction_registry", registry)
    return record["event_id"]


def record_accepted_revalidation(
    run_dir: Path, frontier: RevalidationFrontier,
    registry: SourceAuthorityRegistry,
) -> str:
    """Persist signed source recomputation evidence and advance live holds."""
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache

    if not isinstance(frontier, RevalidationFrontier) or not frontier.results:
        _invalid("BAMF_C09_REVALIDATION_FRONTIER_REQUIRED")
    for result in frontier.results:
        registry.verify_revalidation(result)
    run_dir = Path(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    corrections = {
        event.event_id: event
        for _event_id, event in accepted_corrections(
            run_dir, cache.accepted_manifest_sha256, registry)
    }
    for result in frontier.results:
        correction = corrections.get(result.correction_event_id)
        if (correction is None
                or correction.source_receipt_sha256
                != result.correction_receipt_sha256):
            _invalid("BAMF_C09_REVALIDATION_CORRECTION_MISSING")
    record = revalidation_record(cache.accepted_manifest_sha256, frontier)
    append_record(run_dir, cache.accepted_manifest_sha256, record)
    runtime(run_dir, cache.accepted_manifest_sha256).deliver_revalidation(
        record["event_id"], frontier, registry)
    object.__setattr__(cache, "_correction_registry", registry)
    return record["event_id"]


__all__ = (
    "_RUNTIME_OWNER", "accepted_correction_id", "accepted_corrections",
    "bind_accepted_registry", "record_accepted_correction",
    "record_accepted_revalidation", "register_accepted_target",
    "register_compiled_batch", "register_solve_context",
)
