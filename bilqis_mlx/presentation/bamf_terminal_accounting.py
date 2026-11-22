"""Command-local BAMF counters, independent of bounded terminal row history."""
from __future__ import annotations


_ACCEPTED = "BAMF_C16_3_ACCEPTED"
_REJECTED = "BAMF_CANDIDATE_REJECTED"
_STOPPED = "BAMF_RUN_STOPPED"
_COUNTER_FIELDS = ("visits", "retained_visits", "attempted_steps", "retained_steps")


def begin_bamf_command_accounting(board) -> None:
    """Start one operator-command counter epoch."""
    board._bamf_command_accounting = {"active": True, "seen": set()}
    board.state.update(
        visits=0, retained_visits=0, attempted_steps=0, retained_steps=0,
        _rate_sample_eligible=True)


def bamf_command_accounting_active(board) -> bool:
    state = getattr(board, "_bamf_command_accounting", None)
    return isinstance(state, dict) and state.get("active") is True


def _nonnegative_int(value) -> int:
    return value if type(value) is int and value >= 0 else 0


def _terminal_payload(event: dict):
    kind = event.get("event")
    if kind == _ACCEPTED:
        envelope = event
        accepted = True
    elif kind == _REJECTED:
        envelope = event.get("evidence")
        accepted = False
    else:
        return None
    if not isinstance(envelope, dict):
        return None
    how = envelope.get("how_outcome")
    how = how if isinstance(how, dict) else {}
    visit_id = event.get("visit_id") or envelope.get("visit_id")
    event_id = event.get("event_id")
    if isinstance(visit_id, str) and visit_id:
        key = ("visit", visit_id)
    elif isinstance(event_id, str) and event_id:
        key = ("event", event_id)
    else:
        key = (
            "shape", kind, event.get("capability") or envelope.get("capability"),
            event.get("optimizer_step") or envelope.get("candidate_optimizer_step"),
            event.get("candidate_attempt_ordinal")
            or envelope.get("rejection_attempt_ordinal"),
        )
    return key, accepted, _nonnegative_int(how.get("attempted_steps")), _nonnegative_int(
        how.get("retained_steps"))


def _apply_stop_receipt(board, event: dict) -> bool:
    receipt = event.get("run_stop_receipt")
    if not isinstance(receipt, dict):
        return False
    visits = receipt.get("visits")
    accepted = receipt.get("accepted_visits")
    if type(visits) is not int or visits < 0 or type(accepted) is not int or accepted < 0:
        return False
    board.state.update(
        visits=visits, retained_visits=accepted, _rate_sample_eligible=True)
    return True


def ingest_bamf_command_event(board, event: dict) -> bool:
    """Consume one durable BAMF event into command counters exactly once."""
    if not bamf_command_accounting_active(board):
        return False
    if event.get("event") == _STOPPED:
        return _apply_stop_receipt(board, event)
    payload = _terminal_payload(event)
    if payload is None:
        return False
    key, accepted, attempted, retained = payload
    accounting = board._bamf_command_accounting
    seen = accounting["seen"]
    if key in seen:
        return True
    seen.add(key)
    board.state.update(
        visits=_nonnegative_int(board.state.get("visits")) + 1,
        retained_visits=_nonnegative_int(board.state.get("retained_visits"))
        + (1 if accepted else 0),
        attempted_steps=_nonnegative_int(board.state.get("attempted_steps")) + attempted,
        retained_steps=_nonnegative_int(board.state.get("retained_steps")) + retained,
        _rate_sample_eligible=True,
    )
    return True


def transfer_bamf_command_accounting(source, target) -> None:
    """Carry one command epoch across the final dashboard rebuild."""
    accounting = getattr(source, "_bamf_command_accounting", None)
    if not isinstance(accounting, dict) or accounting.get("active") is not True:
        return
    target._bamf_command_accounting = {
        "active": True, "seen": set(accounting.get("seen", ()))}
    for field in _COUNTER_FIELDS:
        if field in source.state:
            target.state[field] = source.state[field]
    target.state["_rate_sample_eligible"] = True
    for field in ("started", "_rate_step", "_rate_time", "_steps_per_min"):
        if hasattr(source, field):
            setattr(target, field, getattr(source, field))


__all__ = (
    "bamf_command_accounting_active", "begin_bamf_command_accounting",
    "ingest_bamf_command_event", "transfer_bamf_command_accounting",
)
