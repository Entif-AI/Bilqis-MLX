"""Grade-hold and certified-successor transitions for BAMF sessions."""
from pathlib import Path
import json

from bilqis_mlx.errors import BilqisError, SCHOOL

from .session_support import BamfPreparedVisit


def adopt_and_activate_certified_successor(
    run_dir: Path, context, *, certification_receipt_sha256: str,
    reserve_gib: float,
) -> bool:
    """Compose #1320 -> C07/B13 -> #1314 without acquiring any authority."""
    from bilqis_mlx.runtime.atlas_flywheel_runtime import run_accepted_atlas_flywheel
    result = run_accepted_atlas_flywheel(
        Path(run_dir), context.graph, reserve_gib=reserve_gib, max_advances=1)
    if result.advances != 1:
        return False
    from bilqis_mlx.runtime.active_generated_grade import activate_certified_generated_grade
    activate_certified_generated_grade(
        Path(run_dir), certification_receipt_sha256=certification_receipt_sha256)
    return True


def _rearm_current_grade(run_dir, selection):
    from bilqis_mlx.runtime.accepted_priority_visit_contracts import (
        require_priority_cadence_authorization,
        require_priority_lawful_frontier,
    )
    from bilqis_mlx.runtime.active_grade_cadence import rearm_active_grade_acquisition
    return rearm_active_grade_acquisition(
        Path(run_dir),
        require_priority_cadence_authorization(selection),
        require_priority_lawful_frontier(selection),
    )


def priority_hold_result(
        run_dir, selection, context, parent, atlas_path, reserve_gib, progress,
        *, emit_progress, adopt_successor=None):
    adopt_successor = (
        adopt_and_activate_certified_successor
        if adopt_successor is None else adopt_successor)
    status = "ACTION_REQUIRED" if selection.status == "ACTION_REQUIRED" else "HELD"
    metadata = getattr(selection, "metadata", None) or {}
    cadence = metadata.get("cadence")
    payload = {
        "holds": getattr(selection, "holds", ()),
        "exclusions": [item.to_record() for item in getattr(selection, "exclusions", ())],
        **({"cadence": cadence} if cadence is not None else {}),
    }
    emit_progress(progress, "priority holds: " + json.dumps(
        payload, sort_keys=True, ensure_ascii=True))
    boundary_disposition = cadence.get("disposition") if isinstance(cadence, dict) else None
    if boundary_disposition == "RECOVERY_EXHAUSTED":
        from bilqis_mlx.runtime.bamf_bundle.publication.preflight import (
            PREFLIGHT_EXHAUSTED, skip_only_exhaustion,
        )
        if skip_only_exhaustion(run_dir, parent, context.release, cadence):
            emit_progress(progress, "current target preflights exhausted without a training trial")
            return BamfPreparedVisit(PREFLIGHT_EXHAUSTED, parent, selection=selection)
        _rearm_current_grade(run_dir, selection)
        emit_progress(
            progress,
            "active grade recovery exhausted; rearmed ordinary MAIN acquisition",
        )
        return BamfPreparedVisit("ACQUISITION_REARMED", parent, selection=selection)
    certification = None
    if boundary_disposition == "GRADE_COMPLETE":
        from bilqis_mlx.runtime.grade_certification import run_grade_boundary_certification
        try:
            certification = run_grade_boundary_certification(
                Path(run_dir), selection, context, parent, str(atlas_path))
        except BilqisError as error:
            if not (
                error.spec is SCHOOL.BAMF_CURRICULUM.INVALID
                and error.context.get("reason")
                == "BAMF_GRADE_CERTIFICATION_POLICY_SELECTION_REQUIRED"
            ):
                raise
            emit_progress(
                progress,
                "grade certification requires signed C07 atlas-release "
                "progression-policy authority; retained learner state is unchanged",
            )
            return BamfPreparedVisit(
                "CERTIFICATION_POLICY_REQUIRED", parent, selection=selection)
    if certification is None:
        return BamfPreparedVisit(status, parent, selection=selection)
    if certification.status == "SUCCEEDED":
        from ..accepted_learning_evidence import refresh_accepted_learning_evidence
        evidence = refresh_accepted_learning_evidence(Path(run_dir), progress=progress)
        emit_progress(
            progress,
            "grade boundary learner evidence refresh: "
            f"{evidence.measured} measured, {evidence.passed} passed; "
            f"next {evidence.final_action}",
        )
        if not adopt_successor(
                Path(run_dir), context,
                certification_receipt_sha256=certification.receipt.receipt_sha256,
                reserve_gib=reserve_gib):
            emit_progress(
                progress, "grade certification succeeded; successor admission "
                "did not advance C07/B13")
            return BamfPreparedVisit("HELD", parent, selection=selection)
        emit_progress(
            progress, "grade certification succeeded; activated exact "
            "receipt-bound generated successor")
        return BamfPreparedVisit("GRADE_TRANSITIONED", parent, selection=selection)
    if certification.status == "SUPERSEDED":
        return BamfPreparedVisit("CERTIFICATION_SUPERSEDED", parent, selection=selection)
    if certification.status == "NOT_ELIGIBLE":
        _rearm_current_grade(run_dir, selection)
        emit_progress(
            progress,
            "grade certification entry not yet eligible; resumed ordinary MAIN acquisition",
        )
        return BamfPreparedVisit("ACQUISITION_REARMED", parent, selection=selection)
    if certification.status == "FAILED":
        return BamfPreparedVisit("CERTIFICATION_FAILED", parent, selection=selection)
    return BamfPreparedVisit(status, parent, selection=selection)


__all__ = ("adopt_and_activate_certified_successor", "priority_hold_result")
