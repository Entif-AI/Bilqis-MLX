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


@dataclass
class _Counts:
    major: int = 0
    success: int = 0
    attempts: int = 0

    def render(self) -> str:
        return f"{self.major}.{self.success}.{self.attempts}"


class GraduationProjection:
    """Count sweep attempts and successful semantic/grade transitions.

    Historical journals predate an explicit promotion-result event, so a
    same-grade MAIN exit is held pending until the next event proves whether
    the introduction stage advanced. A grade change proves a major success.
    """

    def __init__(self):
        self.lifetime = _Counts()
        self.current = _Counts()
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

    def _success(self, *, major: bool, current_epoch: bool) -> None:
        self.lifetime.success += 1
        self.lifetime.major += int(major)
        if current_epoch:
            self.current.success += 1
            self.current.major += int(major)

    def _resolve_pending(self, event: dict) -> None:
        if self._pending is None:
            return
        grade, stage, current_epoch = self._pending
        event_grade = event.get("grade")
        if isinstance(event_grade, str) and event_grade and event_grade > grade:
            self._success(major=True, current_epoch=current_epoch)
            self._pending = None
            return
        if event.get("event") not in _EXAM_EVENTS:
            return
        next_stage = event.get("introduction_stage")
        if type(next_stage) is not int:
            return
        if event_grade == grade and next_stage > stage:
            self._success(major=False, current_epoch=current_epoch)
        self._pending = None

    def observe(self, event: dict) -> str:
        self._resolve_pending(event)
        if event.get("event") not in _EXAM_EVENTS:
            return self.summary()
        grade = event.get("grade")
        stage = event.get("introduction_stage")
        phase = event.get("phase")
        if not isinstance(grade, str) or type(stage) is not int:
            return self.summary()
        if phase == "PROMOTION_SWEEP":
            if self._active is None:
                self._attempt(grade, stage)
            return self.summary()
        if self._active is None:
            return self.summary()
        active_grade, active_stage, current_epoch = self._active
        self._active = None
        if phase in _BOUNDARY_SUCCESS:
            self._success(major=True, current_epoch=current_epoch)
        elif phase not in _DEFINITE_ABORT:
            self._pending = (active_grade, active_stage, current_epoch)
        return self.summary()
