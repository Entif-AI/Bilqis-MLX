"""One-time accepted-authority migration at the human BAMF resume boundary."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.errors import BilqisError, SCHOOL


def _missing_accepted_authority_checkpoint(error: BilqisError) -> bool:
    return (
        error.spec is SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID
        and error.context.get("reason") == "BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_REQUIRED"
    )


def _cadence_projection_rebuild_required(error: BilqisError) -> bool:
    return (
        error.spec is SCHOOL.BAMF_CURRICULUM.INVALID
        and error.context.get("reason")
        == "BAMF_ACTIVE_GRADE_CADENCE_PROJECTION_REBUILD_REQUIRED"
    )


def _ensure_resume_cadence_projection(args, run_dir: Path) -> None:
    from bilqis_mlx.runtime.active_grade_cadence_replay import (
        authenticated_cadence_attempts, rebuild_authenticated_cadence_attempts,
    )

    try:
        authenticated_cadence_attempts(run_dir)
        return
    except BilqisError as error:
        if not _cadence_projection_rebuild_required(error):
            raise
        if args.human_run is not True or args.dry_run:
            raise

    from bilqis_mlx.runtime.bamf_operator.locking import bamf_operator_lock
    with bamf_operator_lock(run_dir):
        rebuild_authenticated_cadence_attempts(run_dir)
    authenticated_cadence_attempts(run_dir)


def _load_resume_generation_authority(args, run_dir: Path, pointer: Path):
    """Load current authority, migrating only a human-authorized legacy run once."""
    from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority

    try:
        loaded = load_bamf_generation_authority(pointer)
    except BilqisError as error:
        if (args.human_run is not True or args.dry_run
                or not _missing_accepted_authority_checkpoint(error)):
            raise
        from bilqis_mlx.runtime.bamf_bundle import backfill_current_accepted_authority
        from bilqis_mlx.runtime.bamf_operator.locking import bamf_operator_lock
        with bamf_operator_lock(run_dir) as custody:
            backfill_current_accepted_authority(run_dir, operator_custody=custody)
        loaded = load_bamf_generation_authority(pointer)
    _ensure_resume_cadence_projection(args, run_dir)
    return loaded


__all__ = ("_load_resume_generation_authority",)
