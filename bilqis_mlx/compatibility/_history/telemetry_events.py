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


def historical_event_kind(event_name: str) -> str | None:
    return HISTORICAL_EVENT_KINDS.get(event_name)


def historical_live_exam(event_name: str) -> bool:
    return event_name in _HISTORICAL_LIVE_EXAMS


def historical_course_admission(event_name: str) -> bool:
    return event_name == "SCHOOL_GRADE_B_COURSE_ADMITTED"


def historical_capability_grade(name: str, event_grade: str) -> str:
    prefix = name.split(".", 1)[0]
    return prefix if len(prefix) == 1 and prefix.isalpha() else event_grade


def historical_withheld_inventory_change_explains(
        event: dict, grade: str, previous, current) -> bool:
    withheld = {
        cap for cap in event.get("withheld_capabilities", ())
        if isinstance(cap, str) and historical_capability_grade(cap, grade) == grade
    }
    if not withheld:
        return False
    before, after = dict(previous), dict(current)
    changed = set(before) ^ set(after)
    return (bool(changed) and changed <= withheld and
            all(before[cap] == after[cap] for cap in set(before) & set(after)))
