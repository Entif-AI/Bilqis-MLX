"""Crash-safe persistence for neural-inert autonomous curriculum state."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from ..factory.autonomy import (
    AutonomyPlan,
    EvidenceLedger,
    EvidenceReceipt,
    ProjectionEvidenceSpec,
    SourceCompositionEdge,
    TeachingReceipt,
    compile_autonomy_plan,
    next_action,
)
from ..factory.model import FactoryRelease
from .state import _canonical, _durable_json, _fingerprint


STATE_SCHEMA = "bilqis.mlx.autonomous-curriculum-state/v1"
POINTER_SCHEMA = "bilqis.mlx.autonomous-curriculum-pointer/v1"


def _artifact_dirs(run_dir: Path) -> tuple[Path, Path]:
    root = Path(run_dir)
    autonomy = root / "autonomy"
    states = autonomy / "states"
    if autonomy.is_symlink() or states.is_symlink():
        raise ValueError("AUTONOMY_UNSAFE_ARTIFACT_DIRECTORY")
    return autonomy, states


def _plan_from_json(value: dict) -> AutonomyPlan:
    if not isinstance(value, dict):
        raise ValueError("AUTONOMY_STATE_PLAN_INVALID")
    try:
        return AutonomyPlan(
            factory_release_sha256=value["factory_release_sha256"],
            source_composition_audited=value["source_composition_audited"],
            source_composition_edges=tuple(
                SourceCompositionEdge(
                    consumer=item["consumer"], producer=item["producer"],
                    operand_slot=item["operand_slot"],
                    witness_ids=tuple(item["witness_ids"]),
                    source_cohort_sha256=item["source_cohort_sha256"],
                ) for item in value.get("source_composition_edges", ())),
            coverage_debt=tuple(value.get("coverage_debt", ())),
            blocked_capabilities=tuple(value.get("blocked_capabilities", ())),
            deferred_composition_candidates=tuple(
                value.get("deferred_composition_candidates", ())),
            projection_evidence=tuple(
                ProjectionEvidenceSpec(
                    capability_id=item["capability_id"],
                    projection_id=item["projection_id"],
                    minimum_specimens=item["minimum_specimens"],
                    proof_axes=tuple(item["proof_axes"]),
                )
                for item in value.get("projection_evidence", ())),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("AUTONOMY_STATE_PLAN_INVALID") from exc


def _ledger_from_json(value: dict) -> EvidenceLedger:
    if not isinstance(value, dict):
        raise ValueError("AUTONOMY_STATE_LEDGER_INVALID")
    try:
        receipts = tuple(EvidenceReceipt(**item) for item in value.get("receipts", ()))
        interventions = tuple(
            TeachingReceipt(**item) for item in value.get("interventions", ()))
        return EvidenceLedger(
            factory_release_sha256=value["factory_release_sha256"],
            autonomy_plan_sha256=value["autonomy_plan_sha256"],
            receipts=receipts,
            interventions=interventions,
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("AUTONOMY_STATE_LEDGER_INVALID") from exc


def persist_autonomy_state(
    run_dir: Path, release: FactoryRelease, *, ledger: EvidenceLedger,
    plan: AutonomyPlan | None = None,
) -> dict:
    """Write one immutable snapshot, then atomically advance a tiny pointer."""
    if not isinstance(release, FactoryRelease) or not isinstance(ledger, EvidenceLedger):
        raise TypeError("AUTONOMY_STATE_INVALID_INPUT")
    resolved_plan = compile_autonomy_plan(release) if plan is None else plan
    # next_action validates release/plan/ledger binding without mutating anything.
    next_action(release, ledger, plan=resolved_plan)
    autonomy, states = _artifact_dirs(Path(run_dir))
    payload = {
        "schema": STATE_SCHEMA,
        "factory_release_sha256": release.release_sha256,
        "autonomy_plan_sha256": resolved_plan.digest(),
        "plan": asdict(resolved_plan),
        "ledger": asdict(ledger),
    }
    # Normalize tuple/list container differences before hashing or readback.
    payload = json.loads(_canonical(payload))
    state_sha256 = _fingerprint(payload)
    sequence = len(ledger.receipts) + len(ledger.interventions)
    relative = Path("autonomy") / "states" / (
        f"{sequence:07d}-{state_sha256[:16]}.json")
    state_path = Path(run_dir) / relative
    if states.is_symlink() or state_path.is_symlink():
        raise ValueError("AUTONOMY_UNSAFE_ARTIFACT_DIRECTORY")
    if state_path.exists():
        if not state_path.is_file() or json.loads(state_path.read_text()) != payload:
            raise ValueError("AUTONOMY_STATE_IMMUTABLE_SNAPSHOT_DRIFT")
    else:
        _durable_json(state_path, payload)
    if json.loads(state_path.read_text()) != payload:
        raise ValueError("AUTONOMY_STATE_DURABLE_READBACK_DRIFT")

    pointer = {
        "schema": POINTER_SCHEMA,
        "factory_release_sha256": release.release_sha256,
        "autonomy_plan_sha256": resolved_plan.digest(),
        "state_file": relative.as_posix(),
        "state_sha256": state_sha256,
        "receipt_count": len(ledger.receipts),
        "intervention_count": len(ledger.interventions),
    }
    current = autonomy / "current.json"
    if current.is_symlink():
        raise ValueError("AUTONOMY_UNSAFE_ARTIFACT_DIRECTORY")
    _durable_json(current, pointer, replace_existing=True)
    # Fail closed unless exact durable readback reconstructs the same values.
    restored_plan, restored_ledger = read_autonomy_state(run_dir, release)
    if restored_plan != resolved_plan or restored_ledger != ledger:
        raise ValueError("AUTONOMY_STATE_DURABLE_READBACK_DRIFT")
    return pointer


def read_autonomy_state(
    run_dir: Path, release: FactoryRelease,
) -> tuple[AutonomyPlan, EvidenceLedger]:
    """Read and fully revalidate the latest durable autonomous state."""
    if not isinstance(release, FactoryRelease):
        raise TypeError("AUTONOMY_STATE_INVALID_RELEASE")
    autonomy, states = _artifact_dirs(Path(run_dir))
    current = autonomy / "current.json"
    if current.is_symlink() or not current.is_file():
        raise ValueError("AUTONOMY_STATE_POINTER_MISSING")
    try:
        pointer = json.loads(current.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError("AUTONOMY_STATE_POINTER_INVALID") from exc
    if (pointer.get("schema") != POINTER_SCHEMA or
            pointer.get("factory_release_sha256") != release.release_sha256):
        raise ValueError("AUTONOMY_STATE_POINTER_BINDING_DRIFT")
    relative = pointer.get("state_file")
    if not isinstance(relative, str):
        raise ValueError("AUTONOMY_STATE_POINTER_INVALID")
    parts = Path(relative).parts
    if len(parts) != 3 or parts[:2] != ("autonomy", "states"):
        raise ValueError("AUTONOMY_STATE_POINTER_UNSAFE_PATH")
    state_path = Path(run_dir) / relative
    if states.is_symlink() or state_path.is_symlink() or not state_path.is_file():
        raise ValueError("AUTONOMY_STATE_SNAPSHOT_MISSING")
    try:
        payload = json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError("AUTONOMY_STATE_SNAPSHOT_INVALID") from exc
    if _fingerprint(payload) != pointer.get("state_sha256"):
        raise ValueError("AUTONOMY_STATE_DIGEST_DRIFT")
    if (payload.get("schema") != STATE_SCHEMA or
            payload.get("factory_release_sha256") != release.release_sha256):
        raise ValueError("AUTONOMY_STATE_SNAPSHOT_BINDING_DRIFT")
    plan = _plan_from_json(payload.get("plan"))
    ledger = _ledger_from_json(payload.get("ledger"))
    if (payload.get("autonomy_plan_sha256") != plan.digest() or
            pointer.get("autonomy_plan_sha256") != plan.digest() or
            pointer.get("receipt_count") != len(ledger.receipts) or
            pointer.get("intervention_count", 0) != len(ledger.interventions)):
        raise ValueError("AUTONOMY_STATE_PLAN_OR_SEQUENCE_DRIFT")
    next_action(release, ledger, plan=plan)
    return plan, ledger
