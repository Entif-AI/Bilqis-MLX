"""Accepted admission and learning re-entry helpers."""
from pathlib import Path

from bilqis_mlx.errors import BilqisError, SCHOOL


def accepted_admission_reentry(
        run_dir: Path, parent_graph: dict, reserve_gib: float, progress=None,
        *, emit_progress, invalid):
    from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
    from bilqis_mlx.runtime.atlas_flywheel import AdmissionFlywheelStatus
    from bilqis_mlx.runtime.atlas_flywheel_runtime import run_accepted_atlas_flywheel
    if not isinstance(parent_graph, dict):
        invalid("BAMF_OPERATOR_ADMISSION_PARENT_GRAPH_INVALID")
    before = read_accepted_atlas_factory_release(run_dir)
    emit_progress(progress, "re-entering accepted C07 admission flywheel")
    try:
        result = run_accepted_atlas_flywheel(run_dir, parent_graph, reserve_gib=reserve_gib)
    except BilqisError as error:
        reason = error.context.get("reason")
        lease_boundary = (
            error.spec is SCHOOL.BAMF_ATLAS_ADMISSION.ACCEPTED_LEASE_REQUIRED
            or (error.spec is SCHOOL.BAMF_ATLAS_ADMISSION.INVALID
                and isinstance(reason, str) and "LEASE" in reason))
        if not lease_boundary:
            raise
        return AdmissionFlywheelStatus.LEASE_REQUIRED.value, 0, "ADMISSION_LEASE_REQUIRED"
    after = read_accepted_atlas_factory_release(run_dir)
    if after.release_sha256 != result.final_state.epoch.current_release.release_sha256:
        invalid("BAMF_OPERATOR_ADMISSION_REFRESH_DRIFT")
    if after.release_sha256 != before.release_sha256:
        emit_progress(progress, "C07 adopted a successor; next visit must cold-refresh accepted custody")
    emit_progress(
        progress, f"admission flywheel outcome: {result.status.value} after {result.advances} advance(s)")
    stop_status = {
        AdmissionFlywheelStatus.FIXED_POINT: "FIXED_POINT",
        AdmissionFlywheelStatus.HELD: "ADMISSION_HOLD",
        AdmissionFlywheelStatus.IMPLEMENTATION_UNCOVERED: "IMPLEMENTATION_UNCOVERED",
        AdmissionFlywheelStatus.LEASE_REQUIRED: "ADMISSION_LEASE_REQUIRED",
    }.get(result.status)
    return result.status.value, result.advances, stop_status


def accepted_learning_reentry(
        run_dir: Path, parent_graph: dict, reserve_gib: float, progress=None,
        *, emit_progress, invalid):
    """Compose evidence refresh and C07 only for an explicit admission boundary."""
    from ..accepted_learning_evidence import refresh_accepted_learning_evidence
    evidence = refresh_accepted_learning_evidence(Path(run_dir), progress=progress)
    emit_progress(
        progress, "accepted learner evidence refresh: "
        f"{evidence.measured} measured, {evidence.passed} passed; next {evidence.final_action}")
    return accepted_admission_reentry(
        run_dir, parent_graph, reserve_gib, progress,
        emit_progress=emit_progress, invalid=invalid)


__all__ = ("accepted_admission_reentry", "accepted_learning_reentry")
