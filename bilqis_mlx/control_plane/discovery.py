"""Read-only BAMF learner identity discovery for CP01."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.presentation.run_discovery import operator_lock_held
from bilqis_mlx.runtime.bamf_operator.locking import LOCKFILE

from .contracts import ControlPlaneState, LearnerIdentity


def _failure_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    if isinstance(code, str) and code:
        return code
    return error.__class__.__name__


def discover_learner(run_dir: Path) -> LearnerIdentity:
    """Resolve current accepted BAMF generation without creating or mutating a run."""
    run_dir = Path(run_dir).expanduser().resolve()
    pointer = run_dir / "bamf-state.json"
    if not pointer.exists() and not pointer.is_symlink():
        return LearnerIdentity(
            ControlPlaneState.LEARNER_UNAVAILABLE, str(run_dir))
    operator_active = operator_lock_held(run_dir / LOCKFILE)
    try:
        from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority
        student, manifest_sha256 = load_bamf_generation_authority(pointer)
    except FileNotFoundError as error:
        return LearnerIdentity(
            ControlPlaneState.STALE, str(run_dir),
            operator_active=operator_active,
            failure_code=_failure_code(error))
    except Exception as error:
        return LearnerIdentity(
            ControlPlaneState.DEGRADED, str(run_dir),
            operator_active=operator_active,
            failure_code=_failure_code(error))
    identity = student.run_identity
    return LearnerIdentity(
        ControlPlaneState.HEALTHY,
        str(run_dir),
        operator_active=operator_active,
        run_id=identity.run_id,
        run_identity_sha256=identity.digest,
        generation=student.generation,
        generation_manifest_sha256=manifest_sha256,
        optimizer_step=student.retained_state.optimizer_step,
        factory_release_sha256=identity.factory_release_sha256,
        topology_sha256=identity.initial_topology_digest,
    )
