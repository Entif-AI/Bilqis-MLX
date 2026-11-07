"""Operator-owned C12 receive, screen and accepted-publication composition."""
from __future__ import annotations

from pathlib import Path

from .adoption import _verify_export_clearance, publish_screened_delta_import
from .contracts import require
from .delta import apply_plastic_delta, screen_delta_candidate
from .exchange import receive_package
from .receiver import _load_current_generation, current_receiver_binding


def receive_screen_and_publish_package(
        sender_dir, staging_dir, package_sha256, run_dir, *,
        max_wire_bytes: int, source_context, artifact_path, target_capability: str,
        export_clearance, atlas_selection, source_frontier, authority_registry,
        reserve_gib: float = 100.0):
    """Apply one exact-binding package only through A12, C05, B12 and B13 owners."""
    run_dir = Path(run_dir)
    binding = current_receiver_binding(run_dir)
    exchange = receive_package(
        sender_dir, staging_dir, package_sha256, binding,
        max_wire_bytes=max_wire_bytes)
    require(exchange.plan.disposition == "EXACT_BINDING",
            "package is not eligible for receiver-state adoption")

    # Reject stale/revoked source authority before paying for the C05 screen.
    _, parent = _load_current_generation(run_dir)
    _verify_export_clearance(
        exchange.package, parent, export_clearance, atlas_selection,
        source_frontier, authority_registry)

    candidate = apply_plastic_delta(exchange.package, run_dir)
    screened = screen_delta_candidate(
        candidate, source_context, artifact_path, target_capability,
        run_dir=run_dir)
    return publish_screened_delta_import(
        screened, run_dir, export_clearance=export_clearance,
        atlas_selection=atlas_selection, source_frontier=source_frontier,
        authority_registry=authority_registry, reserve_gib=reserve_gib)
