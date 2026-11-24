"""Planning-input proof and process-live verification for priority qualification."""
from dataclasses import dataclass, field
from bilqis_mlx.errors import ErrorBus, SCHOOL

_PLANNING_OWNER = object()
_PLANNING_VERIFICATION_ISSUER = object()

def _invalid(reason):
    ErrorBus.Raise(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


@dataclass(frozen=True)
class PriorityPlanningInput:
    progress: object
    closure: object
    selection: object | None
    selected_projection: object | None
    _owner: object | None = field(default=None, init=False, repr=False, compare=False)
    _verification: object | None = field(
        default=None, init=False, repr=False, compare=False)


@dataclass(frozen=True, init=False, eq=False)
class _PlanningVerification:
    planning: PriorityPlanningInput = field(repr=False, compare=False)
    release: object = field(repr=False, compare=False)
    fingerprint: tuple = field(repr=False, compare=False)
    _issuance: object = field(repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid('BAMF_PRIORITY_PLANNING_VERIFICATION_CALLER_CONSTRUCTION_FORBIDDEN')


def _planning(planning, release):
    from bilqis_mlx.factory.atlas_frontier_selection import (
        FrontierDeltaSelection, validate_frontier_selection,
    )
    from bilqis_mlx.factory.atlas_frontier_selection_validation import (
        TargetDeltaProjection, validate_closure_structure,
    )
    from bilqis_mlx.factory.atlas_frontier_progress_contracts import FrontierProgress
    from bilqis_mlx.factory.atlas_frontier_closure import FrontierClosure

    if type(planning) is not PriorityPlanningInput:
        _invalid('BAMF_PRIORITY_PLANNING_INVALID')
    progress, closure = planning.progress, planning.closure
    if (type(progress) is not FrontierProgress or type(closure) is not FrontierClosure
            or (planning.selection is not None and type(planning.selection) is not FrontierDeltaSelection)
            or (planning.selected_projection is not None and type(planning.selected_projection) is not TargetDeltaProjection)):
        _invalid('BAMF_PRIORITY_PLANNING_INVALID')
    progress.verify()
    closure.verify()
    snapshot = progress.input_snapshot
    if (closure.snapshot_sha256 != progress.input_snapshot_sha256
            or snapshot.admitted_factory_release_sha256 != release.release_sha256):
        _invalid('BAMF_PRIORITY_PLANNING_DRIFT')
    validate_closure_structure(snapshot, closure)
    selection, projection = planning.selection, planning.selected_projection
    if (selection is None) != (projection is None):
        _invalid('BAMF_PRIORITY_PLANNING_SELECTION_REQUIRED')
    if selection is not None:
        validate_frontier_selection(snapshot, closure, selection, release, projection)
        if progress.proposal_selection_sha256 != selection.selection_sha256:
            _invalid('BAMF_PRIORITY_PLANNING_SELECTION_DRIFT')
    elif progress.proposal_selection_sha256 is not None:
        _invalid('BAMF_PRIORITY_PLANNING_SELECTION_REQUIRED')


def _issue_internal_priority_planning(
        progress, closure, selection, selected_projection, *, release=None):
    """Mark one owner-derived A09 projection as eligible for process-live proof reuse."""
    planning = PriorityPlanningInput(
        progress, closure, selection, selected_projection)
    object.__setattr__(planning, '_owner', _PLANNING_OWNER)
    if release is not None:
        witness = (
            id(planning),
            id(progress),
            id(progress.input_snapshot),
            progress.input_snapshot_sha256,
            id(closure),
            closure.closure_sha256,
            release.release_sha256,
            None if selection is None else (
                id(selection), selection.selection_sha256),
            None if selected_projection is None else (
                id(selected_projection), selected_projection.projection_sha256),
        )
        object.__setattr__(planning, '_verification', witness)
    return planning


def _planning_fingerprint(planning, release):
    """Cheap tamper-evident identity for fields consumed after full A09 verification."""
    progress = planning.progress
    closure = planning.closure
    selection = planning.selection
    projection = planning.selected_projection
    release_digest = release.expected_digest()
    return (
        id(planning),
        id(progress),
        progress.progress_sha256,
        id(progress.input_snapshot),
        progress.input_snapshot_sha256,
        progress.proposal_selection_sha256,
        progress.status,
        id(closure),
        closure.closure_sha256,
        closure.snapshot_sha256,
        None if selection is None else (
            id(selection),
            selection.selection_sha256,
            selection.snapshot_sha256,
            selection.closure_sha256,
            selection.admitted_release_sha256,
            selection.selected_semantic_id,
            selection.downstream_unlocks,
        ),
        None if projection is None else (
            id(projection),
            projection.projection_sha256,
            projection.semantic_id,
            projection.current_release_sha256,
            projection.current_semantic_catalog_sha256,
            projection.projected_semantic_catalog_sha256,
        ),
        id(release),
        release.release_sha256,
        release_digest,
        id(release.execution_plan),
        release.execution_plan.digest(),
        id(release.curriculum),
        release.curriculum.digest(),
        id(release.source_bindings),
        release.source_bindings.digest(),
    )


def _mint_planning_verification(planning, release):
    release.verify()
    fingerprint = _planning_fingerprint(planning, release)
    witness = object.__new__(_PlanningVerification)
    for name, value in (
        ('planning', planning),
        ('release', release),
        ('fingerprint', fingerprint),
        ('_issuance', _PLANNING_VERIFICATION_ISSUER),
    ):
        object.__setattr__(witness, name, value)
    object.__setattr__(planning, '_verification', witness)


def _has_current_planning_verification(planning, release):
    if (type(planning) is not PriorityPlanningInput
            or getattr(planning, '_owner', None) is not _PLANNING_OWNER):
        return False
    witness = getattr(planning, '_verification', None)
    if (type(witness) is not _PlanningVerification
            or getattr(witness, '_issuance', None)
               is not _PLANNING_VERIFICATION_ISSUER
            or witness.planning is not planning
            or witness.release is not release):
        return False
    try:
        fingerprint = _planning_fingerprint(planning, release)
    except Exception:
        return False
    return fingerprint == witness.fingerprint
