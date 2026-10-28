"""Read-only integer-root scope presentation helpers."""
from __future__ import annotations


PROFILE_ADOPTION_EVENTS = frozenset({
    "SCHOOL_EXECUTION_PROFILE_ADOPTED",
    "SCHOOL_SEMANTIC_CATALOG_PROFILE_ADOPTED",
})


def integer_root_scope(maximum) -> str:
    if type(maximum) is not int or maximum < 0:
        return "-"
    return f"0...{maximum}" if maximum else "0"


def apply_profile_adoption(telemetry, grade, event) -> None:
    telemetry._reset_score_era(reason=event["event"], grade=grade)
    maximum = event.get("numeric_maximum")
    if maximum is not None and (type(maximum) is not int or maximum < 0):
        raise ValueError("SCHOOL_TELEMETRY_CURRICULUM_REPLACEMENT_INVALID")
    if maximum is not None:
        telemetry.board.state["numeric_maximum"] = maximum
    telemetry.board.state["step"] = event.get(
        "optimizer_step", telemetry.board.state.get("step"))
    telemetry.board.push("system", {
        "kind": "CURRICULUM", "grade": grade,
        "detail": "Active profile " + str(event.get("profile_id") or "-") +
                  (" | integer roots " + integer_root_scope(maximum)
                   if maximum is not None else ""),
    }, redraw=False)
