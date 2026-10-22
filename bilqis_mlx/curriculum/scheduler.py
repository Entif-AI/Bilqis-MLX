"""Deterministic, neural-inert school-grade scheduler and promotion contract.

No optimizer, teacher/model or exam generator is invoked here. This state
machine accepts only explicit same-checkpoint scores from a separate evaluator.
It prevents an old mixed-step score board from certifying new grade mastery.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from bilqis_mlx.learning.champions import Checkpoint, repoint_earlier, vote_counts, soup_weights
from bilqis_mlx.factory.schedule import ScheduleProgram
from bilqis_mlx.runtime.disk import atomic_text


PROMOTION_MEAN_FLOOR = Fraction(9, 10)
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


@dataclass(frozen=True)
class Score:
    correct: int
    total: int

    def __post_init__(self):
        if (type(self.correct) is not int or type(self.total) is not int or
                not 0 <= self.correct <= self.total or self.total < 1):
            raise ValueError("INVALID_CAPABILITY_SCORE")

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
            raise ValueError("ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE")
        if (len(self.rubric_digest) != 64 or
                any(c not in "0123456789abcdef" for c in self.rubric_digest) or
                not self.evaluation_id):
            raise ValueError("ASSESSMENT_RUBRIC_IDENTITY_MISSING")
        rubric_scope = (required_capabilities if rubric_capabilities is None
                        else rubric_capabilities)
        if not set(required_capabilities) <= set(rubric_scope):
            raise ValueError("ASSESSMENT_RUBRIC_SCOPE_DOES_NOT_COVER_ACTIVE_POOL")
        represented = [grade for grade in program.grades if
                       any(cap.id in rubric_scope
                           for cap in grade.capabilities)]
        if not represented:
            raise ValueError("ASSESSMENT_HAS_NO_REPRESENTED_GRADE")
        # Each grade seals its *cumulative* exam (including prior grades).
        # A newly introduced B rubric need not share A's exam digest.
        grade_seal = (program.exact_scope_rubric(rubric_scope) or
                      represented[-1].assessment_sha256)
        if grade_seal is not None and self.rubric_digest != grade_seal:
            raise ValueError("ASSESSMENT_NOT_GRADE_SEALED_RUBRIC")
        all_caps = _caps(program, tuple(g.id for g in program.grades))
        if (set(rubric_scope) == set(all_caps) and
                program.assessment_manifest_sha256 is not None and
                self.rubric_digest != program.assessment_manifest_sha256):
            raise ValueError("ASSESSMENT_NOT_COURSE_SEALED_RUBRIC")
        if set(self.scores) != set(required_capabilities):
            raise ValueError("ASSESSMENT_NOT_COMPLETE_ACTIVE_POOL")
        if not all(isinstance(s, Score) for s in self.scores.values()):
            raise ValueError("ASSESSMENT_INVALID_SCORE_TYPE")
        declared_counts = {cap: count for grade in program.grades
                           for cap, count in grade.exam_item_counts}
        if any(cap in declared_counts and score.total != declared_counts[cap]
               for cap, score in self.scores.items()):
            raise ValueError("ASSESSMENT_TOTAL_DIFFERS_FROM_SEALED_ITEM_COUNT")


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
    # Explicit human-authorized progression may admit a later grade before all
    # earlier capabilities are mastered.  These identities remain cumulative
    # mastery debt until one intact checkpoint clears the whole active program.
    carried_mastery_debt: tuple[str, ...] = ()
    # A >90% grade mean opens a one-pass semantic stability sweep.
    promotion_sweep_scope: tuple[str, ...] = ()
    promotion_sweep_return_stage: str | None = None

    @property
    def grade(self) -> str:
        return self.active_grades[self.grade_index]


def _caps(program, grade_ids: tuple[str, ...]) -> tuple[str, ...]:
    program = _program(program)
    lookup = {grade.id: grade for grade in program.grades}
    return tuple(c.id for grade in grade_ids for c in lookup[grade].capabilities)


def _introduced_grade_capabilities(program, state: SchoolState) -> tuple[str, ...]:
    program = _program(program)
    grade = next(g for g in program.grades if g.id == state.grade)
    if not grade.teaching_stages:
        return tuple(capability.id for capability in grade.capabilities)
    return tuple(
        capability
        for stage in grade.teaching_stages[:state.introduction_stage + 1]
        for capability in stage
    )


def _mean_accuracy(scores: dict[str, Score],
                   capabilities: tuple[str, ...]) -> Fraction:
    if not capabilities or not set(capabilities) <= set(scores):
        raise ValueError("GRADE_MEAN_REQUIRES_COMPLETE_SEMANTIC_SET")
    return sum((scores[capability].accuracy for capability in capabilities),
               Fraction(0, 1)) / len(capabilities)


def _promotion_sweep_fields_cleared(state: SchoolState, **changes) -> SchoolState:
    return replace(
        state,
        promotion_sweep_scope=(),
        promotion_sweep_return_stage=None,
        **changes,
    )


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
    current = {g.id: g for g in program.grades}[state.grade]
    introduced = (set(c for stage in current.teaching_stages[:state.introduction_stage+1]
                      for c in stage) if current.teaching_stages else
                  {c.id for c in current.capabilities})
    return tuple(cap for cap in _caps(program, seen)
                 if cap in introduced or cap not in {c.id for c in current.capabilities})


def assessment_capabilities(program, state: SchoolState) -> tuple[str, ...]:
    """Expose only already introduced concepts plus earlier mastered grades."""
    program = _program(program)
    verify_state(program, state)
    return _score_pool(program, state)


def _main_queue(program, state: SchoolState) -> tuple[str, ...]:
    program = _program(program)
    return tuple(c for c in _score_pool(program, state)
                 if c in _caps(program, (state.grade,)))


def _frontiers_with(state: SchoolState, grade: str, stage: int) -> tuple[tuple[str, int], ...]:
    frontiers = dict(state.introduction_frontiers)
    frontiers[grade] = stage
    return tuple((grade_id, frontiers[grade_id])
                 for grade_id in state.active_grades if grade_id in frontiers)


def _at_introduction_stage(state: SchoolState, introduction_stage: int,
                           **changes) -> SchoolState:
    return replace(
        state,
        introduction_stage=introduction_stage,
        introduction_frontiers=_frontiers_with(
            state, state.grade, introduction_stage),
        **changes,
    )


def _enter_grade(program, state: SchoolState, grade_index: int, **changes) -> SchoolState:
    program = _program(program)
    grade_id = state.active_grades[grade_index]
    grade = next(g for g in program.grades if g.id == grade_id)
    frontiers = dict(state.introduction_frontiers)
    if 0 <= state.grade_index < len(state.active_grades):
        frontiers[state.grade] = state.introduction_stage
    index = (len(grade.teaching_stages)-1
             if grade_id in state.champions and grade.teaching_stages
             else frontiers.get(grade_id, 0))
    frontiers[grade_id] = index
    entered = replace(
        state, grade_index=grade_index, introduction_stage=index,
        introduction_frontiers=tuple(
            (active_grade, frontiers[active_grade])
            for active_grade in state.active_grades if active_grade in frontiers),
        **changes)
    queue = _main_queue(program, entered)
    if grade.teaching_stages and grade_id not in entered.champions:
        queue = grade.teaching_stages[index]
    return replace(entered, queue=queue)


def start_new(program, initial_student: Checkpoint) -> SchoolState:
    program = _program(program)
    state = SchoolState(schema="bilqis.mlx.letter-grade/v1",
                       course_digest=program.digest(),
                       active_grades=tuple(g.id for g in program.grades),
                       grade_index=0, stage="MAIN",
                       queue=_caps(program, (program.grades[0].id,)),
                       first_recovery=(), current_student=initial_student,
                       champions={})
    return replace(state, queue=_main_queue(program, state))


def _verify_promotion_sweep_state(program, state: SchoolState) -> None:
    sweep_active = state.stage in ("PROMOTION_SWEEP", "ASSESS_PROMOTION_SWEEP")
    scope = state.promotion_sweep_scope
    return_stage = state.promotion_sweep_return_stage
    if not sweep_active:
        if scope or return_stage is not None:
            raise ValueError("PROMOTION_SWEEP_STATE_OUTSIDE_SWEEP")
        return

    introduced = _introduced_grade_capabilities(program, state)
    valid_return_stage = return_stage in (
        "ASSESS_MAIN", "ASSESS_RECOVERY_1", "ASSESS_RECOVERY_2")
    valid_queue = (
        len(state.queue) <= len(scope) and
        state.queue == scope[len(scope)-len(state.queue):])
    valid_phase_queue = (
        (state.stage == "PROMOTION_SWEEP" and bool(state.queue)) or
        (state.stage == "ASSESS_PROMOTION_SWEEP" and
         len(state.queue) < len(scope)))
    if (not scope or scope != introduced or
            not valid_return_stage or not valid_queue or not valid_phase_queue):
        raise ValueError("INVALID_PROMOTION_SWEEP_STATE")


def verify_state(program, state: SchoolState):
    program = _program(program)
    expected_digest = program.digest()
    if state.schema != "bilqis.mlx.letter-grade/v1":
        raise ValueError(
            "INVALID_OR_DRIFTED_SCHOOL_STATE: schema "
            f"saved={state.schema!r} expected='bilqis.mlx.letter-grade/v1'")
    if state.course_digest != expected_digest:
        raise ValueError(
            "INVALID_OR_DRIFTED_SCHOOL_STATE: course_digest "
            f"saved={state.course_digest} expected={expected_digest}")
    if state.stage not in STAGES:
        raise ValueError(
            "INVALID_OR_DRIFTED_SCHOOL_STATE: stage "
            f"saved={state.stage!r} expected_one_of={sorted(STAGES)!r}")
    if not state.active_grades:
        raise ValueError(
            "INVALID_OR_DRIFTED_SCHOOL_STATE: active_grades saved=() expected=nonempty")
    if not 0 <= state.grade_index < len(state.active_grades):
        raise ValueError(
            "INVALID_OR_DRIFTED_SCHOOL_STATE: grade_index "
            f"saved={state.grade_index} valid_range=0..{len(state.active_grades)-1}")
    known = {g.id for g in program.grades}
    if (not set(state.active_grades) <= known or
            tuple(g.id for g in program.grades if g.id in state.active_grades) != state.active_grades or
            not set(state.champions) <= known):
        raise ValueError("INVALID_GRADE_PROGRAM_OR_CHAMPIONS")
    if any(cap not in _score_pool(program, state) for cap in state.queue + state.first_recovery):
        raise ValueError("QUEUE_CAPABILITY_OUTSIDE_ACTIVE_AND_PASSED_GRADES")
    if (state.visits < 0 or state.school_cycles < 1 or
            type(state.grade_exam_epoch) is not int or state.grade_exam_epoch < 0 or
            type(state.introduction_stage) is not int or state.introduction_stage < 0):
        raise ValueError("INVALID_SCHOOL_COUNTER")
    frontiers = state.introduction_frontiers
    grade_lookup = {grade.id: grade for grade in program.grades}
    if (len({grade for grade, _ in frontiers}) != len(frontiers) or
            any(grade not in state.active_grades or type(stage) is not int or stage < 0
                for grade, stage in frontiers) or
            any(stage >= max(1, len(grade_lookup[grade].teaching_stages))
                for grade, stage in frontiers)):
        raise ValueError("INVALID_INTRODUCTION_FRONTIER_HISTORY")
    if (len(set(state.main_sweep_visited)) != len(state.main_sweep_visited) or
            not set(state.main_sweep_visited) <= set(state.active_grades)):
        raise ValueError("INVALID_MAIN_SWEEP_HISTORY")
    all_active_caps = set(_caps(program, state.active_grades))
    if (len(set(state.carried_mastery_debt)) != len(state.carried_mastery_debt) or
            not set(state.carried_mastery_debt) <= all_active_caps):
        raise ValueError("INVALID_CARRIED_MASTERY_DEBT")
    if state.carried_mastery_debt and state.stage in (
            "AWAITING_NEXT_GRADE", "WHOLE_SCHOOL_MASTERED"):
        raise ValueError("CARRIED_MASTERY_DEBT_AT_COMPLETION_BOUNDARY")
    current = next(g for g in program.grades if g.id == state.grade)
    if state.introduction_stage >= max(1, len(current.teaching_stages)):
        raise ValueError("INVALID_INTRODUCTION_STAGE")
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
            raise ValueError("INVALID_GRADE_REVALIDATION_STATE")
    if state.stage == "AWAITING_NEXT_GRADE" and (
            program.program_complete or state.grade != program.grades[-1].id or
            state.queue or state.pending_failures or
            state.grade not in state.champions):
        raise ValueError("INVALID_PARTIAL_SCHOOL_COMPLETION")
    if state.stage == "AWAITING_NEXT_GRADE_WITH_DEBT" and (
            program.program_complete or state.grade != state.active_grades[-1] or
            state.queue or not state.carried_mastery_debt):
        raise ValueError("INVALID_DEBT_BEARING_GRADE_BOUNDARY")
    if state.stage == "WHOLE_SCHOOL_MASTERED" and not program.program_complete:
        raise ValueError("WHOLE_SCHOOL_CANNOT_COMPLETE_PARTIAL_COURSE")


def next_capability(state: SchoolState) -> str | None:
    return (state.queue[0]
            if state.stage in ("MAIN", "RECOVERY_1", "RECOVERY_2",
                               "PROMOTION_SWEEP") and state.queue
            else None)


def visit(program, state: SchoolState, capability: str,
          student_after_visit: Checkpoint) -> SchoolState:
    """Record a completed human-run visit. Caller supplies the admitted full student.

    A rejected candidate leaves the complete student checkpoint unchanged.
    """
    program = _program(program)
    verify_state(program, state)
    if next_capability(state) != capability:
        raise ValueError("VISIT_NOT_NEXT_SCHEDULED_CAPABILITY")
    rest = state.queue[1:]
    if state.stage == "PROMOTION_SWEEP":
        after = "ASSESS_PROMOTION_SWEEP"
    else:
        after = (state.stage if rest else
                 "ASSESS_" + ("MAIN" if state.stage == "MAIN" else state.stage))
    return replace(state, queue=rest, stage=after, visits=state.visits+1,
                   current_student=student_after_visit)


def require_assessment_after_flash(program, state: SchoolState) -> SchoolState:
    """End flash mode owing a real assessment before normal scheduling resumes."""
    program = _program(program)
    verify_state(program, state)
    if state.stage in ("ASSESS_MAIN", "ASSESS_RECOVERY_1",
                       "ASSESS_RECOVERY_2", "ASSESS_PROMOTION_SWEEP"):
        return state
    if state.stage not in ("MAIN", "RECOVERY_1", "RECOVERY_2",
                           "PROMOTION_SWEEP"):
        raise ValueError("FLASH_MODE_CANNOT_REQUIRE_ASSESSMENT_FROM_STAGE")
    if state.stage == "PROMOTION_SWEEP":
        return replace(state, stage="ASSESS_PROMOTION_SWEEP")
    return replace(state, stage="ASSESS_" + state.stage, queue=())


def weakest_three(scores: dict[str, Score], pool: tuple[str, ...]) -> tuple[str, ...]:
    """Select up to three failures from the complete cumulative introduced pool."""
    if len(set(pool)) != len(pool) or not set(pool) <= set(scores):
        raise ValueError("WEAKEST_THREE_INCOMPLETE_POOL")
    ranking = sorted((c for c in pool if not scores[c].perfect),
                     key=lambda c: (scores[c].accuracy, c))
    return tuple(ranking[:3])


def _perfect_in_grade(program, grade: str, scores: dict[str, Score]) -> bool:
    return all(c in scores and scores[c].perfect for c in _caps(program, (grade,)))


def _next_imperfect_grade_index(program, state: SchoolState,
                                scores: dict[str, Score], *,
                                allowed_capabilities: tuple[str, ...] | None = None,
                                excluded_grades: tuple[str, ...] = ()) -> int | None:
    """Find the next imperfect eligible grade in canonical wrapped order.

    Start immediately after the current grade, wrap once through canonical
    admitted order, skip grades already perfect on the latest cumulative
    assessment, and optionally skip grades already visited in the current
    ordinary MAIN sweep.
    """
    allowed = set(scores) if allowed_capabilities is None else set(allowed_capabilities)
    if not allowed <= set(scores):
        raise ValueError("SPIRAL_ALLOWED_CAPABILITY_OUTSIDE_ASSESSMENT")
    excluded = set(excluded_grades)
    if not excluded <= set(state.active_grades):
        raise ValueError("SPIRAL_EXCLUDED_GRADE_OUTSIDE_ACTIVE_PROGRAM")
    count = len(state.active_grades)
    for offset in range(1, count + 1):
        index = (state.grade_index + offset) % count
        if state.active_grades[index] in excluded:
            continue
        grade_caps = _caps(program, (state.active_grades[index],))
        eligible = tuple(cap for cap in grade_caps if cap in allowed)
        if not eligible:
            continue
        # An ordinary pass is due when any currently eligible capability in the
        # grade is imperfect. Missing/withheld capabilities are handled by the
        # caller's explicit containment authority, never synthesized as perfect.
        if any(not scores[cap].perfect for cap in eligible):
            return index
    return None


def _instructional_pool(program, state: SchoolState, scores: dict[str, Score],
                        pool: tuple[str, ...]) -> tuple[str, ...]:
    """Prioritize the admitted frontier without concealing prior-grade debt."""
    if not state.carried_mastery_debt:
        return pool
    frontier = state.active_grades[-1]
    grade = next(g for g in _program(program).grades if g.id == frontier)
    current = set(_caps(program, (frontier,)))
    if grade.teaching_stages and frontier not in state.champions:
        frontier_stage = dict(state.introduction_frontiers).get(
            frontier, state.introduction_stage if state.grade == frontier else 0)
        current &= set(cap for stage in grade.teaching_stages[:frontier_stage + 1]
                       for cap in stage)
    due = tuple(cap for cap in pool if cap in current and
                cap in scores and not scores[cap].perfect)
    return due or pool


def _resume_ordinary_spiral(program, state: SchoolState,
                            snapshot: Assessment, *,
                            allowed_capabilities: tuple[str, ...] | None = None,
                            reset_sweep: bool = True) -> SchoolState | None:
    due = _instructional_pool(
        program, state, snapshot.scores,
        allowed_capabilities or _score_pool(program, state))
    frontier = state.active_grades[-1]
    if (state.carried_mastery_debt and due and
            all(cap in set(_caps(program, (frontier,))) for cap in due)):
        entered = _enter_grade(program, state, len(state.active_grades) - 1,
                               stage="MAIN", first_recovery=(),
                               main_sweep_visited=(),
                               latest_rubric_digest=snapshot.rubric_digest)
        return replace(entered, queue=due)
    excluded: tuple[str, ...] = ()
    while len(excluded) < len(state.active_grades):
        index = _next_imperfect_grade_index(
            program, state, snapshot.scores,
            allowed_capabilities=allowed_capabilities,
            excluded_grades=excluded)
        if index is None:
            return None
        entered = _enter_grade(
            program, state, index, stage="MAIN", first_recovery=(),
            main_sweep_visited=() if reset_sweep else state.main_sweep_visited,
            latest_rubric_digest=snapshot.rubric_digest)
        if allowed_capabilities is None:
            return entered
        allowed = set(allowed_capabilities)
        queue = tuple(cap for cap in entered.queue if cap in allowed)
        if queue:
            return replace(entered, queue=queue)
        excluded = (*excluded, entered.grade)
    return None


def _continue_main_sweep(program, state: SchoolState,
                         snapshot: Assessment, *,
                         allowed_capabilities: tuple[str, ...] | None = None) -> SchoolState | None:
    """Continue ordinary grade passes before scheduling global recovery.

    A grade enters `main_sweep_visited` only after its complete currently
    introduced MAIN queue has been assessed. Recovery therefore happens at
    most twice *between* full multi-grade sweeps, not twice after every grade.
    """
    program = _program(program)
    grade = next(g for g in program.grades if g.id == state.grade)
    if (grade.teaching_stages and
            state.introduction_stage < len(grade.teaching_stages) - 1):
        # An incompletely introduced staged grade is not yet an ordinary
        # cross-grade sweep member. Its current stage must pass/remediate first.
        return None
    due = _instructional_pool(program, state, snapshot.scores,
                              allowed_capabilities or _score_pool(program, state))
    frontier = state.active_grades[-1]
    if (state.carried_mastery_debt and due and
            all(cap in set(_caps(program, (frontier,))) for cap in due)):
        entered = _enter_grade(program, state, len(state.active_grades) - 1,
                               stage="MAIN", first_recovery=(),
                               main_sweep_visited=(),
                               latest_rubric_digest=snapshot.rubric_digest)
        return replace(entered, queue=due)
    visited = state.main_sweep_visited
    if state.grade not in visited:
        visited = visited + (state.grade,)
    excluded = visited
    while len(excluded) < len(state.active_grades):
        index = _next_imperfect_grade_index(
            program, state, snapshot.scores,
            allowed_capabilities=allowed_capabilities,
            excluded_grades=excluded)
        if index is None:
            return None
        entered = _enter_grade(
            program, state, index, stage="MAIN", first_recovery=(),
            main_sweep_visited=visited,
            latest_rubric_digest=snapshot.rubric_digest)
        if allowed_capabilities is None:
            return entered
        allowed = set(allowed_capabilities)
        queue = tuple(cap for cap in entered.queue if cap in allowed)
        if queue:
            return replace(entered, queue=queue)
        excluded = (*excluded, entered.grade)
    return None


def _finish_grade_series(program, state: SchoolState, assessment: Assessment,
                         pointers: dict[str, Checkpoint]) -> SchoolState:
    """Advance to the next grade or stop at a verified program boundary."""
    program = _program(program)
    next_index = state.grade_index + 1
    if next_index < len(state.active_grades):
        next_grade = state.active_grades[next_index]
        return _enter_grade(program, state, next_index,
                       stage="MAIN", first_recovery=(), champions=pointers,
                       main_sweep_visited=(),
                       revalidation_target_grade=None,
                       # The newly admitted grade owns the next cumulative seal.
                       latest_rubric_digest=None)
    if not program.program_complete:
        # Passing the last *published* grade cannot silently certify the
        # still-unpublished rest of New Ithkuil. Retain the intact champion
        # and wait for an explicitly versioned next-grade admission.
        return replace(state, queue=(), first_recovery=(), champions=pointers,
                       stage="AWAITING_NEXT_GRADE", pending_failures=(),
                       main_sweep_visited=(),
                       revalidation_target_grade=None,
                       latest_rubric_digest=assessment.rubric_digest)
    # Whole-school result is *one* model's all-grade result. A collection of
    # per-grade champions does not substitute for a perfect all-grade student.
    all_caps = _caps(program, tuple(g.id for g in program.grades))
    if set(assessment.scores) != set(all_caps):
        raise ValueError("FINAL_WHOLE_SCHOOL_SNAPSHOT_INCOMPLETE")
    failed = tuple(g.id for g in program.grades
                   if not _perfect_in_grade(program, g.id, assessment.scores))
    return replace(state, queue=(), first_recovery=(), champions=pointers,
                   stage="AWAITING_TEACHER_SOUP" if failed else "WHOLE_SCHOOL_MASTERED",
                   main_sweep_visited=(),
                   revalidation_target_grade=None,
                   latest_rubric_digest=assessment.rubric_digest,
                   pending_failures=failed)


def _promote(program, state: SchoolState, assessment: Assessment) -> SchoolState:
    program = _program(program)
    candidate = state.current_student
    previous = tuple(g.id for g in program.grades if g.id in state.champions)
    full_at_candidate = tuple(g for g in previous if _perfect_in_grade(program, g, assessment.scores))
    pointers = repoint_earlier(state.champions, candidate,
                               previously_passed=previous,
                               fully_mastered_at_this_candidate=full_at_candidate)
    pointers[state.grade] = candidate

    if state.carried_mastery_debt:
        all_caps = _caps(program, state.active_grades)
        if not set(all_caps) <= set(assessment.scores):
            raise ValueError("DEBT_PROMOTION_REQUIRES_COMPLETE_ACTIVE_ASSESSMENT")
        debt = tuple(capability for capability in all_caps
                     if not assessment.scores[capability].perfect)
        if not debt:
            # One intact checkpoint has finally cleared every admitted grade.
            # Repoint every grade to that same complete student, then use the
            # ordinary partial/full program boundary machinery.
            complete_pointers = {
                grade: candidate for grade in state.active_grades
            }
            last = len(state.active_grades) - 1
            boundary = _enter_grade(
                program, replace(state, carried_mastery_debt=()), last,
                stage="MAIN", first_recovery=(), champions=complete_pointers,
                main_sweep_visited=(), revalidation_target_grade=None,
                latest_rubric_digest=assessment.rubric_digest)
            return _finish_grade_series(
                program, boundary, assessment, complete_pointers)
        next_index = _next_imperfect_grade_index(
            program, state, assessment.scores)
        if next_index is None:
            raise ValueError("DEBT_SPIRAL_HAS_NO_IMPERFECT_GRADE")
        return _enter_grade(
            program, replace(state, carried_mastery_debt=debt), next_index,
            stage="MAIN", first_recovery=(), champions=pointers,
            main_sweep_visited=(), revalidation_target_grade=None,
            latest_rubric_digest=assessment.rubric_digest)

    target = state.revalidation_target_grade
    if target is not None:
        target_index = state.active_grades.index(target)
        if state.grade_index < target_index:
            # A/B/C are revisited in order, with their normal full-grade,
            # weakest-three and same-checkpoint assessment schedule.
            next_index = state.grade_index + 1
            return _enter_grade(program, state, next_index,
                           stage="MAIN", first_recovery=(), champions=pointers,
                           main_sweep_visited=())
        failed = tuple(g for g in state.active_grades[:target_index + 1]
                       if not _perfect_in_grade(program, g, assessment.scores))
        if failed:
            if program.program_complete and target == program.grades[-1].id:
                # Preserve the original final-program teacher-soup recovery:
                # only failed grades are revisited in that next school cycle.
                return replace(state, queue=(), first_recovery=(), champions=pointers,
                               stage="AWAITING_TEACHER_SOUP", pending_failures=failed,
                               main_sweep_visited=(),
                               revalidation_target_grade=None,
                               latest_rubric_digest=assessment.rubric_digest)
            # At a partial-program boundary, do not start C if the final B
            # checkpoint lost A. Repeat the ordered prefix until it sticks.
            return _enter_grade(program, state, 0, stage="MAIN",
                           first_recovery=(), champions=pointers,
                           main_sweep_visited=())
        return _finish_grade_series(program, state, assessment, pointers)

    if state.grade_index > 0 and state.grade not in state.champions:
        # Newly mastered B triggers A->B; C triggers A->B->C, etc.
        # Even a perfect initial cumulative B examination is followed by a
        # fresh ordered revalidation pass before the next grade is entered.
        return _enter_grade(program, state, 0, stage="MAIN",
                       first_recovery=(), champions=pointers,
                       main_sweep_visited=(),
                       revalidation_target_grade=state.grade,
                       latest_rubric_digest=assessment.rubric_digest)
    return _finish_grade_series(program, state, assessment, pointers)


def _verify_assessment_boundary(program, state: SchoolState,
                                snapshot: Assessment,
                                pool: tuple[str, ...], *,
                                rubric_pool: tuple[str, ...] | None = None) -> None:
    program = _program(program)
    verify_state(program, state)
    if state.stage not in ("ASSESS_MAIN", "ASSESS_RECOVERY_1",
                           "ASSESS_RECOVERY_2", "ASSESS_PROMOTION_SWEEP"):
        raise ValueError("ASSESSMENT_NOT_SCHEDULED_AT_DURABLE_BOUNDARY")
    snapshot.verify(
        state.current_student, program, pool,
        rubric_capabilities=rubric_pool,
    )
    if (not program.assessment_projections and
            state.latest_rubric_digest is not None and
            state.latest_rubric_digest != snapshot.rubric_digest):
        raise ValueError("ASSESSMENT_RUBRIC_CHANGED_MID_COURSE")


def _promotion_sweep_due(program, state: SchoolState,
                         snapshot: Assessment) -> bool:
    if state.revalidation_target_grade is not None or state.grade in state.champions:
        return False
    scope = _introduced_grade_capabilities(program, state)
    return _mean_accuracy(snapshot.scores, scope) > PROMOTION_MEAN_FLOOR


def _start_promotion_sweep(program, state: SchoolState,
                           snapshot: Assessment) -> SchoolState:
    scope = _introduced_grade_capabilities(program, state)
    return replace(
        state, stage="PROMOTION_SWEEP", queue=scope,
        promotion_sweep_scope=scope,
        promotion_sweep_return_stage=state.stage,
        latest_rubric_digest=snapshot.rubric_digest,
    )


def _promotion_debt(program, state: SchoolState,
                    snapshot: Assessment) -> tuple[str, ...]:
    unresolved = set(state.carried_mastery_debt)
    unresolved.update(
        capability for capability in state.promotion_sweep_scope
        if not snapshot.scores[capability].perfect)
    return tuple(
        capability for capability in _caps(program, state.active_grades)
        if capability in unresolved
    )


def _boundary_mastery_debt(program, state: SchoolState,
                           snapshot: Assessment,
                           fallback: tuple[str, ...]) -> tuple[str, ...]:
    all_caps = _caps(program, state.active_grades)
    if not set(all_caps) <= set(snapshot.scores):
        return fallback
    return tuple(capability for capability in all_caps
                 if not snapshot.scores[capability].perfect)


def _refresh_mastery_debt(program, state: SchoolState,
                          snapshot: Assessment) -> SchoolState:
    if not state.carried_mastery_debt:
        return state
    all_caps = _caps(program, state.active_grades)
    if not set(all_caps) <= set(snapshot.scores):
        return state
    debt = tuple(capability for capability in all_caps
                 if not snapshot.scores[capability].perfect)
    # Keep the nonempty marker until _promote observes one complete
    # all-perfect checkpoint and closes the debt-admission epoch.
    return replace(state, carried_mastery_debt=debt) if debt else state


def _assess_ordinary(program, state: SchoolState,
                     snapshot: Assessment) -> SchoolState:
    pool = _score_pool(program, state)
    grade = next(g for g in program.grades if g.id == state.grade)
    if grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1:
        own = set(_main_queue(program, state))
        if all(snapshot.scores[c].perfect for c in own):
            next_stage = state.introduction_stage + 1
            return _at_introduction_stage(
                state, next_stage, stage="MAIN",
                queue=grade.teaching_stages[next_stage], first_recovery=(),
                latest_rubric_digest=snapshot.rubric_digest)
    if _perfect_in_grade(program, state.grade, snapshot.scores):
        return replace(_promote(program, state, snapshot),
                       grade_exam_epoch=state.grade_exam_epoch + 1)
    if state.stage == "ASSESS_MAIN":
        continued = _continue_main_sweep(program, state, snapshot)
        if continued is not None:
            return continued
        trio = weakest_three(
            snapshot.scores,
            _instructional_pool(program, state, snapshot.scores, pool))
        return replace(state, stage="RECOVERY_1", queue=trio,
                       first_recovery=trio,
                       main_sweep_visited=(
                           state.main_sweep_visited + (state.grade,)
                           if state.grade not in state.main_sweep_visited
                           else state.main_sweep_visited),
                       latest_rubric_digest=snapshot.rubric_digest)
    if state.stage == "ASSESS_RECOVERY_1":
        trio = weakest_three(
            snapshot.scores,
            _instructional_pool(program, state, snapshot.scores, pool))
        return replace(state, stage="RECOVERY_2", queue=trio,
                       latest_rubric_digest=snapshot.rubric_digest)
    resumed = _resume_ordinary_spiral(
        program, state, snapshot, reset_sweep=True)
    if resumed is None:
        raise ValueError("SPIRAL_RECOVERY_ENDED_WITHOUT_IMPERFECT_GRADE")
    return resumed


def _advance_after_promotion_sweep(program, state: SchoolState,
                                   snapshot: Assessment) -> SchoolState:
    debt = _promotion_debt(program, state, snapshot)
    return_stage = state.promotion_sweep_return_stage
    cleared = _promotion_sweep_fields_cleared(
        state, carried_mastery_debt=debt,
        latest_rubric_digest=snapshot.rubric_digest)
    grade = next(g for g in program.grades if g.id == state.grade)
    if grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1:
        next_stage = state.introduction_stage + 1
        return _at_introduction_stage(
            cleared, next_stage, stage="MAIN",
            queue=grade.teaching_stages[next_stage], first_recovery=())
    if _perfect_in_grade(program, state.grade, snapshot.scores):
        return replace(_promote(program, cleared, snapshot),
                       grade_exam_epoch=state.grade_exam_epoch + 1)
    boundary_debt = _boundary_mastery_debt(
        program, state, snapshot, debt)
    cleared = replace(cleared, carried_mastery_debt=boundary_debt)
    next_index = state.grade_index + 1
    if next_index < len(state.active_grades):
        return _enter_grade(
            program, cleared, next_index, stage="MAIN", first_recovery=(),
            main_sweep_visited=(), latest_rubric_digest=None)
    if not program.program_complete:
        return replace(
            cleared, stage="AWAITING_NEXT_GRADE_WITH_DEBT", queue=(),
            first_recovery=(), main_sweep_visited=())
    ordinary = replace(cleared, stage=return_stage, queue=())
    return _assess_ordinary(program, ordinary, snapshot)


def _assess_promotion_sweep(program, state: SchoolState,
                            snapshot: Assessment) -> SchoolState:
    scope = state.promotion_sweep_scope
    completed = len(scope) - len(state.queue)
    if completed < 1:
        raise ValueError("PROMOTION_SWEEP_ASSESSMENT_WITHOUT_VISIT")
    if _mean_accuracy(snapshot.scores, scope) < PROMOTION_MEAN_FLOOR:
        return_stage = state.promotion_sweep_return_stage
        ordinary = _promotion_sweep_fields_cleared(
            state, stage=return_stage, queue=(),
            latest_rubric_digest=snapshot.rubric_digest)
        ordinary = _refresh_mastery_debt(program, ordinary, snapshot)
        return _assess_ordinary(program, ordinary, snapshot)
    if state.queue:
        return replace(
            state, stage="PROMOTION_SWEEP",
            latest_rubric_digest=snapshot.rubric_digest)
    return _advance_after_promotion_sweep(program, state, snapshot)


def assess(program, state: SchoolState, snapshot: Assessment) -> SchoolState:
    program = _program(program)
    pool = _score_pool(program, state)
    _verify_assessment_boundary(program, state, snapshot, pool)
    if state.stage == "ASSESS_PROMOTION_SWEEP":
        return _assess_promotion_sweep(program, state, snapshot)
    state = _refresh_mastery_debt(program, state, snapshot)
    if _promotion_sweep_due(program, state, snapshot):
        return _start_promotion_sweep(program, state, snapshot)
    return _assess_ordinary(program, state, snapshot)


def assess_flash(program, state: SchoolState, snapshot: Assessment) -> SchoolState:
    """Use fresh routine evidence for scheduling without minting qualification authority.

    Flash mode may decide what should be taught next, including crossing grade
    boundaries, but it must not promote a grade, move champion pointers, or
    increment the authoritative grade-exam epoch. If every currently eligible
    grade is perfect, leave the assessment debt in place so a later full exam
    can establish qualification on the authoritative path.
    """
    program = _program(program)
    pool = _score_pool(program, state)
    _verify_assessment_boundary(program, state, snapshot, pool)
    if state.stage == "ASSESS_PROMOTION_SWEEP":
        # Stability promotion is qualification authority. Flash may collect the
        # fresh evidence but cannot consume it to advance the sweep.
        return replace(state, latest_rubric_digest=snapshot.rubric_digest)
    grade = next(g for g in program.grades if g.id == state.grade)
    if grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1:
        own = set(_main_queue(program, state))
        if all(snapshot.scores[c].perfect for c in own):
            next_stage = state.introduction_stage + 1
            return _at_introduction_stage(
                state, next_stage, stage="MAIN",
                queue=grade.teaching_stages[next_stage], first_recovery=(),
                latest_rubric_digest=snapshot.rubric_digest)

    if _perfect_in_grade(program, state.grade, snapshot.scores):
        if state.stage == "ASSESS_MAIN":
            continued = _continue_main_sweep(program, state, snapshot)
            if continued is not None:
                return continued
            # If another grade visited earlier in this sweep is still imperfect,
            # the ordinary sweep is complete and the two global recovery rounds
            # are due before regular progression resumes.
            trio = weakest_three(snapshot.scores, _instructional_pool(program, state, snapshot.scores, pool))
            if trio:
                visited = state.main_sweep_visited
                if state.grade not in visited:
                    visited = visited + (state.grade,)
                return replace(state, stage="RECOVERY_1", queue=trio,
                               first_recovery=trio, main_sweep_visited=visited,
                               latest_rubric_digest=snapshot.rubric_digest)
        resumed = _resume_ordinary_spiral(program, state, snapshot, reset_sweep=True)
        if resumed is not None and resumed.grade != state.grade:
            return resumed
        # No remaining imperfect grade exists. Hold the exact assessment debt
        # for a non-flash qualification exam instead of manufacturing a pass.
        return replace(state, latest_rubric_digest=snapshot.rubric_digest)

    if state.stage == "ASSESS_MAIN":
        continued = _continue_main_sweep(program, state, snapshot)
        if continued is not None:
            return continued
        trio = weakest_three(snapshot.scores, _instructional_pool(program, state, snapshot.scores, pool))
        return replace(state, stage="RECOVERY_1", queue=trio,
                       first_recovery=trio,
                       main_sweep_visited=(state.main_sweep_visited + (state.grade,)
                                           if state.grade not in state.main_sweep_visited
                                           else state.main_sweep_visited),
                       latest_rubric_digest=snapshot.rubric_digest)
    if state.stage == "ASSESS_RECOVERY_1":
        trio = weakest_three(snapshot.scores, _instructional_pool(program, state, snapshot.scores, pool))
        return replace(state, stage="RECOVERY_2", queue=trio,
                       latest_rubric_digest=snapshot.rubric_digest)
    resumed = _resume_ordinary_spiral(program, state, snapshot, reset_sweep=True)
    if resumed is None:
        return replace(state, latest_rubric_digest=snapshot.rubric_digest)
    return resumed


def assess_withheld(program, state: SchoolState, snapshot: Assessment,
                    withheld: tuple[str, ...], *,
                    rubric_capabilities: tuple[str, ...] | None = None) -> SchoolState:
    """Advance ordinary school work while retaining quarantined mastery debt.

    The snapshot contains only capabilities still eligible for this human
    command's ordinary evaluation.  Withheld capabilities are never assigned a
    synthetic/stale score and can never permit promotion.  When the remaining
    eligible work is exhausted the command stops at `DEFERRED_STAGNATION` for
    end-of-run review; a later command may explicitly re-enter that debt.
    """
    program = _program(program)
    if not withheld:
        return assess(program, state, snapshot)
    if state.stage == "ASSESS_PROMOTION_SWEEP":
        return_stage = state.promotion_sweep_return_stage
        ordinary = _promotion_sweep_fields_cleared(
            state, stage=return_stage, queue=(),
            latest_rubric_digest=snapshot.rubric_digest)
        return assess_withheld(
            program, ordinary, snapshot, withheld,
            rubric_capabilities=rubric_capabilities)
    pool = _score_pool(program, state)
    blocked = tuple(dict.fromkeys(withheld))
    if (len(blocked) != len(withheld) or not set(blocked) <= set(pool)):
        raise ValueError("STAGNATION_WITHHELD_CAPABILITY_OUTSIDE_ACTIVE_POOL")
    active_pool = tuple(cap for cap in pool if cap not in set(blocked))
    if not active_pool:
        return replace(state, stage="DEFERRED_STAGNATION", queue=(),
                       first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)
    _verify_assessment_boundary(
        program, state, snapshot, active_pool,
        rubric_pool=(rubric_capabilities if rubric_capabilities is not None else
                     active_pool if program.assessment_projections else pool),
    )

    grade = next(g for g in program.grades if g.id == state.grade)
    current_caps = set(_caps(program, (state.grade,)))
    blocked_current = current_caps & set(blocked)
    if (grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1 and
            not blocked_current):
        own = tuple(c for c in _main_queue(program, state) if c in active_pool)
        if own and all(snapshot.scores[c].perfect for c in own):
            next_stage = state.introduction_stage + 1
            entered = _at_introduction_stage(
                state, next_stage, stage="MAIN", first_recovery=(),
                latest_rubric_digest=snapshot.rubric_digest)
            queue = tuple(c for c in grade.teaching_stages[next_stage]
                          if c not in set(blocked))
            if queue:
                return replace(entered, queue=queue)

    # Any withheld capability remains explicit graduation debt; never promote
    # a grade or cumulative prefix from a partial ordinary assessment.
    if state.stage == "ASSESS_MAIN":
        continued = _continue_main_sweep(
            program, state, snapshot, allowed_capabilities=active_pool)
        if continued is not None:
            return continued
        trio = weakest_three(snapshot.scores, _instructional_pool(program, state, snapshot.scores, active_pool))
        if trio:
            visited = state.main_sweep_visited
            if state.grade not in visited:
                visited = visited + (state.grade,)
            return replace(state, stage="RECOVERY_1", queue=trio,
                           first_recovery=trio,
                           main_sweep_visited=visited,
                           latest_rubric_digest=snapshot.rubric_digest)
        return replace(state, stage="DEFERRED_STAGNATION", queue=(),
                       first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)
    if state.stage == "ASSESS_RECOVERY_1":
        trio = weakest_three(snapshot.scores, _instructional_pool(program, state, snapshot.scores, active_pool))
        if trio:
            return replace(state, stage="RECOVERY_2", queue=trio,
                           latest_rubric_digest=snapshot.rubric_digest)
        return replace(state, stage="DEFERRED_STAGNATION", queue=(),
                       first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)

    resumed = _resume_ordinary_spiral(
        program, state, snapshot, allowed_capabilities=active_pool,
        reset_sweep=True)
    if resumed is not None:
        return resumed
    return replace(state, stage="DEFERRED_STAGNATION", queue=(),
                   first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)


def reactivate_stagnation_debt(program, state: SchoolState,
                               debt: tuple[str, ...]) -> SchoolState:
    """Start a later human command by explicitly re-entering deferred debt."""
    program = _program(program)
    verify_state(program, state)
    if state.stage != "DEFERRED_STAGNATION" or not debt or len(set(debt)) != len(debt):
        raise ValueError("STAGNATION_REENTRY_INVALID")
    pool = _score_pool(program, state)
    if not set(debt) <= set(pool):
        raise ValueError("STAGNATION_REENTRY_OUTSIDE_ACTIVE_POOL")
    return replace(state, stage="RECOVERY_1", queue=tuple(debt),
                   first_recovery=tuple(debt[:3]))


def adopt_appended_program(previous: ScheduleProgram,
                           successor: ScheduleProgram,
                           state: SchoolState) -> SchoolState:
    """Admit exactly one appended projected grade without knowing its identity."""
    if (not isinstance(previous, ScheduleProgram) or
            not isinstance(successor, ScheduleProgram)):
        raise TypeError("FACTORY_SCHEDULE_PROGRAM_REQUIRED")
    verify_state(previous, state)
    previous_ids = tuple(grade.id for grade in previous.grades)
    successor_ids = tuple(grade.id for grade in successor.grades)
    if (previous.program_complete or
            state.stage != "AWAITING_NEXT_GRADE" or
            len(successor_ids) != len(previous_ids) + 1 or
            successor_ids[:-1] != previous_ids or
            successor.grades[:-1] != previous.grades):
        raise ValueError("FACTORY_SCHEDULE_APPEND_INVALID")
    if state.grade not in state.champions:
        raise ValueError("FACTORY_SCHEDULE_APPEND_REQUIRES_GRADUATED_PREFIX")
    added = successor_ids[-1]
    if added in state.champions:
        raise ValueError("FACTORY_SCHEDULE_APPEND_FUTURE_CHAMPION_EXISTS")
    extended = replace(
        state,
        course_digest=successor.digest(),
        grade_exam_epoch=state.grade_exam_epoch + 1,
        active_grades=successor_ids,
        stage="MAIN",
        first_recovery=(),
        main_sweep_visited=(),
        revalidation_target_grade=None,
        latest_rubric_digest=None,
        pending_failures=(),
        teacher_soup_digest=None,
        carried_mastery_debt=(),
    )
    return _enter_grade(successor, extended, len(previous.grades))


def append_next_grade_with_debt(
        previous, successor, state: SchoolState,
        mastery_debt: tuple[str, ...]) -> SchoolState:
    """Human-authorized append while preserving unresolved prior mastery debt.

    This is progression, not graduation.  It never fabricates a champion for
    an unresolved grade and it never clears debt merely because a later grade
    becomes available.  One later cumulative checkpoint must still perfect the
    complete active program before the ordinary next-grade boundary is reached.
    """
    previous, successor = _program(previous), _program(successor)
    verify_state(previous, state)
    if previous.program_complete:
        raise ValueError("DEBT_GRADE_APPEND_REQUIRES_PARTIAL_PROGRAM")
    if not mastery_debt or len(set(mastery_debt)) != len(mastery_debt):
        raise ValueError("DEBT_GRADE_APPEND_REQUIRES_EXPLICIT_MASTERY_DEBT")
    previous_caps = set(_caps(previous, tuple(g.id for g in previous.grades)))
    if not set(mastery_debt) <= previous_caps:
        raise ValueError("DEBT_GRADE_APPEND_DEBT_OUTSIDE_PREVIOUS_PROGRAM")
    if len(successor.grades) != len(previous.grades) + 1:
        raise ValueError("GRADE_APPEND_REQUIRES_EXACTLY_ONE_NEW_GRADE")
    if tuple(successor.grades[:len(previous.grades)]) != previous.grades:
        raise ValueError("GRADE_APPEND_WOULD_CHANGE_PREVIOUS_GRADE")
    if any(g.assessment_sha256 is None for g in previous.grades):
        raise ValueError("GRADE_APPEND_UNSEALED_PREVIOUS_GRADE")
    if state.revalidation_target_grade is not None:
        raise ValueError("DEBT_GRADE_APPEND_DURING_REVALIDATION_FORBIDDEN")
    grade_by_capability = {
        capability.id: grade.id
        for grade in previous.grades for capability in grade.capabilities
    }
    debt_grades = {grade_by_capability[capability] for capability in mastery_debt}
    mastered_required = set(state.active_grades) - debt_grades
    if not mastered_required <= set(state.champions):
        raise ValueError("DEBT_GRADE_APPEND_NONDEBT_GRADE_NOT_MASTERED")
    added = successor.grades[-1].id
    if added in state.champions:
        raise ValueError("GRADE_APPEND_FUTURE_CHAMPION_ALREADY_EXISTS")
    extended = replace(
        state, course_digest=successor.digest(),
        grade_exam_epoch=state.grade_exam_epoch + 1,
        active_grades=tuple(g.id for g in successor.grades),
        stage="MAIN", first_recovery=(), main_sweep_visited=(),
        revalidation_target_grade=None, latest_rubric_digest=None,
        pending_failures=(), teacher_soup_digest=None,
        carried_mastery_debt=tuple(mastery_debt))
    return _enter_grade(successor, extended, len(previous.grades))


def adopt_revised_program(previous: ScheduleProgram,
                          successor: ScheduleProgram,
                          state: SchoolState) -> tuple[SchoolState, str]:
    """Rebind one active projected grade after a profile roster revision."""
    if (not isinstance(previous, ScheduleProgram) or
            not isinstance(successor, ScheduleProgram)):
        raise TypeError("FACTORY_SCHEDULE_PROGRAM_REQUIRED")
    verify_state(previous, state)
    previous_ids = tuple(grade.id for grade in previous.grades)
    successor_ids = tuple(grade.id for grade in successor.grades)
    changed = tuple(
        index for index, (old, new) in
        enumerate(zip(previous.grades, successor.grades))
        if old != new)
    if (previous_ids != successor_ids or len(changed) != 1 or
            changed[0] != len(previous.grades) - 1):
        raise ValueError("FACTORY_SCHEDULE_REVISION_INVALID")
    revised_grade = successor_ids[changed[0]]
    if state.grade != revised_grade:
        raise ValueError("FACTORY_SCHEDULE_REVISION_REQUIRES_ACTIVE_GRADE")
    champions = dict(state.champions)
    champions.pop(revised_grade, None)
    successor_caps = set(_caps(successor, state.active_grades))
    active_debt = tuple(
        capability for capability in state.carried_mastery_debt
        if capability in successor_caps)
    rebound = replace(
        state,
        course_digest=successor.digest(),
        stage="MAIN",
        queue=(),
        first_recovery=(),
        champions=champions,
        carried_mastery_debt=active_debt,
        grade_exam_epoch=state.grade_exam_epoch + 1,
        introduction_stage=0,
        main_sweep_visited=(),
        revalidation_target_grade=None,
        latest_rubric_digest=None,
        pending_failures=(),
        teacher_soup_digest=None,
    )
    rebound = _enter_grade(successor, rebound, state.grade_index)
    verify_state(successor, rebound)
    return rebound, revised_grade


def append_next_grade(previous, successor, state: SchoolState) -> SchoolState:
    """Historical Course append migration; canonical v2 uses release deltas."""
    from bilqis_mlx.compatibility.scheduler_transitions import append_next_grade as legacy
    return legacy(previous, successor, state)


def revise_admitted_grade(previous, successor, state: SchoolState):
    """Historical Course revision; canonical v2 uses release deltas."""
    from bilqis_mlx.compatibility.scheduler_transitions import revise_admitted_grade as legacy
    return legacy(previous, successor, state)


def replace_admitted_grade(previous, successor, state: SchoolState):
    """Historical Course replacement; canonical v2 uses release deltas."""
    from bilqis_mlx.compatibility.scheduler_transitions import replace_admitted_grade as legacy
    return legacy(previous, successor, state)


def continue_after_soup(program, state: SchoolState,
                        *, frozen_teacher_receipt: str) -> SchoolState:
    """Start a new *grade cycle*. The causal student and AdamW are untouched."""
    program = _program(program)
    verify_state(program, state)
    if state.stage != "AWAITING_TEACHER_SOUP" or not state.pending_failures:
        raise ValueError("TEACHER_SOUP_NOT_DUE")
    if (len(frozen_teacher_receipt) != 64 or
            any(c not in "0123456789abcdef" for c in frozen_teacher_receipt)):
        raise ValueError("TEACHER_SOUP_RECEIPT_MISSING")
    restarted = replace(state, active_grades=state.pending_failures,
                   grade_exam_epoch=state.grade_exam_epoch + 1,
                   first_recovery=(), stage="MAIN",
                   main_sweep_visited=(),
                   pending_failures=(), school_cycles=state.school_cycles+1,
                   revalidation_target_grade=None,
                   teacher_soup_digest=frozen_teacher_receipt)
    return _enter_grade(program, restarted, 0)


def teacher_vote_weights(program, state: SchoolState) -> dict[str, int]:
    program = _program(program)
    if state.revalidation_target_grade is not None:
        # Every already-graduated grade is an eligible teacher when revisited,
        # including a grade numerically later than the active replay grade.
        return soup_weights(state.champions)
    return vote_counts(state.champions,
                       grade_order=tuple(g.id for g in program.grades),
                       active_grade=state.grade)


def whole_school_soup_weights(state: SchoolState) -> dict[str, int]:
    if state.stage != "AWAITING_TEACHER_SOUP":
        raise ValueError("NOT_AT_WHOLE_SCHOOL_SOUP_BOUNDARY")
    return soup_weights(state.champions)


def save_new_state(path: Path, state: SchoolState) -> None:
    """Exclusive no-overwrite write, rather than silent continuation of old run."""
    payload = json.dumps(asdict(state), sort_keys=True, indent=2) + "\n"
    atomic_text(path, payload)


def read_state(path: Path, program) -> SchoolState:
    """Use only for an explicitly requested --resume operation."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw["active_grades"] = tuple(raw["active_grades"])
    raw["queue"] = tuple(raw["queue"])
    raw["first_recovery"] = tuple(raw["first_recovery"])
    raw["pending_failures"] = tuple(raw["pending_failures"])
    raw["main_sweep_visited"] = tuple(raw.get("main_sweep_visited", ()))
    raw["carried_mastery_debt"] = tuple(raw.get("carried_mastery_debt", ()))
    raw["promotion_sweep_scope"] = tuple(raw.get("promotion_sweep_scope", ()))
    raw["promotion_sweep_return_stage"] = raw.get(
        "promotion_sweep_return_stage")
    raw["introduction_frontiers"] = tuple(
        (grade, stage) for grade, stage in raw.get("introduction_frontiers", ()))
    raw["current_student"] = Checkpoint(**raw["current_student"])
    raw["champions"] = {grade: Checkpoint(**cp)
                        for grade, cp in raw["champions"].items()}
    result = SchoolState(**raw)
    verify_state(program, result)
    return result


def choose_best_whole_student(program,
                              candidates: tuple[tuple[Checkpoint, Assessment], ...],
                              assessed_grades: tuple[str, ...]) -> Checkpoint:
    """Select ONE complete model+optimizer by same-rubric whole-student score.

    Never blend per-capability maxima across checkpoints or prefer latest step
    merely because the optimizer has run longer. Candidates must use the exact
    same questions/rubric identity and cover the entire observed grade pool.
    """
    if not candidates or not assessed_grades:
        raise ValueError("WHOLE_STUDENT_CANDIDATE_POOL_EMPTY")
    program = _program(program)
    required = _caps(program, assessed_grades)
    rubrics = set()
    totals = set()
    for candidate,assessment in candidates:
        assessment.verify(candidate,program,required)
        rubrics.add(assessment.rubric_digest)
        totals.add(tuple((k,assessment.scores[k].total) for k in required))
    if len(rubrics) != 1 or len(totals) != 1:
        raise ValueError("WHOLE_STUDENT_CANDIDATES_NOT_COMPARABLE")
    def rank(row):
        candidate,assessment = row
        correct = sum(assessment.scores[c].correct for c in required)
        total = sum(assessment.scores[c].total for c in required)
        return (Fraction(correct,total),-candidate.optimizer_step,candidate.sha256)
    return max(candidates,key=rank)[0]
