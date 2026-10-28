"""Immutable school state, assessment contracts and boundary validation."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from enum import Enum
import hashlib

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.mature_debt import (
    HARD_LIMIT as MATURE_DEBT_HARD_LIMIT,
    REPAIR_THRESHOLD as MATURE_DEBT_REPAIR_THRESHOLD,
    RELEASE_THRESHOLD as MATURE_DEBT_RELEASE_THRESHOLD,
)
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.factory.schedule import ScheduleProgram
from .promotion import PromotionError, _verify_promotion_sweep_state


SHA256_HEX_LENGTH = hashlib.sha256().digest_size * 2

SCHOOL_STATE_SCHEMA = "bilqis.mlx.letter-grade/v1"
STAGES = frozenset(("MAIN", "ASSESS_MAIN", "RECOVERY_1", "ASSESS_RECOVERY_1",
                    "RECOVERY_2", "ASSESS_RECOVERY_2", "PROMOTION_SWEEP",
                    "ASSESS_PROMOTION_SWEEP", "AWAITING_TEACHER_SOUP",
                    "AWAITING_NEXT_GRADE", "AWAITING_NEXT_GRADE_WITH_DEBT",
                    "WHOLE_SCHOOL_MASTERED", "DEFERRED_STAGNATION"))

def _program(value) -> ScheduleProgram:
    if isinstance(value, ScheduleProgram):
        return value
    from bilqis_mlx.compatibility.schedule_program import (
        schedule_program_from_legacy_course,
    )
    return schedule_program_from_legacy_course(value)


class ScheduleTopology(str, Enum):
    UNCHANGED = "UNCHANGED"
    APPEND_GRADE = "APPEND_GRADE"
    SAME_GRADE_EXPANSION = "SAME_GRADE_EXPANSION"
    SAME_GRADE_REVISION = "SAME_GRADE_REVISION"
    UNSUPPORTED = "UNSUPPORTED"


def classify_schedule_topology(previous: ScheduleProgram,
                               successor: ScheduleProgram) -> ScheduleTopology:
    """Classify ordered grade/capability changes independently of semantic ABI."""
    if not isinstance(previous, ScheduleProgram) or not isinstance(successor, ScheduleProgram):
        raise TypeError(SCHOOL.SCHEDULE.PROGRAM_REQUIRED.legacy_codes[0])
    if previous == successor:
        return ScheduleTopology.UNCHANGED
    old_ids = tuple(grade.id for grade in previous.grades)
    new_ids = tuple(grade.id for grade in successor.grades)
    if len(new_ids) == len(old_ids) + 1 and new_ids[:-1] == old_ids:
        return ScheduleTopology.APPEND_GRADE
    if new_ids != old_ids:
        return ScheduleTopology.UNSUPPORTED
    old_rosters = tuple(tuple(cap.id for cap in grade.capabilities) for grade in previous.grades)
    new_rosters = tuple(tuple(cap.id for cap in grade.capabilities) for grade in successor.grades)
    if old_rosters != new_rosters and all(
            set(old) <= set(new) and tuple(name for name in new if name in old) == old
            for old, new in zip(old_rosters, new_rosters)):
        return ScheduleTopology.SAME_GRADE_EXPANSION
    return ScheduleTopology.SAME_GRADE_REVISION


@dataclass(frozen=True)
class Score:
    correct: int
    total: int

    def __post_init__(self):
        if (type(self.correct) is not int or type(self.total) is not int or
                not 0 <= self.correct <= self.total or self.total < 1):
            ErrorBus.raise_legacy(SCHOOL.STATE.INVALID_CAPABILITY_SCORE)

    @property
    def accuracy(self):
        return Fraction(self.correct, self.total)

    @property
    def perfect(self):
        return self.correct == self.total


@dataclass(frozen=True)
class DebtCadencePolicy:
    """Explicit grade roles and turn budget for bounded debt scheduling."""

    bounded_debt_grade_id: str
    progression_priority_grade_id: str
    non_debt_turns_per_run: int

    def __post_init__(self):
        if (not isinstance(self.bounded_debt_grade_id, str) or
                not self.bounded_debt_grade_id or
                not isinstance(self.progression_priority_grade_id, str) or
                not self.progression_priority_grade_id or
                self.bounded_debt_grade_id == self.progression_priority_grade_id or
                type(self.non_debt_turns_per_run) is not int or
                self.non_debt_turns_per_run < 1):
            ErrorBus.raise_legacy(SCHOOL.SCHEDULE.INVALID_DEBT_CADENCE_POLICY)

    @classmethod
    def from_legacy_adr094(cls):
        """Translate the historical B/C/four-turn contract at the boundary."""
        return cls(
            bounded_debt_grade_id="B",
            progression_priority_grade_id="C",
            non_debt_turns_per_run=4)


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
            ErrorBus.raise_legacy(SCHOOL.STATE.ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE)
        if (len(self.rubric_digest) != SHA256_HEX_LENGTH or
                any(c not in "0123456789abcdef" for c in self.rubric_digest) or
                not self.evaluation_id):
            ErrorBus.raise_legacy(SCHOOL.STATE.ASSESSMENT_RUBRIC_IDENTITY_MISSING)
        rubric_scope = (required_capabilities if rubric_capabilities is None
                        else rubric_capabilities)
        if not set(required_capabilities) <= set(rubric_scope):
            ErrorBus.raise_legacy(SCHOOL.STATE.ASSESSMENT_RUBRIC_SCOPE_DOES_NOT_COVER_ACTIVE_POOL)
        represented = [grade for grade in program.grades if
                       any(cap.id in rubric_scope
                           for cap in grade.capabilities)]
        if not represented:
            ErrorBus.raise_legacy(SCHOOL.STATE.ASSESSMENT_HAS_NO_REPRESENTED_GRADE)
        # Each grade seals its *cumulative* exam (including prior grades).
        # A newly introduced B rubric need not share A's exam digest.
        grade_seal = (program.exact_scope_rubric(rubric_scope) or
                      represented[-1].assessment_sha256)
        if grade_seal is not None and self.rubric_digest != grade_seal:
            ErrorBus.raise_legacy(SCHOOL.STATE.ASSESSMENT_NOT_GRADE_SEALED_RUBRIC)
        all_caps = _caps(program, tuple(g.id for g in program.grades))
        if (set(rubric_scope) == set(all_caps) and
                program.assessment_manifest_sha256 is not None and
                self.rubric_digest != program.assessment_manifest_sha256):
            ErrorBus.raise_legacy(SCHOOL.STATE.ASSESSMENT_NOT_COURSE_SEALED_RUBRIC)
        if set(self.scores) != set(required_capabilities):
            ErrorBus.raise_legacy(SCHOOL.STATE.ASSESSMENT_NOT_COMPLETE_ACTIVE_POOL)
        if not all(isinstance(s, Score) for s in self.scores.values()):
            ErrorBus.raise_legacy(SCHOOL.STATE.ASSESSMENT_INVALID_SCORE_TYPE)
        declared_counts = {cap: count for grade in program.grades
                           for cap, count in grade.exam_item_counts}
        if any(cap in declared_counts and score.total != declared_counts[cap]
               for cap, score in self.scores.items()):
            ErrorBus.raise_legacy(SCHOOL.STATE.ASSESSMENT_TOTAL_DIFFERS_FROM_SEALED_ITEM_COUNT)


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
    # A newly graduated grade B or later triggers an ordered A..grade replay.
    # Optional so saved letter-grade/v1 and human-run states remain readable.
    revalidation_target_grade: str | None = None
    # A pass ends one enrollment. A return to the grade owns a fresh test.
    grade_exam_epoch: int = 0
    introduction_stage: int = 0
    # A staged grade can temporarily yield the teaching spiral to another
    # grade before mastery.  Preserve each grade's introduced frontier so
    # re-entry resumes the same semantic stage instead of silently rewinding
    # to stage zero.  The scalar above remains the active-grade projection for
    # backward-compatible saved states and operator surfaces.
    introduction_frontiers: tuple[tuple[str, int], ...] = ()
    # Grades that already received their ordinary full MAIN pass in the
    # current cross-grade sweep. Global weakest-three recovery is due only
    # after every currently imperfect eligible grade has had that pass.
    main_sweep_visited: tuple[str, ...] = ()
    # Number of completed ordinary MAIN passes given to the newest active
    # grade in the current school sweep while it is below the school semantic
    # median. This is a bounded catch-up budget, not permanent grade priority.
    frontier_catchup_passes: int = 0
    # Explicit human-authorized progression may admit a later grade before all
    # earlier capabilities are mastered.  These identities remain cumulative
    # mastery debt until one intact checkpoint clears the whole active program.
    carried_mastery_debt: tuple[str, ...] = ()
    # A >90% grade mean opens a one-pass semantic stability sweep.
    promotion_sweep_scope: tuple[str, ...] = ()
    promotion_sweep_return_stage: str | None = None
    # Running current-grade score vector for ADR-093. The threshold-crossing
    # assessment freezes the baseline; each sweep visit replaces only the
    # semantic that was just rescored.
    promotion_sweep_scores: tuple[tuple[str, int, int], ...] = ()
    # A promotion attempt is owned by one exact learner state and semantic
    # scope. Fresh cohort flux alone cannot re-arm an unchanged student.
    promotion_sweep_attempt_student_sha256: str | None = None
    promotion_sweep_attempt_scope: tuple[str, ...] = ()
    # Imperfect capabilities from the last failed attempt on this scope.  A
    # fresh checkpoint cannot retry until this blocker set measurably improves.
    promotion_sweep_retry_scores: tuple[tuple[str, int, int], ...] = ()
    # Historical ADR-090 candidate-visit counters retain their saved receipt
    # fields. ADR-094 moved scheduling authority to whole grade-turns.
    frontier_priority_visits: int = 0
    nongating_b_visits: int = 0
    # Saved under its historical wire name; policy supplies the active roles
    # and number of completed non-debt turns.
    non_b_training_turns_since_b_run: int = 0
    # Absent on old receipts only until the neural-inert ADR-094 migration.
    # New schedules receive a policy only when one is explicitly supplied.
    debt_cadence_policy: DebtCadencePolicy | None = None
    # Net fixed-cohort damage carried by already-graduated capabilities.
    # Counts are local parent-to-candidate losses accumulated across retained
    # updates. Repair candidates pay these counts back; no historical
    # checkpoint becomes an admission baseline.
    mature_capability_debt: tuple[tuple[str, int], ...] = ()
    mature_grade_debt: tuple[tuple[str, int], ...] = ()

    @property
    def grade(self) -> str:
        return self.active_grades[self.grade_index]


def _caps(program, grade_ids: tuple[str, ...]) -> tuple[str, ...]:
    program = _program(program)
    lookup = {grade.id: grade for grade in program.grades}
    return tuple(c.id for grade in grade_ids for c in lookup[grade].capabilities)


def _score_pool(program, state: SchoolState) -> tuple[str, ...]:
    program = _program(program)
    represented = set(state.champions) | {state.grade}
    if state.carried_mastery_debt:
        # Debt admission opens new learning territory without letting an
        # unresolved earlier grade disappear from cumulative assessment.
        represented.update(state.active_grades)
    if state.latest_rubric_digest is not None:
        sealed = [index for index, grade in enumerate(program.grades)
                  if grade.id in state.active_grades and
                  grade.assessment_sha256 == state.latest_rubric_digest]
        if sealed:
            cutoff = max(sealed)
            represented.update(
                grade.id for grade in program.grades[:cutoff + 1]
                if grade.id in state.active_grades)
    seen = tuple(g.id for g in program.grades if g.id in represented)
    frontiers = dict(state.introduction_frontiers)
    introduced = set()
    for grade in program.grades:
        if grade.id not in represented:
            continue
        if not grade.teaching_stages or grade.id in state.champions:
            introduced.update(capability.id for capability in grade.capabilities)
            continue
        stage_index = (
            state.introduction_stage if grade.id == state.grade
            else frontiers.get(grade.id, 0)
        )
        introduced.update(
            capability
            for stage in grade.teaching_stages[:stage_index + 1]
            for capability in stage
        )
    return tuple(cap for cap in _caps(program, seen) if cap in introduced)


def _school_state_boundary_issue(program, state: SchoolState):
    """Return the first boundary violation without discarding its evidence."""
    program = _program(program)
    runtime_digest = program.digest()
    if state.schema != SCHOOL_STATE_SCHEMA:
        return SCHOOL.STATE.SCHEMA_MISMATCH, {
            "actual_schema": state.schema,
            "expected_schema": SCHOOL_STATE_SCHEMA,
        }
    if state.course_digest != runtime_digest:
        return SCHOOL.STATE.COURSE_DIGEST_MISMATCH, {
            "saved_course_digest": state.course_digest,
            "runtime_course_digest": runtime_digest,
        }
    if state.stage not in STAGES:
        return SCHOOL.STATE.STAGE_INVALID, {
            "actual_stage": state.stage,
        }
    if not state.active_grades:
        return SCHOOL.STATE.ACTIVE_GRADES_EMPTY, {}
    if not 0 <= state.grade_index < len(state.active_grades):
        return SCHOOL.STATE.GRADE_INDEX_OUT_OF_RANGE, {
            "grade_index": state.grade_index,
            "active_grade_count": len(state.active_grades),
        }
    return None


def verify_state(program, state: SchoolState):
    program = _program(program)
    boundary_issue = _school_state_boundary_issue(program, state)
    if boundary_issue is not None:
        spec, context = boundary_issue
        ErrorBus.raise_(spec, **context)
    known = {g.id for g in program.grades}
    if (not set(state.active_grades) <= known or
            tuple(g.id for g in program.grades if g.id in state.active_grades) != state.active_grades or
            not set(state.champions) <= known):
        ErrorBus.raise_legacy(SCHOOL.STATE.INVALID_GRADE_PROGRAM_OR_CHAMPIONS)
    if (state.debt_cadence_policy is not None and
            (not isinstance(state.debt_cadence_policy, DebtCadencePolicy) or
             not {state.debt_cadence_policy.bounded_debt_grade_id,
                  state.debt_cadence_policy.progression_priority_grade_id} <= known)):
        ErrorBus.raise_legacy(SCHOOL.SCHEDULE.INVALID_DEBT_CADENCE_POLICY)
    if any(cap not in _score_pool(program, state) for cap in state.queue + state.first_recovery):
        ErrorBus.raise_legacy(SCHOOL.STATE.QUEUE_CAPABILITY_OUTSIDE_ACTIVE_AND_PASSED_GRADES)
    if (state.visits < 0 or state.school_cycles < 1 or
            type(state.grade_exam_epoch) is not int or state.grade_exam_epoch < 0 or
            type(state.introduction_stage) is not int or state.introduction_stage < 0 or
            type(state.frontier_priority_visits) is not int or
            state.frontier_priority_visits < 0 or
            type(state.nongating_b_visits) is not int or
            state.nongating_b_visits < 0 or
            type(state.non_b_training_turns_since_b_run) is not int or
            state.non_b_training_turns_since_b_run < 0 or
            type(state.frontier_catchup_passes) is not int or
            state.frontier_catchup_passes < 0):
        ErrorBus.raise_legacy(SCHOOL.STATE.INVALID_SCHOOL_COUNTER)
    frontiers = state.introduction_frontiers
    grade_lookup = {grade.id: grade for grade in program.grades}
    if (len({grade for grade, _ in frontiers}) != len(frontiers) or
            any(grade not in state.active_grades or type(stage) is not int or stage < 0
                for grade, stage in frontiers) or
            any(stage >= max(1, len(grade_lookup[grade].teaching_stages))
                for grade, stage in frontiers)):
        ErrorBus.raise_legacy(SCHOOL.STATE.INVALID_INTRODUCTION_FRONTIER_HISTORY)
    if (len(set(state.main_sweep_visited)) != len(state.main_sweep_visited) or
            not set(state.main_sweep_visited) <= set(state.active_grades)):
        ErrorBus.raise_legacy(SCHOOL.STATE.INVALID_MAIN_SWEEP_HISTORY)
    all_active_caps = set(_caps(program, state.active_grades))
    if (len(set(state.carried_mastery_debt)) != len(state.carried_mastery_debt) or
            not set(state.carried_mastery_debt) <= all_active_caps):
        ErrorBus.raise_legacy(SCHOOL.STATE.INVALID_CARRIED_MASTERY_DEBT)
    if state.carried_mastery_debt and state.stage in (
            "AWAITING_NEXT_GRADE", "WHOLE_SCHOOL_MASTERED"):
        ErrorBus.raise_legacy(SCHOOL.STATE.CARRIED_MASTERY_DEBT_AT_COMPLETION_BOUNDARY)
    mature_debt = state.mature_capability_debt
    if (len({capability for capability, _ in mature_debt}) != len(mature_debt) or
            any(capability not in all_active_caps or type(amount) is not int or amount < 1
                for capability, amount in mature_debt)):
        ErrorBus.raise_legacy(SCHOOL.STATE.INVALID_MATURE_CAPABILITY_DEBT)
    grade_debt = state.mature_grade_debt
    if (len({grade for grade, _ in grade_debt}) != len(grade_debt) or
            any(grade not in state.active_grades or type(amount) is not int or amount < 1
                for grade, amount in grade_debt)):
        ErrorBus.raise_legacy(SCHOOL.STATE.INVALID_MATURE_CAPABILITY_DEBT)
    current = next(g for g in program.grades if g.id == state.grade)
    if state.introduction_stage >= max(1, len(current.teaching_stages)):
        ErrorBus.raise_legacy(SCHOOL.STATE.INVALID_INTRODUCTION_STAGE)
    _verify_promotion_sweep_state(program, state)
    program = _program(program)
    if state.revalidation_target_grade is not None:
        if (state.revalidation_target_grade not in state.active_grades[1:] or
                state.grade_index > state.active_grades.index(state.revalidation_target_grade) or
                state.stage not in ("MAIN", "ASSESS_MAIN", "RECOVERY_1",
                                    "ASSESS_RECOVERY_1", "RECOVERY_2", "ASSESS_RECOVERY_2",
                                    "PROMOTION_SWEEP", "ASSESS_PROMOTION_SWEEP",
                                    "DEFERRED_STAGNATION") or
                not set(state.active_grades[:state.active_grades.index(
                    state.revalidation_target_grade) + 1]) <= set(state.champions)):
            ErrorBus.raise_legacy(SCHOOL.STATE.INVALID_GRADE_REVALIDATION_STATE)
    if state.stage == "AWAITING_NEXT_GRADE" and (
            program.program_complete or state.grade != program.grades[-1].id or
            state.queue or state.pending_failures or
            state.grade not in state.champions):
        ErrorBus.raise_legacy(SCHOOL.STATE.INVALID_PARTIAL_SCHOOL_COMPLETION)
    if state.stage == "AWAITING_NEXT_GRADE_WITH_DEBT" and (
            program.program_complete or state.grade != state.active_grades[-1] or
            state.queue or not state.carried_mastery_debt):
        raise ValueError(PromotionError.INVALID_DEBT_BEARING_GRADE_BOUNDARY.value)
    if state.stage == "WHOLE_SCHOOL_MASTERED" and not program.program_complete:
        ErrorBus.raise_legacy(SCHOOL.STATE.WHOLE_SCHOOL_CANNOT_COMPLETE_PARTIAL_COURSE)



def assessment_capabilities(program, state: SchoolState) -> tuple[str, ...]:
    """Expose only already introduced concepts plus earlier mastered grades."""
    program = _program(program)
    verify_state(program, state)
    return _score_pool(program, state)


def next_capability(state: SchoolState) -> str | None:
    return (state.queue[0]
            if state.stage in ("MAIN", "RECOVERY_1", "RECOVERY_2",
                               "PROMOTION_SWEEP") and state.queue
            else None)



def weakest_three(scores: dict[str, Score], pool: tuple[str, ...]) -> tuple[str, ...]:
    """Select up to three failures from the complete cumulative introduced pool."""
    if len(set(pool)) != len(pool) or not set(pool) <= set(scores):
        ErrorBus.raise_legacy(SCHOOL.STATE.WEAKEST_THREE_INCOMPLETE_POOL)
    ranking = sorted((c for c in pool if not scores[c].perfect),
                     key=lambda c: (scores[c].accuracy, c))
    return tuple(ranking[:3])
