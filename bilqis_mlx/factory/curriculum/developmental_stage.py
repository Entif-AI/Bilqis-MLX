"""Pure C14 stage intent over admitted Factory and atlas-frontier authority."""
from __future__ import annotations

from dataclasses import dataclass

from bilqis_mlx.factory.atlas_frontier_closure import ClosureStatus, FrontierClosure
from bilqis_mlx.factory.atlas_frontier_contracts import CurriculumSnapshot
from bilqis_mlx.factory.atlas_frontier_progress_contracts import FrontierStatus
from bilqis_mlx.factory.atlas_frontier_selection import ranked_frontier_target
from bilqis_mlx.factory.atlas_frontier_selection_validation import validate_closure_structure
from .developmental_program import BamfDevelopmentalProgram, _fail
from bilqis_mlx.factory.executable_release import ExecutableFactoryRelease


@dataclass(frozen=True, order=True)
class StageRemediation:
    semantic_id: str
    family_id: str
    code: str
    owner: str
    dependency_id: str = ""


@dataclass(frozen=True)
class DevelopmentalSourceCoverage:
    snapshot: CurriculumSnapshot
    closure: FrontierClosure

    def verify(self) -> None:
        if (type(self.snapshot) is not CurriculumSnapshot
                or type(self.closure) is not FrontierClosure):
            _fail("DEVELOPMENTAL_STAGE_COVERAGE_INVALID")
        self.snapshot.verify()
        self.closure.verify()
        if self.closure.snapshot_sha256 != self.snapshot.snapshot_sha256:
            _fail("DEVELOPMENTAL_STAGE_COVERAGE_DRIFT")
        validate_closure_structure(self.snapshot, self.closure)


@dataclass(frozen=True)
class DevelopmentalLearnerState:
    admitted_release: ExecutableFactoryRelease

    def verify(self) -> None:
        if not isinstance(self.admitted_release, ExecutableFactoryRelease):
            _fail("DEVELOPMENTAL_STAGE_RELEASE_INVALID")
        try:
            self.admitted_release.verify()
        except (TypeError, ValueError):
            _fail("DEVELOPMENTAL_STAGE_RELEASE_INVALID")


@dataclass(frozen=True)
class StageIntent:
    program_sha256: str
    admitted_release_sha256: str
    status: FrontierStatus
    selected_semantic_id: str | None
    selected_family_ids: tuple[str, ...]
    active_grade_ids: tuple[str, ...]
    active_capability_ids: tuple[str, ...]
    numeric_maximum: int | None
    source_eligible_concept_ids: tuple[str, ...]
    covered_semantic_ids: tuple[str, ...]
    retained_mastery_debt: tuple[str, ...]
    teacher_epoch: int
    remediation: tuple[StageRemediation, ...]
    nonblocking_levels: tuple[str, ...] = ("L3", "L4")
    authorizes_learning: bool = False

    def __post_init__(self) -> None:
        tuple_fields = (
            self.selected_family_ids, self.active_grade_ids,
            self.active_capability_ids, self.source_eligible_concept_ids,
            self.covered_semantic_ids, self.retained_mastery_debt,
            self.remediation, self.nonblocking_levels,
        )
        if (not isinstance(self.status, FrontierStatus)
                or any(type(value) is not tuple for value in tuple_fields)
                or self.nonblocking_levels != ("L3", "L4")
                or type(self.authorizes_learning) is not bool
                or self.authorizes_learning
                or type(self.teacher_epoch) is not int or self.teacher_epoch < 0
                or (self.numeric_maximum is not None
                    and (type(self.numeric_maximum) is not int
                         or self.numeric_maximum < 0))
                or (self.selected_semantic_id is not None
                    and (type(self.selected_semantic_id) is not str
                         or not self.selected_semantic_id))):
            _fail("DEVELOPMENTAL_STAGE_INTENT_INVALID")


def _numeric_maximum_from_capabilities(capabilities) -> int | None:
    maxima = set()
    for capability in capabilities:
        parameters = dict(capability.provider_parameters)
        values = parameters.get("numbers")
        if values is None:
            continue
        try:
            numbers = tuple(int(value) for value in values)
        except (TypeError, ValueError):
            _fail("DEVELOPMENTAL_STAGE_NUMERIC_SCOPE_INVALID")
        if (not numbers or numbers != tuple(range(max(numbers) + 1))):
            _fail("DEVELOPMENTAL_STAGE_NUMERIC_SCOPE_INVALID")
        maxima.add(max(numbers))
    if len(maxima) > 1:
        _fail("DEVELOPMENTAL_STAGE_NUMERIC_SCOPE_DRIFT")
    return None if not maxima else next(iter(maxima))


def _remediation(coverage: DevelopmentalSourceCoverage) -> tuple[StageRemediation, ...]:
    rows = [StageRemediation(
        item.semantic_id, item.family_id, reason.code,
        reason.owner, reason.dependency_id,
    ) for item in coverage.closure.candidates for reason in item.reasons]
    rows.extend(StageRemediation(
        "", "", hold.reason_code, hold.owner, hold.source_id,
    ) for hold in coverage.closure.source_holds)
    return tuple(sorted(rows))


def _ready_group_exists(closure: FrontierClosure) -> bool:
    grouped: dict[str, list[ClosureStatus]] = {}
    for item in closure.candidates:
        grouped.setdefault(item.semantic_id, []).append(item.status)
    return any(states and all(
        status is ClosureStatus.READY for status in states)
        for states in grouped.values())


def _blocked_status(coverage: DevelopmentalSourceCoverage) -> FrontierStatus:
    statuses = {item.status for item in coverage.closure.candidates}
    if ClosureStatus.IMPLEMENTATION_UNCOVERED in statuses:
        return FrontierStatus.IMPLEMENTATION_UNCOVERED
    if ClosureStatus.WAITING_FOR_EVIDENCE in statuses:
        return FrontierStatus.WAITING_FOR_EVIDENCE
    if ClosureStatus.SOURCE_HELD in statuses or coverage.closure.source_holds:
        return FrontierStatus.SOURCE_HELD
    if not coverage.snapshot.source_eligible_concept_ids:
        return FrontierStatus.COMPLETE_ATLAS_COVERAGE
    return FrontierStatus.FIXED_POINT


def resolve_training_stage(
    program: BamfDevelopmentalProgram,
    source_coverage: DevelopmentalSourceCoverage,
    learner_state: DevelopmentalLearnerState,
) -> StageIntent:
    """Project the next lawful intent; never stage, admit, or authorize learning."""
    if type(program) is not BamfDevelopmentalProgram:
        _fail("DEVELOPMENTAL_STAGE_PROGRAM_INVALID")
    source_coverage.verify()
    learner_state.verify()
    snapshot = source_coverage.snapshot
    release = learner_state.admitted_release
    if snapshot.admitted_factory_release_sha256 != release.release_sha256:
        _fail("DEVELOPMENTAL_STAGE_RELEASE_DRIFT")

    selected_semantic_id = None
    selected_family_ids: tuple[str, ...] = ()
    status = _blocked_status(source_coverage)
    if _ready_group_exists(source_coverage.closure):
        selected_semantic_id, rows = ranked_frontier_target(
            snapshot, source_coverage.closure)
        selected_family_ids = tuple(sorted(item.family_id for item in rows))
        status = FrontierStatus.PROPOSAL

    active_grade_ids = tuple(grade.grade_id for grade in release.execution_plan.grades)
    active_capability_ids = tuple(
        capability.capability_id for capability in release.execution_plan.capabilities)
    covered = tuple(sorted({row.semantic_id for row in snapshot.coverage_rows}))
    return StageIntent(
        program.digest(), release.release_sha256, status,
        selected_semantic_id, selected_family_ids,
        active_grade_ids, active_capability_ids,
        _numeric_maximum_from_capabilities(release.execution_plan.capabilities),
        snapshot.source_eligible_concept_ids, covered,
        snapshot.retained_mastery_debt, snapshot.teacher_epoch,
        _remediation(source_coverage),
    )
