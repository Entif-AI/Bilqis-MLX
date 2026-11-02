"""Independent truth oracle for the qualified finite-world rule fixture."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SOURCE

DIRECT_CAUSE_PAIR_WIDTH = 2


def _fail(reason: str) -> None:
    ErrorBus.raise_(SOURCE.BAMF_WORLD.INVALID, reason=reason)


def answer(record: dict) -> str:
    """Evaluate only explicit world facts; never infer transitive causation."""
    events = record.get("events") if isinstance(record, dict) else None
    query = record.get("query") if isinstance(record, dict) else None
    if (not isinstance(record, dict)
            or not isinstance(events, list) or not events
            or not isinstance(query, dict)):
        _fail("WORLD_RULE_RECORD_INVALID")
    by_id = {
        event.get("id"): event for event in events
        if isinstance(event, dict) and isinstance(event.get("id"), str)
    }
    if len(by_id) != len(events):
        _fail("WORLD_RULE_EVENT_INVALID")
    kind = query.get("kind")
    left = query.get("left")
    right = query.get("right")
    if kind == "ACTOR_OF":
        event = by_id.get(left)
        result = event is not None and event.get("actor") == right
    elif kind == "BEFORE":
        a, b = by_id.get(left), by_id.get(right)
        if a is None or b is None:
            _fail("WORLD_RULE_QUERY_EVENT_UNKNOWN")
        result = (
            type(a.get("time")) is int and type(b.get("time")) is int
            and a["time"] < b["time"]
        )
    elif kind == "IS_OCCURRED":
        event = by_id.get(left)
        result = event is not None and event.get("state") == "OCCURRED"
    elif kind == "DIRECT_CAUSE":
        causes = record.get("direct_causes")
        if (not isinstance(causes, list)
                or any(not isinstance(pair, list)
                       or len(pair) != DIRECT_CAUSE_PAIR_WIDTH
                       or any(type(item) is not str for item in pair)
                       for pair in causes)):
            _fail("WORLD_RULE_CAUSE_INVALID")
        result = [left, right] in causes
    else:
        _fail("WORLD_RULE_QUERY_INVALID")
    return "TRUE" if result else "FALSE"
