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

from .champions import Checkpoint, repoint_earlier, vote_counts, soup_weights
from .curriculum import Course, validate
from .disk import atomic_text


STAGES = frozenset(("MAIN", "ASSESS_MAIN", "RECOVERY_1", "ASSESS_RECOVERY_1",
                    "RECOVERY_2", "ASSESS_RECOVERY_2", "AWAITING_TEACHER_SOUP",
                    "AWAITING_NEXT_GRADE", "WHOLE_SCHOOL_MASTERED"))


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
               required_capabilities: tuple[str, ...]) -> None:
        if (self.checkpoint_sha256 != checkpoint.sha256 or
                self.optimizer_step != checkpoint.optimizer_step or
                self.course_digest != course.digest()):
            raise ValueError("ASSESSMENT_NOT_SAME_CHECKPOINT_OR_COURSE")
        if (len(self.rubric_digest) != 64 or
                any(c not in "0123456789abcdef" for c in self.rubric_digest) or
                not self.evaluation_id):
            raise ValueError("ASSESSMENT_RUBRIC_IDENTITY_MISSING")
        represented = [grade for grade in course.grades if
                       any(cap.id in required_capabilities
                           for cap in grade.capabilities)]
        if not represented:
            raise ValueError("ASSESSMENT_HAS_NO_REPRESENTED_GRADE")
        # Each grade seals its *cumulative* exam (including prior grades).
        # A newly introduced B rubric need not share A's exam digest.
        grade_seal = represented[-1].assessment_sha256
        if grade_seal is not None and self.rubric_digest != grade_seal:
            raise ValueError("ASSESSMENT_NOT_GRADE_SEALED_RUBRIC")
        all_caps = _caps(course, tuple(g.id for g in course.grades))
        if (set(required_capabilities) == set(all_caps) and
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

    @property
    def grade(self) -> str:
        return self.active_grades[self.grade_index]


def _caps(course: Course, grade_ids: tuple[str, ...]) -> tuple[str, ...]:
    lookup = {grade.id: grade for grade in course.grades}
    return tuple(c.id for grade in grade_ids for c in lookup[grade].capabilities)


def _score_pool(course: Course, state: SchoolState) -> tuple[str, ...]:
    seen = tuple(g.id for g in course.grades
                 if g.id in state.champions or g.id == state.grade)
    return _caps(course, seen)


def start_new(course: Course, initial_student: Checkpoint) -> SchoolState:
    validate(course)
    return SchoolState(schema="bilqis.mlx.letter-grade/v1",
                       course_digest=course.digest(),
                       active_grades=tuple(g.id for g in course.grades),
                       grade_index=0, stage="MAIN",
                       queue=_caps(course, (course.grades[0].id,)),
                       first_recovery=(), current_student=initial_student,
                       champions={})


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
    if state.visits < 0 or state.school_cycles < 1:
        raise ValueError("INVALID_SCHOOL_COUNTER")
    if state.revalidation_target_grade is not None:
        if (state.revalidation_target_grade not in state.active_grades[1:] or
                state.grade_index > state.active_grades.index(state.revalidation_target_grade) or
                state.stage not in ("MAIN", "ASSESS_MAIN", "RECOVERY_1",
                                    "ASSESS_RECOVERY_1", "RECOVERY_2", "ASSESS_RECOVERY_2") or
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


def weakest_three(scores: dict[str, Score], pool: tuple[str, ...],
                  *, exclude: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Normalized exact-rational ordering; re-rank the remaining pool each round."""
    if len(set(pool)) != len(pool) or not set(pool) <= set(scores):
        raise ValueError("WEAKEST_THREE_INCOMPLETE_POOL")
    ranking = sorted((c for c in pool if c not in exclude),
                     key=lambda c: (scores[c].accuracy, c))
    if len(ranking) < 3:
        raise ValueError("WEAKEST_THREE_NOT_ENOUGH_REMAINING_CAPABILITIES")
    return tuple(ranking[:3])


def _perfect_in_grade(course: Course, grade: str, scores: dict[str, Score]) -> bool:
    return all(scores[c].perfect for c in _caps(course, (grade,)))


def _finish_grade_series(course: Course, state: SchoolState, assessment: Assessment,
                         pointers: dict[str, Checkpoint]) -> SchoolState:
    """Advance to the next grade or stop at a verified course boundary."""
    next_index = state.grade_index + 1
    if next_index < len(state.active_grades):
        next_grade = state.active_grades[next_index]
        return replace(state, grade_index=next_index, queue=_caps(course, (next_grade,)),
                       stage="MAIN", first_recovery=(), champions=pointers,
                       revalidation_target_grade=None,
                       # The newly admitted grade owns the next cumulative seal.
                       latest_rubric_digest=None)
    if not course.program_complete:
        # Passing the last *published* grade cannot silently certify the
        # still-unpublished rest of New Ithkuil. Retain the intact champion
        # and wait for an explicitly versioned next-grade admission.
        return replace(state, queue=(), first_recovery=(), champions=pointers,
                       stage="AWAITING_NEXT_GRADE", pending_failures=(),
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
            return replace(state, grade_index=next_index,
                           queue=_caps(course, (state.active_grades[next_index],)),
                           stage="MAIN", first_recovery=(), champions=pointers)
        failed = tuple(g for g in state.active_grades[:target_index + 1]
                       if not _perfect_in_grade(course, g, assessment.scores))
        if failed:
            if course.program_complete and target == course.grades[-1].id:
                # Preserve the original final-program teacher-soup recovery:
                # only failed grades are revisited in that next school cycle.
                return replace(state, queue=(), first_recovery=(), champions=pointers,
                               stage="AWAITING_TEACHER_SOUP", pending_failures=failed,
                               revalidation_target_grade=None,
                               latest_rubric_digest=assessment.rubric_digest)
            # At a partial-program boundary, do not start C if the final B
            # checkpoint lost A. Repeat the ordered prefix until it sticks.
            return replace(state, grade_index=0, stage="MAIN",
                           queue=_caps(course, (state.active_grades[0],)),
                           first_recovery=(), champions=pointers)
        return _finish_grade_series(course, state, assessment, pointers)

    if state.grade_index > 0 and state.grade not in state.champions:
        # Newly mastered B triggers A->B; C triggers A->B->C, etc.
        # Even a perfect initial cumulative B examination is followed by a
        # fresh ordered revalidation pass before the next grade is entered.
        return replace(state, grade_index=0, stage="MAIN",
                       queue=_caps(course, (state.active_grades[0],)),
                       first_recovery=(), champions=pointers,
                       revalidation_target_grade=state.grade,
                       latest_rubric_digest=assessment.rubric_digest)
    return _finish_grade_series(course, state, assessment, pointers)


def assess(course: Course, state: SchoolState, snapshot: Assessment) -> SchoolState:
    verify_state(course, state)
    if state.stage not in ("ASSESS_MAIN", "ASSESS_RECOVERY_1", "ASSESS_RECOVERY_2"):
        raise ValueError("ASSESSMENT_NOT_SCHEDULED_AT_DURABLE_BOUNDARY")
    pool = _score_pool(course, state)
    snapshot.verify(state.current_student, course, pool)
    if (state.latest_rubric_digest is not None and
            state.latest_rubric_digest != snapshot.rubric_digest):
        raise ValueError("ASSESSMENT_RUBRIC_CHANGED_MID_COURSE")
    if _perfect_in_grade(course, state.grade, snapshot.scores):
        return _promote(course, state, snapshot)
    if state.stage == "ASSESS_MAIN":
        trio = weakest_three(snapshot.scores, pool)
        return replace(state, stage="RECOVERY_1", queue=trio,
                       first_recovery=trio, latest_rubric_digest=snapshot.rubric_digest)
    if state.stage == "ASSESS_RECOVERY_1":
        trio = weakest_three(snapshot.scores, pool, exclude=state.first_recovery)
        return replace(state, stage="RECOVERY_2", queue=trio,
                       latest_rubric_digest=snapshot.rubric_digest)
    return replace(state, stage="MAIN", queue=_caps(course, (state.grade,)),
                   first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)


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
    return replace(state, course_digest=successor.digest(),
                   active_grades=successor_ids,
                   grade_index=len(previous.grades), stage="MAIN",
                   queue=_caps(successor, (added,)), first_recovery=(),
                   revalidation_target_grade=None,
                   latest_rubric_digest=None, pending_failures=(),
                   teacher_soup_digest=None)


def continue_after_soup(course: Course, state: SchoolState,
                        *, frozen_teacher_receipt: str) -> SchoolState:
    """Start a new *grade cycle*. The causal student and AdamW are untouched."""
    verify_state(course, state)
    if state.stage != "AWAITING_TEACHER_SOUP" or not state.pending_failures:
        raise ValueError("TEACHER_SOUP_NOT_DUE")
    if (len(frozen_teacher_receipt) != 64 or
            any(c not in "0123456789abcdef" for c in frozen_teacher_receipt)):
        raise ValueError("TEACHER_SOUP_RECEIPT_MISSING")
    first = state.pending_failures[0]
    return replace(state, active_grades=state.pending_failures, grade_index=0,
                   queue=_caps(course, (first,)), first_recovery=(), stage="MAIN",
                   pending_failures=(), school_cycles=state.school_cycles+1,
                   revalidation_target_grade=None,
                   teacher_soup_digest=frozen_teacher_receipt)


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
