"""Read-only promotion-sweep attempt/success projection for dashboard history."""
from __future__ import annotations

from dataclasses import dataclass


_EXAM_EVENTS = frozenset({
    "SCHOOL_EXAM_COMMITTED",
    "SCHOOL_LIVE_EXAM_COMMITTED",
    "SCHOOL_FLASH_ROUTINE_EXAM_COMMITTED",
})
_BOUNDARY_SUCCESS = frozenset({
    "AWAITING_NEXT_GRADE",
    "AWAITING_NEXT_GRADE_WITH_DEBT",
})
_DEFINITE_ABORT = frozenset({"RECOVERY_1", "RECOVERY_2"})
_GRADE_REACH_EVENTS = frozenset({
    "SCHOOL_NEW_RUN_INITIALIZED",
    "SCHOOL_RUN_INITIALIZED",
    "SCHOOL_COURSE_ADMITTED",
    "SCHOOL_NEXT_GRADE_COURSE_ADMITTED",
    "SCHOOL_EXECUTION_PROFILE_ADOPTED",
    "SCHOOL_SEMANTIC_CATALOG_PROFILE_ADOPTED",
})
_GRADE_ADMISSION_EVENTS = frozenset({
    "SCHOOL_COURSE_ADMITTED",
    "SCHOOL_NEXT_GRADE_COURSE_ADMITTED",
    "SCHOOL_SEMANTIC_CATALOG_PROFILE_ADOPTED",
    "SCHOOL_GRADE_B_COURSE_ADMITTED",
})


@dataclass
class _Counts:
    grade_successes: int = 0
    successes: int = 0
    attempts: int = 0

    def render(self) -> str:
        return f"{self.grade_successes}.{self.successes}.{self.attempts}"


class GraduationProjection:
    """Project ``letter graduations.unique graduations.sweep attempts``.

    Historical journals predate an explicit promotion-result event, so a
    same-grade MAIN exit is held pending until the next event proves whether
    the introduction stage advanced. The starting grade is not a graduation,
    and an already-crossed grade/stage frontier can never graduate twice.

    ``current / lifetime`` means the current human execution command versus
    the complete model journal across all commands/runs in this lineage.
    """

    def __init__(self):
        self.lifetime = _Counts()
        self.current = _Counts()
        self._grades_reached = set()
        self._successful_frontiers = set()
        self._active = None
        self._pending = None
        self._current_epoch = False

    def begin_execution(self) -> str:
        self.current = _Counts()
        self._current_epoch = True
        return self.summary()

    def summary(self) -> str:
        return f"{self.current.render()} / {self.lifetime.render()}"

    def _attempt(self, grade: str, stage: int) -> None:
        self.lifetime.attempts += 1
        if self._current_epoch:
            self.current.attempts += 1
        self._active = (grade, stage, self._current_epoch)

    def _success(self, grade: str, stage: int, *, current_epoch: bool) -> None:
        frontier = (grade, stage)
        if frontier in self._successful_frontiers:
            return
        self._successful_frontiers.add(frontier)
        self.lifetime.successes += 1
        if current_epoch:
            self.current.successes += 1

    def _grade_reached(self, grade: object, *, current: bool) -> None:
        if not isinstance(grade, str) or not grade or grade in self._grades_reached:
            return
        self._grades_reached.add(grade)
        self.lifetime.grade_successes = len(self._grades_reached)
        if current and self._current_epoch:
            self.current.grade_successes += 1

    @staticmethod
    def _is_grade_admission(event: dict) -> bool:
        name = event.get("event")
        if name == "SCHOOL_EXECUTION_PROFILE_ADOPTED":
            return event.get("transition_kind") == "APPEND_GRADE"
        return name in _GRADE_ADMISSION_EVENTS

    def _resolve_pending(self, event: dict) -> None:
        if self._pending is None:
            return
        grade, stage, current_epoch = self._pending
        event_grade = event.get("grade")
        if (isinstance(event_grade, str) and event_grade and event_grade > grade and
                event_grade not in self._grades_reached and
                self._is_grade_admission(event)):
            self._success(grade, stage, current_epoch=current_epoch)
            self._grade_reached(event_grade, current=current_epoch)
            self._pending = None
            return
        if event.get("event") not in _EXAM_EVENTS:
            return
        next_stage = event.get("introduction_stage")
        if type(next_stage) is not int:
            return
        if event_grade == grade and next_stage > stage:
            self._success(grade, stage, current_epoch=current_epoch)
        self._pending = None

    def observe(self, event: dict) -> str:
        self._resolve_pending(event)
        if event.get("event") in _GRADE_REACH_EVENTS:
            self._grade_reached(event.get("grade"), current=self._current_epoch)
        if event.get("event") not in _EXAM_EVENTS:
            return self.summary()
        grade = event.get("grade")
        stage = event.get("introduction_stage")
        phase = event.get("phase")
        if not isinstance(grade, str) or type(stage) is not int:
            return self.summary()
        # Exam history proves the model has reached this grade, but not that
        # the grade was newly promoted during the current execution command.
        self._grade_reached(grade, current=False)
        if phase == "PROMOTION_SWEEP":
            if self._active is None:
                self._attempt(grade, stage)
            return self.summary()
        if self._active is None:
            return self.summary()
        active_grade, active_stage, current_epoch = self._active
        self._active = None
        if phase in _BOUNDARY_SUCCESS:
            self._success(active_grade, active_stage, current_epoch=current_epoch)
        elif phase not in _DEFINITE_ABORT:
            self._pending = (active_grade, active_stage, current_epoch)
        return self.summary()
