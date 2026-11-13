"""One-step C07 semantic-delta continuation for the disposable C13 lineage."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from bilqis_mlx.factory.atlas_frontier import next_atlas_delta
from bilqis_mlx.paths import LEGACY_SOURCE
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_admission import (
    enroll_accepted_atlas_lease_v2,
    read_accepted_atlas_lease_v2,
    read_atlas_enrollment_request_v2,
)
from bilqis_mlx.runtime.atlas_flywheel_runtime import AcceptedAtlasFlywheelSupervisor
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation

from scripts.bamf.c13.delivery_runtime import record_append_only_semantic_delta


PRODUCTION_RESERVE_GIB = 100.0
STAGE_SCHEMA = "bilqis.c13.semantic-delta-stage/v1"


def _lease(run_dir: Path, request_path: str | Path | None, host):
    source_authority = host.source_authority()
    current = read_accepted_atlas_lease_v2(
        run_dir, source_authority=source_authority)
    if current is not None:
        return current
    if request_path is None:
        raise ValueError("BAMF_C13_SIGNED_ENROLLMENT_REQUEST_REQUIRED")
    request = read_atlas_enrollment_request_v2(request_path)
    return enroll_accepted_atlas_lease_v2(
        run_dir,
        request,
        human_started=True,
        source_authority=source_authority,
    )


def apply_next_atlas_delta(
    run_dir: str | Path,
    *,
    request_path: str | Path | None = None,
    reserve_gib: float = PRODUCTION_RESERVE_GIB,
) -> dict:
    """Advance exactly one A09-selected C07 delta; never choose or skip a handoff."""
    run_dir = Path(run_dir).resolve()
    host = AcceptedRuntimeHost(run_dir)
    lease = _lease(run_dir, request_path, host)
    parent = load_accepted_generation(run_dir)
    parent_graph = host.source_context(source_root=LEGACY_SOURCE.resolve()).graph
    supervisor = AcceptedAtlasFlywheelSupervisor(run_dir, parent_graph, reserve_gib)
    state = supervisor.load_state()
    planned = next_atlas_delta(state.epoch, state.learner_evidence, state.plan)
    if not hasattr(planned, "receipt"):
        return {
            "schema": STAGE_SCHEMA,
            "status": "NO_DELTA_ADOPTED",
            "planner_status": getattr(planned, "value", str(planned)),
            "lease_sha256": lease.digest(),
            "parent_generation": parent.generation,
            "parent_optimizer_step": parent.retained_state.optimizer_step,
            "semantic_delta": None,
        }
    introduced = tuple(planned.receipt.selection.introduced_semantic_ids)
    result = supervisor.admit(planned)
    current = load_accepted_generation(run_dir)
    record = {
        "schema": STAGE_SCHEMA,
        "status": result.status.value,
        "reason": result.reason,
        "lease_sha256": lease.digest(),
        "proposal_sha256": result.proposal_sha256,
        "parent_generation": parent.generation,
        "current_generation": current.generation,
        "parent_optimizer_step": parent.retained_state.optimizer_step,
        "current_optimizer_step": current.retained_state.optimizer_step,
        "introduced_capability_ids": list(
            planned.receipt.selection.introduced_capability_ids),
        "introduced_semantic_ids": list(introduced),
        "actual_neural_updates": result.actual_neural_updates,
        "semantic_delta": None,
    }
    if result.status.value != "ADOPTED":
        return record
    if introduced:
        if len(introduced) != 1:
            raise ValueError("BAMF_C13_SEMANTIC_DELTA_SINGLE_ID_REQUIRED")
        receipt = record_append_only_semantic_delta(parent, current, introduced[0])
        record["semantic_delta"] = asdict(receipt)
    elif (current.generation != parent.generation + 1
          or current.retained_state.optimizer_step != parent.retained_state.optimizer_step):
        raise ValueError("BAMF_C13_CAPABILITY_ONLY_DELTA_CUSTODY_DRIFT")
    return record


def _main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Advance one C07 delta for the disposable C13 run")
    parser.add_argument("--run", required=True)
    parser.add_argument("--request")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    record = apply_next_atlas_delta(args.run, request_path=args.request)
    target = Path(args.out).expanduser().resolve()
    target.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"receipt": str(target), "status": record["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = ("PRODUCTION_RESERVE_GIB", "STAGE_SCHEMA", "apply_next_atlas_delta")
