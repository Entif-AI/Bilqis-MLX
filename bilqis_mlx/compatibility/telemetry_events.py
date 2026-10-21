"""Historical telemetry aliases for replaying pre-generic event ledgers."""

from types import MappingProxyType

HISTORICAL_EVENT_KINDS = MappingProxyType({
    "GRADE_A_NEW_RUN_INITIALIZED": "init",
    "GRADE_A_TEACHER_VISIT_COMMITTED": "visit",
    "GRADE_A_EXAM_COMMITTED": "exam",
    "GRADE_A_LIVE_EXAM_COMMITTED": "exam",
    "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED": "visit",
    "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED": "exam",
    "SCHOOL_GRADE_B_COURSE_ADMITTED": "init",
    "GRADE_A_SESSION_STOPPED": "stop",
})

_HISTORICAL_GRADE_A_EVENTS = frozenset(
    event for event in HISTORICAL_EVENT_KINDS
    if event.startswith("GRADE_A_"))
_HISTORICAL_LIVE_EXAMS = frozenset({
    "GRADE_A_LIVE_EXAM_COMMITTED",
    "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
})


def historical_event_grade(event_name: str) -> str | None:
    return "A" if event_name in _HISTORICAL_GRADE_A_EVENTS else None


def historical_live_exam(event_name: str) -> bool:
    return event_name in _HISTORICAL_LIVE_EXAMS
