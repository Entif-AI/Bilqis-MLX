"""Durable identity-only receipt for a successful disposable #1300 causal run."""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.active_generated_grade import read_active_generated_grade
from bilqis_mlx.runtime.active_grade_cadence import read_current_cadence
from bilqis_mlx.runtime.atlas_admission import (
    read_accepted_atlas_factory_release,
    read_accepted_atlas_lease_v2,
)
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.semantics.domains import contract_digest


ENV_PATH = "BILQIS_1300_EVIDENCE_PATH"
SCHEMA = "bilqis.bamf.1300-causal-evidence/v1"


def _publication_records(capture):
    return [
        {
            "binding": binding.to_record(),
            "published_generation": student.generation,
            "published_checkpoint_identity_sha256": candidate_identity_digest(
                student.retained_state),
            "factory_release_sha256": release_sha256,
        }
        for binding, student, release_sha256 in capture.publications
    ]


def _route_record(routes):
    from bilqis_mlx.semantics.domains import contract_digest as digest
    return {
        "complete_solver_routes": [
            {"capability_id": scope, "route": route, "operator_ids": list(operators)}
            for scope, route, operators in routes.solver_routes
        ],
        "resolved_training_goals": [
            {
                "capability_id": authority.capability_id,
                "authority_sha256": authority.digest,
                "release_sha256": authority.release_sha256,
                "generation_binding": authority.generation_binding,
                "goal_sha256": digest(goal),
            }
            for authority, goal in routes.training_goals
        ],
    }


def _write_receipt(path: Path, disposable_root: Path, body: dict) -> Path:
    path = Path(path).expanduser().resolve()
    disposable_root = Path(disposable_root).resolve()
    if path.is_relative_to(disposable_root):
        raise AssertionError("BILQIS_1300_EVIDENCE_PATH_MUST_OUTLIVE_DISPOSABLE_RUN")
    receipt = {**body, "receipt_sha256": contract_digest(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path


def export_causal_evidence(
        run_dir: Path, fixture, *, target_capture, successor_capture, routes,
        cold_receipts: dict, stop_receipt: dict, correction: dict) -> Path | None:
    raw_path = os.environ.get(ENV_PATH)
    if not raw_path:
        return None
    run_dir = Path(run_dir).resolve()
    path = Path(raw_path).expanduser().resolve()

    student = load_accepted_generation(run_dir)
    release = read_accepted_atlas_factory_release(run_dir)
    release.verify()
    active = read_active_generated_grade(run_dir)
    cadence = read_current_cadence(run_dir)
    pointer = json.loads((run_dir / "bamf-state.json").read_text())
    with fixture.host_registry():
        lease = read_accepted_atlas_lease_v2(
            run_dir,
            source_authority=AcceptedRuntimeHost(run_dir).source_authority(),
        )
    if lease is None:
        raise AssertionError("BILQIS_1300_ACCEPTED_V2_LEASE_REQUIRED")

    body = {
        "schema": SCHEMA,
        "detached_source_sha256": os.environ.get("BILQIS_DETACHED_SOURCE_SHA256"),
        "accepted": {
            "pointer": pointer,
            "run_id": student.run_id,
            "generation": student.generation,
            "optimizer_step": student.retained_state.optimizer_step,
            "checkpoint_identity_sha256": candidate_identity_digest(
                student.retained_state),
            "topology_sha256": student.topology.digest,
            "topology_layers": student.topology.layers,
            "semantic_abi": dict(student.semantic_abi),
            "baseline_evidence": student.baseline_evidence,
        },
        "factory_release": {
            "release_sha256": release.release_sha256,
            "manifest": release.manifest(),
        },
        "active_generated_grade": active.to_record(),
        "cadence": None if cadence is None else cadence.to_record(),
        "source_authority": {
            "approval": asdict(lease.source_approval),
            "lease_sha256": lease.digest(),
            "lease_id": lease.lease_id,
            "lease_schema": lease.schema_version,
        },
        "target_publications": _publication_records(target_capture),
        "successor_publications": _publication_records(successor_capture),
        "cold_resume": cold_receipts,
        "solver": _route_record(routes),
        "stop_receipt": stop_receipt,
        "correction": correction,
    }
    return _write_receipt(path, run_dir.parent, body)


__all__ = ("ENV_PATH", "export_causal_evidence")
