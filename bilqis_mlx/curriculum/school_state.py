"""Typed scheduler state and assessment contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from bilqis_mlx.factory.schedule import ScheduleProgram
from bilqis_mlx.learning.champions import Checkpoint


SHA256_HEX_LENGTH = 64


class SchoolContractError(str, Enum):
    INVALID_CAPABILITY_SCORE = "INVALID_CAPABILITY_SCORE"
    ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE = (
        "ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE")
    ASSESSMENT_RUBRIC_IDENTITY_MISSING = "ASSESSMENT_RUBRIC_IDENTITY_MISSING"
    ASSESSMENT_RUBRIC_SCOPE_DOES_NOT_COVER_ACTIVE_POOL = (
        "ASSESSMENT_RUBRIC_SCOPE_DOES_NOT_COVER_ACTIVE_POOL")
    ASSESSMENT_HAS_NO_REPRESENTED_GRADE = "ASSESSMENT_HAS_NO_REPRESENTED_GRADE"
    ASSESSMENT_NOT_GRADE_SEALED_RUBRIC = "ASSESSMENT_NOT_GRADE_SEALED_RUBRIC"
    ASSESSMENT_NOT_COURSE_SEALED_RUBRIC = "ASSESSMENT_NOT_COURSE_SEALED_RUBRIC"
    ASSESSMENT_NOT_COMPLETE_ACTIVE_POOL = "ASSESSMENT_NOT_COMPLETE_ACTIVE_POOL"
    ASSESSMENT_INVALID_SCORE_TYPE = "ASSESSMENT_INVALID_SCORE_TYPE"
    ASSESSMENT_TOTAL_DIFFERS_FROM_SEALED_ITEM_COUNT = (
        "ASSESSMENT_TOTAL_DIFFERS_FROM_SEALED_ITEM_COUNT")


def _program(value) -> ScheduleProgram:
    if isinstance(value, ScheduleProgram):
        return value
    from bilqis_mlx.compatibility.schedule_program import (
        schedule_program_from_legacy_course,
    )
    return schedule_program_from_legacy_course(value)


def _caps(program, grade_ids: tuple[str, ...]) -> tuple[str, ...]:
    program = _program(program)
    lookup = {grade.id: grade for grade in program.grades}
    return tuple(
        capability.id
        for grade_id in grade_ids
        for capability in lookup[grade_id].capabilities)


@dataclass(frozen=True)
class Score:
    correct: int
    total: int

    def __post_init__(self):
        if (type(self.correct) is not int or type(self.total) is not int or
                not 0 <= self.correct <= self.total or self.total < 1):
            raise ValueError(SchoolContractError.INVALID_CAPABILITY_SCORE.value)

    @property
    def accuracy(self):
        return Fraction(self.correct, self.total)

    @property
    def perfect(self):
        return self.correct == self.total


@dataclass(frozen=True)
class Assessment:
    """One independently evaluated, fixed-rubric, single-checkpoint snapshot."""
    checkpoint_sha256: str
    optimizer_step: int
    course_digest: str
    rubric_digest: str
    scores: dict[str, Score]
    evaluation_id: str

    def verify(self, checkpoint: Checkpoint, program,
               required_capabilities: tuple[str, ...], *,
               rubric_capabilities: tuple[str, ...] | None = None) -> None:
        program = _program(program)
        if (self.checkpoint_sha256 != checkpoint.sha256 or
                self.optimizer_step != checkpoint.optimizer_step or
                self.course_digest != program.digest()):
            raise ValueError(
                SchoolContractError.ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE.value)
        if (len(self.rubric_digest) != SHA256_HEX_LENGTH or
                any(c not in "0123456789abcdef" for c in self.rubric_digest) or
                not self.evaluation_id):
            raise ValueError(
                SchoolContractError.ASSESSMENT_RUBRIC_IDENTITY_MISSING.value)
        rubric_scope = (required_capabilities if rubric_capabilities is None
                        else rubric_capabilities)
        if not set(required_capabilities) <= set(rubric_scope):
            raise ValueError(
                SchoolContractError.
                ASSESSMENT_RUBRIC_SCOPE_DOES_NOT_COVER_ACTIVE_POOL.value)
        represented = [
            grade for grade in program.grades
            if any(cap.id in rubric_scope for cap in grade.capabilities)]
        if not represented:
            raise ValueError(
                SchoolContractError.ASSESSMENT_HAS_NO_REPRESENTED_GRADE.value)
        grade_seal = (program.exact_scope_rubric(rubric_scope) or
                      represented[-1].assessment_sha256)
        if grade_seal is not None and self.rubric_digest != grade_seal:
            raise ValueError(
                SchoolContractError.ASSESSMENT_NOT_GRADE_SEALED_RUBRIC.value)
        all_caps = _caps(program, tuple(g.id for g in program.grades))
        if (set(rubric_scope) == set(all_caps) and
                program.assessment_manifest_sha256 is not None and
                self.rubric_digest != program.assessment_manifest_sha256):
            raise ValueError(
                SchoolContractError.ASSESSMENT_NOT_COURSE_SEALED_RUBRIC.value)
        if set(self.scores) != set(required_capabilities):
            raise ValueError(
                SchoolContractError.ASSESSMENT_NOT_COMPLETE_ACTIVE_POOL.value)
        if not all(isinstance(score, Score) for score in self.scores.values()):
            raise ValueError(
                SchoolContractError.ASSESSMENT_INVALID_SCORE_TYPE.value)
        declared_counts = {
            cap: count
            for grade in program.grades
            for cap, count in grade.exam_item_counts}
        if any(cap in declared_counts and score.total != declared_counts[cap]
               for cap, score in self.scores.items()):
            raise ValueError(
                SchoolContractError.
                ASSESSMENT_TOTAL_DIFFERS_FROM_SEALED_ITEM_COUNT.value)


@dataclass(frozen=True)
class SchoolState:
    schema: str
    course_digest: str
    active_grades: tuple[str, ...]
    grade_index: int
    stage: str
    queue: tuple[str, ...]
    first_recovery: tuple[str, ...]
    current_student: Checkpoint
    champions: dict[str, Checkpoint]
    visits: int = 0
    school_cycles: int = 1
    latest_rubric_digest: str | None = None
    pending_failures: tuple[str, ...] = ()
    teacher_soup_digest: str | None = None
    revalidation_target_grade: str | None = None
    grade_exam_epoch: int = 0
    introduction_stage: int = 0
    introduction_frontiers: tuple[tuple[str, int], ...] = ()
    main_sweep_visited: tuple[str, ...] = ()
    carried_mastery_debt: tuple[str, ...] = ()
    promotion_sweep_scope: tuple[str, ...] = ()
    promotion_sweep_return_stage: str | None = None
    promotion_sweep_scores: tuple[tuple[str, int, int], ...] = ()
    frontier_priority_visits: int = 0
    nongating_b_visits: int = 0
    non_b_training_turns_since_b_run: int = 0

    @property
    def grade(self) -> str:
        return self.active_grades[self.grade_index]
