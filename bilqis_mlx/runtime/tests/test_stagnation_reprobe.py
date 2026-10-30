from dataclasses import dataclass

from bilqis_mlx.learning.stagnation_control import start_session
from bilqis_mlx.runtime.reconciliation import _advance_stagnation_after_routine


@dataclass(frozen=True)
class _School:
    stage: str
    grade: str
    queue: tuple[str, ...] = ()
    first_recovery: tuple[str, ...] = ()


def test_due_quarantine_is_injected_into_next_recovery_cycle():
    control = start_session(
        session_id="fixture", generation=1,
        required_capabilities=("C.ADD", "C.SUB"))
    control["cycle_index"] = 21
    control["quarantined"] = {
        "C.SUB": {
            "capability": "C.SUB",
            "cycle_index": 20,
            "reason": "fixture",
        },
    }
    control["alerts"] = [{
        "capability": "C.SUB",
        "delivery": "END_OF_RUN_REVIEW",
        "action": "WITHHELD_UNTIL_BOUNDED_REPROBE",
        "reason": "fixture",
        "trigger_generation": 1,
        "required_mastery_debt": True,
    }]
    school = _School(stage="ASSESS_MAIN", grade="C")
    advanced = _School(
        stage="RECOVERY_1", grade="C",
        queue=("C.ADD",), first_recovery=("C.ADD",))

    updated, events, next_school, blocked = _advance_stagnation_after_routine(
        program=None, school=school, routine_assessment=None,
        routine_advanced=advanced, stagnation=control,
        blocked_before=("C.SUB",), active_scope=("C.ADD",),
        routine_measured={"scores": {}}, routine_warnings={}, generation=12)

    assert next_school.queue[0] == "C.SUB"
    assert next_school.first_recovery[0] == "C.SUB"
    assert blocked == ()
    assert updated["rehabilitation"]["mode"] == "BOUNDED_REPROBE"
    assert any(event["event"] == "SCHOOL_STAGNATION_BOUNDED_REPROBE_STARTED"
               for event in events)
