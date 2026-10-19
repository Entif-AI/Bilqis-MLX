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
from bilqis_mlx.curriculum import Course, validate
from bilqis_mlx.runtime.disk import atomic_text


STAGES = frozenset(("MAIN", "ASSESS_MAIN", "RECOVERY_1", "ASSESS_RECOVERY_1",
                    "RECOVERY_2", "ASSESS_RECOVERY_2", "AWAITING_TEACHER_SOUP",
                    "AWAITING_NEXT_GRADE", "WHOLE_SCHOOL_MASTERED",
                    "DEFERRED_STAGNATION"))


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

    def verify(self, checkpoint: Checkpoint, course: Course,
               required_capabilities: tuple[str, ...], *,
               rubric_capabilities: tuple[str, ...] | None = None) -> None:
        if (self.checkpoint_sha256 != checkpoint.sha256 or
                self.optimizer_step != checkpoint.optimizer_step or
                self.course_digest != course.digest()):
            raise ValueError("ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE")
        if (len(self.rubric_digest) != 64 or
                any(c not in "0123456789abcdef" for c in self.rubric_digest) or
                not self.evaluation_id):
            raise ValueError("ASSESSMENT_RUBRIC_IDENTITY_MISSING")
        rubric_scope = (required_capabilities if rubric_capabilities is None
                        else rubric_capabilities)
        if not set(required_capabilities) <= set(rubric_scope):
            raise ValueError("ASSESSMENT_RUBRIC_SCOPE_DOES_NOT_COVER_ACTIVE_POOL")
        represented = [grade for grade in course.grades if
                       any(cap.id in rubric_scope
                           for cap in grade.capabilities)]
        if not represented:
            raise ValueError("ASSESSMENT_HAS_NO_REPRESENTED_GRADE")
        # Each grade seals its *cumulative* exam (including prior grades).
        # A newly introduced B rubric need not share A's exam digest.
        grade_seal = represented[-1].assessment_sha256
        if grade_seal is not None and self.rubric_digest != grade_seal:
            raise ValueError("ASSESSMENT_NOT_GRADE_SEALED_RUBRIC")
        all_caps = _caps(course, tuple(g.id for g in course.grades))
        if (set(rubric_scope) == set(all_caps) and
                course.assessment_manifest_sha256 is not None and
                self.rubric_digest != course.assessment_manifest_sha256):
            raise ValueError("ASSESSMENT_NOT_COURSE_SEALED_RUBRIC")
        if set(self.scores) != set(required_capabilities):
            raise ValueError("ASSESSMENT_NOT_COMPLETE_ACTIVE_POOL")
        if not all(isinstance(s, Score) for s in self.scores.values()):
            raise ValueError("ASSESSMENT_INVALID_SCORE_TYPE")
        declared_counts = {cap: count for grade in course.grades
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
    # Grades that already received their ordinary full MAIN pass in the
    # current cross-grade sweep. Global weakest-three recovery is due only
    # after every currently imperfect eligible grade has had that pass.
    main_sweep_visited: tuple[str, ...] = ()

    @property
    def grade(self) -> str:
        return self.active_grades[self.grade_index]


def _caps(course: Course, grade_ids: tuple[str, ...]) -> tuple[str, ...]:
    lookup = {grade.id: grade for grade in course.grades}
    return tuple(c.id for grade in grade_ids for c in lookup[grade].capabilities)


def _score_pool(course: Course, state: SchoolState) -> tuple[str, ...]:
    represented = set(state.champions) | {state.grade}
    if state.latest_rubric_digest is not None:
        sealed = [index for index, grade in enumerate(course.grades)
                  if grade.id in state.active_grades and
                  grade.assessment_sha256 == state.latest_rubric_digest]
        if sealed:
            cutoff = max(sealed)
            represented.update(
                grade.id for grade in course.grades[:cutoff + 1]
                if grade.id in state.active_grades)
    seen = tuple(g.id for g in course.grades if g.id in represented)
    current = {g.id: g for g in course.grades}[state.grade]
    introduced = (set(c for stage in current.teaching_stages[:state.introduction_stage+1]
                      for c in stage) if current.teaching_stages else
                  {c.id for c in current.capabilities})
    return tuple(cap for cap in _caps(course, seen)
                 if cap in introduced or cap not in {c.id for c in current.capabilities})


def assessment_capabilities(course: Course, state: SchoolState) -> tuple[str, ...]:
    """Expose only already introduced concepts plus earlier mastered grades."""
    verify_state(course, state)
    return _score_pool(course, state)


def _main_queue(course: Course, state: SchoolState) -> tuple[str, ...]:
    return tuple(c for c in _score_pool(course, state)
                 if c in _caps(course, (state.grade,)))


def _enter_grade(course: Course, state: SchoolState, grade_index: int, **changes) -> SchoolState:
    grade_id = state.active_grades[grade_index]
    grade = next(g for g in course.grades if g.id == grade_id)
    index = len(grade.teaching_stages)-1 if grade_id in state.champions and grade.teaching_stages else 0
    entered = replace(state, grade_index=grade_index, introduction_stage=index, **changes)
    return replace(entered, queue=_main_queue(course, entered))


def start_new(course: Course, initial_student: Checkpoint) -> SchoolState:
    validate(course)
    state = SchoolState(schema="bilqis.mlx.letter-grade/v1",
                       course_digest=course.digest(),
                       active_grades=tuple(g.id for g in course.grades),
                       grade_index=0, stage="MAIN",
                       queue=_caps(course, (course.grades[0].id,)),
                       first_recovery=(), current_student=initial_student,
                       champions={})
    return replace(state, queue=_main_queue(course, state))


def verify_state(course: Course, state: SchoolState):
    validate(course)
    if (state.schema != "bilqis.mlx.letter-grade/v1" or
            state.course_digest != course.digest() or state.stage not in STAGES or
            not state.active_grades or not 0 <= state.grade_index < len(state.active_grades)):
        raise ValueError("INVALID_OR_DRIFTED_SCHOOL_STATE")
    known = {g.id for g in course.grades}
    if (not set(state.active_grades) <= known or
            tuple(g.id for g in course.grades if g.id in state.active_grades) != state.active_grades or
            not set(state.champions) <= known):
        raise ValueError("INVALID_GRADE_PROGRAM_OR_CHAMPIONS")
    if any(cap not in _score_pool(course, state) for cap in state.queue + state.first_recovery):
        raise ValueError("QUEUE_CAPABILITY_OUTSIDE_ACTIVE_AND_PASSED_GRADES")
    if (state.visits < 0 or state.school_cycles < 1 or
            type(state.grade_exam_epoch) is not int or state.grade_exam_epoch < 0 or
            type(state.introduction_stage) is not int or state.introduction_stage < 0):
        raise ValueError("INVALID_SCHOOL_COUNTER")
    if (len(set(state.main_sweep_visited)) != len(state.main_sweep_visited) or
            not set(state.main_sweep_visited) <= set(state.active_grades)):
        raise ValueError("INVALID_MAIN_SWEEP_HISTORY")
    current = next(g for g in course.grades if g.id == state.grade)
    if state.introduction_stage >= max(1, len(current.teaching_stages)):
        raise ValueError("INVALID_INTRODUCTION_STAGE")
    if state.revalidation_target_grade is not None:
        if (state.revalidation_target_grade not in state.active_grades[1:] or
                state.grade_index > state.active_grades.index(state.revalidation_target_grade) or
                state.stage not in ("MAIN", "ASSESS_MAIN", "RECOVERY_1",
                                    "ASSESS_RECOVERY_1", "RECOVERY_2", "ASSESS_RECOVERY_2",
                                    "DEFERRED_STAGNATION") or
                not set(state.active_grades[:state.active_grades.index(
                    state.revalidation_target_grade) + 1]) <= set(state.champions)):
            raise ValueError("INVALID_GRADE_REVALIDATION_STATE")
    if state.stage == "AWAITING_NEXT_GRADE" and (
            course.program_complete or state.grade != course.grades[-1].id or
            state.queue or state.pending_failures or
            state.grade not in state.champions):
        raise ValueError("INVALID_PARTIAL_SCHOOL_COMPLETION")
    if state.stage == "WHOLE_SCHOOL_MASTERED" and not course.program_complete:
        raise ValueError("WHOLE_SCHOOL_CANNOT_COMPLETE_PARTIAL_COURSE")


def next_capability(state: SchoolState) -> str | None:
    return state.queue[0] if state.stage in ("MAIN", "RECOVERY_1", "RECOVERY_2") and state.queue else None


def visit(course: Course, state: SchoolState, capability: str,
          student_after_visit: Checkpoint) -> SchoolState:
    """Record a completed human-run visit. Caller supplies the admitted full student.

    A rejected candidate leaves the complete student checkpoint unchanged.
    """
    verify_state(course, state)
    if next_capability(state) != capability:
        raise ValueError("VISIT_NOT_NEXT_SCHEDULED_CAPABILITY")
    rest = state.queue[1:]
    after = state.stage if rest else "ASSESS_" + ("MAIN" if state.stage == "MAIN" else state.stage)
    return replace(state, queue=rest, stage=after, visits=state.visits+1,
                   current_student=student_after_visit)


def require_assessment_after_flash(course: Course, state: SchoolState) -> SchoolState:
    """End flash mode owing a real assessment before normal scheduling resumes."""
    verify_state(course, state)
    if state.stage in ("ASSESS_MAIN", "ASSESS_RECOVERY_1", "ASSESS_RECOVERY_2"):
        return state
    if state.stage not in ("MAIN", "RECOVERY_1", "RECOVERY_2"):
        raise ValueError("FLASH_MODE_CANNOT_REQUIRE_ASSESSMENT_FROM_STAGE")
    return replace(state, stage="ASSESS_" + state.stage, queue=())


def weakest_three(scores: dict[str, Score], pool: tuple[str, ...]) -> tuple[str, ...]:
    """Select up to three failures from the complete cumulative introduced pool."""
    if len(set(pool)) != len(pool) or not set(pool) <= set(scores):
        raise ValueError("WEAKEST_THREE_INCOMPLETE_POOL")
    ranking = sorted((c for c in pool if not scores[c].perfect),
                     key=lambda c: (scores[c].accuracy, c))
    return tuple(ranking[:3])


def _perfect_in_grade(course: Course, grade: str, scores: dict[str, Score]) -> bool:
    return all(scores[c].perfect for c in _caps(course, (grade,)))


def _next_imperfect_grade_index(course: Course, state: SchoolState,
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
        grade_caps = _caps(course, (state.active_grades[index],))
        eligible = tuple(cap for cap in grade_caps if cap in allowed)
        if not eligible:
            continue
        # An ordinary pass is due when any currently eligible capability in the
        # grade is imperfect. Missing/withheld capabilities are handled by the
        # caller's explicit containment authority, never synthesized as perfect.
        if any(not scores[cap].perfect for cap in eligible):
            return index
    return None


def _resume_ordinary_spiral(course: Course, state: SchoolState,
                            snapshot: Assessment, *,
                            allowed_capabilities: tuple[str, ...] | None = None,
                            reset_sweep: bool = True) -> SchoolState | None:
    index = _next_imperfect_grade_index(
        course, state, snapshot.scores, allowed_capabilities=allowed_capabilities)
    if index is None:
        return None
    entered = _enter_grade(
        course, state, index, stage="MAIN", first_recovery=(),
        main_sweep_visited=() if reset_sweep else state.main_sweep_visited,
        latest_rubric_digest=snapshot.rubric_digest)
    if allowed_capabilities is None:
        return entered
    allowed = set(allowed_capabilities)
    queue = tuple(cap for cap in entered.queue if cap in allowed)
    if not queue:
        return None
    return replace(entered, queue=queue)


def _continue_main_sweep(course: Course, state: SchoolState,
                         snapshot: Assessment, *,
                         allowed_capabilities: tuple[str, ...] | None = None) -> SchoolState | None:
    """Continue ordinary grade passes before scheduling global recovery.

    A grade enters `main_sweep_visited` only after its complete currently
    introduced MAIN queue has been assessed. Recovery therefore happens at
    most twice *between* full multi-grade sweeps, not twice after every grade.
    """
    grade = next(g for g in course.grades if g.id == state.grade)
    if (grade.teaching_stages and
            state.introduction_stage < len(grade.teaching_stages) - 1):
        # An incompletely introduced staged grade is not yet an ordinary
        # cross-grade sweep member. Its current stage must pass/remediate first.
        return None
    visited = state.main_sweep_visited
    if state.grade not in visited:
        visited = visited + (state.grade,)
    index = _next_imperfect_grade_index(
        course, state, snapshot.scores,
        allowed_capabilities=allowed_capabilities,
        excluded_grades=visited)
    if index is None:
        return None
    entered = _enter_grade(
        course, state, index, stage="MAIN", first_recovery=(),
        main_sweep_visited=visited,
        latest_rubric_digest=snapshot.rubric_digest)
    if allowed_capabilities is None:
        return entered
    allowed = set(allowed_capabilities)
    queue = tuple(cap for cap in entered.queue if cap in allowed)
    if not queue:
        return None
    return replace(entered, queue=queue)


def _finish_grade_series(course: Course, state: SchoolState, assessment: Assessment,
                         pointers: dict[str, Checkpoint]) -> SchoolState:
    """Advance to the next grade or stop at a verified course boundary."""
    next_index = state.grade_index + 1
    if next_index < len(state.active_grades):
        next_grade = state.active_grades[next_index]
        return _enter_grade(course, state, next_index,
                       stage="MAIN", first_recovery=(), champions=pointers,
                       main_sweep_visited=(),
                       revalidation_target_grade=None,
                       # The newly admitted grade owns the next cumulative seal.
                       latest_rubric_digest=None)
    if not course.program_complete:
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
    all_caps = _caps(course, tuple(g.id for g in course.grades))
    if set(assessment.scores) != set(all_caps):
        raise ValueError("FINAL_WHOLE_SCHOOL_SNAPSHOT_INCOMPLETE")
    failed = tuple(g.id for g in course.grades
                   if not _perfect_in_grade(course, g.id, assessment.scores))
    return replace(state, queue=(), first_recovery=(), champions=pointers,
                   stage="AWAITING_TEACHER_SOUP" if failed else "WHOLE_SCHOOL_MASTERED",
                   main_sweep_visited=(),
                   revalidation_target_grade=None,
                   latest_rubric_digest=assessment.rubric_digest,
                   pending_failures=failed)


def _promote(course: Course, state: SchoolState, assessment: Assessment) -> SchoolState:
    candidate = state.current_student
    previous = tuple(g.id for g in course.grades if g.id in state.champions)
    full_at_candidate = tuple(g for g in previous if _perfect_in_grade(course, g, assessment.scores))
    pointers = repoint_earlier(state.champions, candidate,
                               previously_passed=previous,
                               fully_mastered_at_this_candidate=full_at_candidate)
    pointers[state.grade] = candidate

    target = state.revalidation_target_grade
    if target is not None:
        target_index = state.active_grades.index(target)
        if state.grade_index < target_index:
            # A/B/C are revisited in order, with their normal full-grade,
            # weakest-three and same-checkpoint assessment schedule.
            next_index = state.grade_index + 1
            return _enter_grade(course, state, next_index,
                           stage="MAIN", first_recovery=(), champions=pointers,
                           main_sweep_visited=())
        failed = tuple(g for g in state.active_grades[:target_index + 1]
                       if not _perfect_in_grade(course, g, assessment.scores))
        if failed:
            if course.program_complete and target == course.grades[-1].id:
                # Preserve the original final-program teacher-soup recovery:
                # only failed grades are revisited in that next school cycle.
                return replace(state, queue=(), first_recovery=(), champions=pointers,
                               stage="AWAITING_TEACHER_SOUP", pending_failures=failed,
                               main_sweep_visited=(),
                               revalidation_target_grade=None,
                               latest_rubric_digest=assessment.rubric_digest)
            # At a partial-program boundary, do not start C if the final B
            # checkpoint lost A. Repeat the ordered prefix until it sticks.
            return _enter_grade(course, state, 0, stage="MAIN",
                           first_recovery=(), champions=pointers,
                           main_sweep_visited=())
        return _finish_grade_series(course, state, assessment, pointers)

    if state.grade_index > 0 and state.grade not in state.champions:
        # Newly mastered B triggers A->B; C triggers A->B->C, etc.
        # Even a perfect initial cumulative B examination is followed by a
        # fresh ordered revalidation pass before the next grade is entered.
        return _enter_grade(course, state, 0, stage="MAIN",
                       first_recovery=(), champions=pointers,
                       main_sweep_visited=(),
                       revalidation_target_grade=state.grade,
                       latest_rubric_digest=assessment.rubric_digest)
    return _finish_grade_series(course, state, assessment, pointers)


def _verify_assessment_boundary(course: Course, state: SchoolState,
                                snapshot: Assessment,
                                pool: tuple[str, ...], *,
                                rubric_pool: tuple[str, ...] | None = None) -> None:
    verify_state(course, state)
    if state.stage not in ("ASSESS_MAIN", "ASSESS_RECOVERY_1", "ASSESS_RECOVERY_2"):
        raise ValueError("ASSESSMENT_NOT_SCHEDULED_AT_DURABLE_BOUNDARY")
    snapshot.verify(
        state.current_student, course, pool,
        rubric_capabilities=rubric_pool,
    )
    if (state.latest_rubric_digest is not None and
            state.latest_rubric_digest != snapshot.rubric_digest):
        raise ValueError("ASSESSMENT_RUBRIC_CHANGED_MID_COURSE")


def assess(course: Course, state: SchoolState, snapshot: Assessment) -> SchoolState:
    pool = _score_pool(course, state)
    _verify_assessment_boundary(course, state, snapshot, pool)
    grade = next(g for g in course.grades if g.id == state.grade)
    if grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1:
        own = set(_main_queue(course, state))
        if all(snapshot.scores[c].perfect for c in own):
            next_stage = state.introduction_stage + 1
            return replace(state, introduction_stage=next_stage, stage="MAIN",
                           queue=grade.teaching_stages[next_stage], first_recovery=(),
                           latest_rubric_digest=snapshot.rubric_digest)
    if _perfect_in_grade(course, state.grade, snapshot.scores):
        return replace(_promote(course, state, snapshot),
                       grade_exam_epoch=state.grade_exam_epoch + 1)
    if state.stage == "ASSESS_MAIN":
        continued = _continue_main_sweep(course, state, snapshot)
        if continued is not None:
            return continued
        trio = weakest_three(snapshot.scores, pool)
        return replace(state, stage="RECOVERY_1", queue=trio,
                       first_recovery=trio,
                       main_sweep_visited=(state.main_sweep_visited + (state.grade,)
                                           if state.grade not in state.main_sweep_visited
                                           else state.main_sweep_visited),
                       latest_rubric_digest=snapshot.rubric_digest)
    if state.stage == "ASSESS_RECOVERY_1":
        # The second ranking is fresh, not disjoint. An unresolved weakness
        # must not become ineligible merely because round one selected it.
        trio = weakest_three(snapshot.scores, pool)
        return replace(state, stage="RECOVERY_2", queue=trio,
                       latest_rubric_digest=snapshot.rubric_digest)
    # weakest_three is deliberately bounded to two rounds. After round two,
    # resume ordinary sequential grade progression, skipping grades already
    # perfect on this cumulative assessment. Never start a third recovery burst
    # before another ordinary grade pass.
    resumed = _resume_ordinary_spiral(course, state, snapshot, reset_sweep=True)
    if resumed is None:
        raise ValueError("SPIRAL_RECOVERY_ENDED_WITHOUT_IMPERFECT_GRADE")
    return resumed


def assess_flash(course: Course, state: SchoolState, snapshot: Assessment) -> SchoolState:
    """Use fresh routine evidence for scheduling without minting qualification authority.

    Flash mode may decide what should be taught next, including crossing grade
    boundaries, but it must not promote a grade, move champion pointers, or
    increment the authoritative grade-exam epoch. If every currently eligible
    grade is perfect, leave the assessment debt in place so a later full exam
    can establish qualification on the authoritative path.
    """
    pool = _score_pool(course, state)
    _verify_assessment_boundary(course, state, snapshot, pool)
    grade = next(g for g in course.grades if g.id == state.grade)
    if grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1:
        own = set(_main_queue(course, state))
        if all(snapshot.scores[c].perfect for c in own):
            next_stage = state.introduction_stage + 1
            return replace(state, introduction_stage=next_stage, stage="MAIN",
                           queue=grade.teaching_stages[next_stage], first_recovery=(),
                           latest_rubric_digest=snapshot.rubric_digest)

    if _perfect_in_grade(course, state.grade, snapshot.scores):
        if state.stage == "ASSESS_MAIN":
            continued = _continue_main_sweep(course, state, snapshot)
            if continued is not None:
                return continued
            # If another grade visited earlier in this sweep is still imperfect,
            # the ordinary sweep is complete and the two global recovery rounds
            # are due before regular progression resumes.
            trio = weakest_three(snapshot.scores, pool)
            if trio:
                visited = state.main_sweep_visited
                if state.grade not in visited:
                    visited = visited + (state.grade,)
                return replace(state, stage="RECOVERY_1", queue=trio,
                               first_recovery=trio, main_sweep_visited=visited,
                               latest_rubric_digest=snapshot.rubric_digest)
        resumed = _resume_ordinary_spiral(course, state, snapshot, reset_sweep=True)
        if resumed is not None and resumed.grade != state.grade:
            return resumed
        # No remaining imperfect grade exists. Hold the exact assessment debt
        # for a non-flash qualification exam instead of manufacturing a pass.
        return replace(state, latest_rubric_digest=snapshot.rubric_digest)

    if state.stage == "ASSESS_MAIN":
        continued = _continue_main_sweep(course, state, snapshot)
        if continued is not None:
            return continued
        trio = weakest_three(snapshot.scores, pool)
        return replace(state, stage="RECOVERY_1", queue=trio,
                       first_recovery=trio,
                       main_sweep_visited=(state.main_sweep_visited + (state.grade,)
                                           if state.grade not in state.main_sweep_visited
                                           else state.main_sweep_visited),
                       latest_rubric_digest=snapshot.rubric_digest)
    if state.stage == "ASSESS_RECOVERY_1":
        trio = weakest_three(snapshot.scores, pool)
        return replace(state, stage="RECOVERY_2", queue=trio,
                       latest_rubric_digest=snapshot.rubric_digest)
    resumed = _resume_ordinary_spiral(course, state, snapshot, reset_sweep=True)
    if resumed is None:
        return replace(state, latest_rubric_digest=snapshot.rubric_digest)
    return resumed


def assess_withheld(course: Course, state: SchoolState, snapshot: Assessment,
                    withheld: tuple[str, ...]) -> SchoolState:
    """Advance ordinary school work while retaining quarantined mastery debt.

    The snapshot contains only capabilities still eligible for this human
    command's ordinary evaluation.  Withheld capabilities are never assigned a
    synthetic/stale score and can never permit promotion.  When the remaining
    eligible work is exhausted the command stops at `DEFERRED_STAGNATION` for
    end-of-run review; a later command may explicitly re-enter that debt.
    """
    if not withheld:
        return assess(course, state, snapshot)
    pool = _score_pool(course, state)
    blocked = tuple(dict.fromkeys(withheld))
    if (len(blocked) != len(withheld) or not set(blocked) <= set(pool)):
        raise ValueError("STAGNATION_WITHHELD_CAPABILITY_OUTSIDE_ACTIVE_POOL")
    active_pool = tuple(cap for cap in pool if cap not in set(blocked))
    if not active_pool:
        return replace(state, stage="DEFERRED_STAGNATION", queue=(),
                       first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)
    _verify_assessment_boundary(
        course, state, snapshot, active_pool,
        rubric_pool=pool,
    )

    grade = next(g for g in course.grades if g.id == state.grade)
    current_caps = set(_caps(course, (state.grade,)))
    blocked_current = current_caps & set(blocked)
    if (grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1 and
            not blocked_current):
        own = tuple(c for c in _main_queue(course, state) if c in active_pool)
        if own and all(snapshot.scores[c].perfect for c in own):
            next_stage = state.introduction_stage + 1
            entered = replace(state, introduction_stage=next_stage, stage="MAIN",
                              first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)
            queue = tuple(c for c in grade.teaching_stages[next_stage]
                          if c not in set(blocked))
            if queue:
                return replace(entered, queue=queue)

    # Any withheld capability remains explicit graduation debt; never promote
    # a grade or cumulative prefix from a partial ordinary assessment.
    if state.stage == "ASSESS_MAIN":
        continued = _continue_main_sweep(
            course, state, snapshot, allowed_capabilities=active_pool)
        if continued is not None:
            return continued
        trio = weakest_three(snapshot.scores, active_pool)
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
        trio = weakest_three(snapshot.scores, active_pool)
        if trio:
            return replace(state, stage="RECOVERY_2", queue=trio,
                           latest_rubric_digest=snapshot.rubric_digest)
        return replace(state, stage="DEFERRED_STAGNATION", queue=(),
                       first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)

    resumed = _resume_ordinary_spiral(
        course, state, snapshot, allowed_capabilities=active_pool,
        reset_sweep=True)
    if resumed is not None:
        return resumed
    return replace(state, stage="DEFERRED_STAGNATION", queue=(),
                   first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)


def reactivate_stagnation_debt(course: Course, state: SchoolState,
                               debt: tuple[str, ...]) -> SchoolState:
    """Start a later human command by explicitly re-entering deferred debt."""
    verify_state(course, state)
    if state.stage != "DEFERRED_STAGNATION" or not debt or len(set(debt)) != len(debt):
        raise ValueError("STAGNATION_REENTRY_INVALID")
    pool = _score_pool(course, state)
    if not set(debt) <= set(pool):
        raise ValueError("STAGNATION_REENTRY_OUTSIDE_ACTIVE_POOL")
    return replace(state, stage="RECOVERY_1", queue=tuple(debt),
                   first_recovery=tuple(debt[:3]))


def append_next_grade(previous: Course, successor: Course,
                      state: SchoolState) -> SchoolState:
    """Explicit append-only course migration at a completed tranche boundary.

    A previously released grade's exact definitions and grade-level question
    seal may not change when the next grade is added. A full-program terminal
    status never arises just because one released tranche was the last known.
    """
    verify_state(previous, state)
    validate(successor)
    if previous.program_complete or state.stage != "AWAITING_NEXT_GRADE":
        raise ValueError("GRADE_APPEND_NOT_AT_PARTIAL_BOUNDARY")
    if len(successor.grades) != len(previous.grades) + 1:
        raise ValueError("GRADE_APPEND_REQUIRES_EXACTLY_ONE_NEW_GRADE")
    if tuple(successor.grades[:len(previous.grades)]) != previous.grades:
        raise ValueError("GRADE_APPEND_WOULD_CHANGE_PREVIOUS_GRADE")
    if any(g.assessment_sha256 is None for g in previous.grades):
        raise ValueError("GRADE_APPEND_UNSEALED_PREVIOUS_GRADE")
    if (previous.assessment_manifest_sha256 is not None and
            state.latest_rubric_digest != previous.assessment_manifest_sha256):
        raise ValueError("GRADE_APPEND_PRIOR_RUBRIC_NOT_VERIFIED")
    successor_ids = tuple(g.id for g in successor.grades)
    added = successor.grades[-1].id
    if added in state.champions:
        raise ValueError("GRADE_APPEND_FUTURE_CHAMPION_ALREADY_EXISTS")
    extended = replace(state, course_digest=successor.digest(),
                   grade_exam_epoch=state.grade_exam_epoch + 1,
                   active_grades=successor_ids,
                   stage="MAIN", first_recovery=(),
                   main_sweep_visited=(),
                   revalidation_target_grade=None,
                   latest_rubric_digest=None, pending_failures=(),
                   teacher_soup_digest=None)
    return _enter_grade(successor, extended, len(previous.grades))


def revise_admitted_grade(previous: Course, successor: Course,
                          state: SchoolState) -> tuple[SchoolState, str]:
    """Neural-inert rebind when one admitted grade gains new capability debt."""
    verify_state(previous, state)
    validate(successor)
    if (previous.program_complete or successor.program_complete or
            tuple(grade.id for grade in previous.grades) !=
            tuple(grade.id for grade in successor.grades)):
        raise ValueError("GRADE_REVISION_REQUIRES_SAME_PARTIAL_GRADE_PROGRAM")
    changed = [(old, new) for old, new in zip(previous.grades, successor.grades)
               if old != new]
    if len(changed) != 1:
        raise ValueError("GRADE_REVISION_REQUIRES_EXACTLY_ONE_CHANGED_GRADE")
    old_grade, new_grade = changed[0]
    old_by_id = {cap.id: cap for cap in old_grade.capabilities}
    new_by_id = {cap.id: cap for cap in new_grade.capabilities}
    if (not set(old_by_id) < set(new_by_id) or
            tuple(cap.id for cap in new_grade.capabilities[:len(old_grade.capabilities)]) !=
            tuple(old_by_id)):
        raise ValueError("GRADE_REVISION_MUST_APPEND_CAPABILITY_DEBT")
    for cap_id, old_cap in old_by_id.items():
        new_cap = new_by_id[cap_id]
        if replace(new_cap, lesson_generator=old_cap.lesson_generator) != old_cap:
            raise ValueError("GRADE_REVISION_CHANGED_EXISTING_SEMANTICS")

    champions = dict(state.champions)
    champions.pop(old_grade.id, None)
    current_grade = state.grade
    current_caps = tuple(cap.id for grade in successor.grades
                         if grade.id == current_grade for cap in grade.capabilities)
    revised = replace(
        state, course_digest=successor.digest(), stage="MAIN", queue=current_caps,
        first_recovery=(), champions=champions,
        grade_exam_epoch=state.grade_exam_epoch + 1, introduction_stage=0,
        main_sweep_visited=(), revalidation_target_grade=None,
        latest_rubric_digest=None, pending_failures=(), teacher_soup_digest=None)
    verify_state(successor, revised)
    return revised, old_grade.id


def continue_after_soup(course: Course, state: SchoolState,
                        *, frozen_teacher_receipt: str) -> SchoolState:
    """Start a new *grade cycle*. The causal student and AdamW are untouched."""
    verify_state(course, state)
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
    return _enter_grade(course, restarted, 0)


def teacher_vote_weights(course: Course, state: SchoolState) -> dict[str, int]:
    if state.revalidation_target_grade is not None:
        # Every already-graduated grade is an eligible teacher when revisited,
        # including a grade numerically later than the active replay grade.
        return soup_weights(state.champions)
    return vote_counts(state.champions,
                       grade_order=tuple(g.id for g in course.grades),
                       active_grade=state.grade)


def whole_school_soup_weights(state: SchoolState) -> dict[str, int]:
    if state.stage != "AWAITING_TEACHER_SOUP":
        raise ValueError("NOT_AT_WHOLE_SCHOOL_SOUP_BOUNDARY")
    return soup_weights(state.champions)


def save_new_state(path: Path, state: SchoolState) -> None:
    """Exclusive no-overwrite write, rather than silent continuation of old run."""
    payload = json.dumps(asdict(state), sort_keys=True, indent=2) + "\n"
    atomic_text(path, payload)


def read_state(path: Path, course: Course) -> SchoolState:
    """Use only for an explicitly requested --resume operation."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw["active_grades"] = tuple(raw["active_grades"])
    raw["queue"] = tuple(raw["queue"])
    raw["first_recovery"] = tuple(raw["first_recovery"])
    raw["pending_failures"] = tuple(raw["pending_failures"])
    raw["main_sweep_visited"] = tuple(raw.get("main_sweep_visited", ()))
    raw["current_student"] = Checkpoint(**raw["current_student"])
    raw["champions"] = {grade: Checkpoint(**cp)
                        for grade, cp in raw["champions"].items()}
    result = SchoolState(**raw)
    verify_state(course, result)
    return result


def choose_best_whole_student(course: Course,
                              candidates: tuple[tuple[Checkpoint, Assessment], ...],
                              assessed_grades: tuple[str, ...]) -> Checkpoint:
    """Select ONE complete model+optimizer by same-rubric whole-student score.

    Never blend per-capability maxima across checkpoints or prefer latest step
    merely because the optimizer has run longer. Candidates must use the exact
    same questions/rubric identity and cover the entire observed grade pool.
    """
    if not candidates or not assessed_grades:
        raise ValueError("WHOLE_STUDENT_CANDIDATE_POOL_EMPTY")
    required = _caps(course, assessed_grades)
    rubrics = set()
    totals = set()
    for candidate,assessment in candidates:
        assessment.verify(candidate,course,required)
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
