"""Refresh the terminal cockpit from disposable BAMF trainer observations."""
from __future__ import annotations

from pathlib import Path

from .bamf_terminal_rows import (
    MARKER, candidate_row, grade, mastery_rows, retention_row, system_rows,
    teacher_row,
)
from .bamf_terminal_source import read_bamf_terminal_observation


OWNED_TABLES = (
    "CANDIDATES", "SENTINEL & RETENTION", "SOUP & TEACHER",
    "BRIDGE FAMILIES", "GRADES & MASTERY", "SYSTEM & QUALIFICATION",
)


def _clear_owned(board):
    for name in OWNED_TABLES:
        rows = board.rows.get(name)
        if rows is None:
            continue
        retained = [row for row in rows if row.get(MARKER) is not True]
        rows.clear()
        rows.extend(retained)


def _visit_identity(visit):
    visit_id = visit.get("visit_id")
    if isinstance(visit_id, str) and visit_id:
        return ("visit", visit_id)
    observation_id = visit.get("observation_id")
    if isinstance(observation_id, str) and observation_id:
        return ("observation", observation_id)
    return (
        "shape", visit.get("capability_id"),
        visit.get("candidate_optimizer_step"), visit.get("outcome"),
    )


def _attempted_steps(visit) -> int:
    outcome = visit.get("outcome")
    value = (
        visit.get("candidate_step") if outcome == "RUNNING"
        else visit.get("candidate_horizon")
    )
    return value if type(value) is int and value >= 0 else 0


def refresh_bamf_terminal_projection(board) -> None:
    """Update display-only rows; malformed input preserves the last good view."""
    hint = getattr(board, "log_hint", "")
    if not hint:
        return
    run_dir = Path(hint).parent
    if not (run_dir / "bamf-state.json").exists():
        return
    loaded = read_bamf_terminal_observation(run_dir)
    if loaded is None:
        return
    run_id, visits = loaded
    if not visits:
        return
    token = tuple(
        (visit.get("observation_id"), visit.get("revision"), visit.get("outcome"))
        for visit in visits)
    if token == getattr(board, "_bamf_terminal_projection_token", None):
        return
    current = visits[-1]
    if getattr(board, "_bamf_terminal_observed_run_id", None) != run_id:
        board._bamf_terminal_observed_history = {}
        board._bamf_terminal_observed_run_id = run_id
    history = getattr(board, "_bamf_terminal_observed_history", {})
    for visit in visits:
        identity = visit.get("observation_id")
        if not isinstance(identity, str) or not identity:
            continue
        history[identity] = visit
    limit = board.rows["CANDIDATES"].maxlen or 512
    while len(history) > limit:
        history.pop(next(iter(history)))
    projected_visits = tuple(history.values())
    identities = {_visit_identity(visit) for visit in projected_visits}
    baseline = getattr(board, "_bamf_session_visit_baseline", None)
    if baseline is None:
        baseline = set(identities)
        board._bamf_session_visit_baseline = baseline
    session_visits = tuple(
        visit for visit in projected_visits
        if _visit_identity(visit) not in baseline)
    terminal_visits = tuple(
        visit for visit in session_visits
        if visit.get("outcome") in {"ACCEPTED", "REJECTED"})
    board.state.update(
        visits=len(terminal_visits),
        retained_visits=sum(
            visit.get("outcome") == "ACCEPTED" for visit in terminal_visits),
        attempted_steps=sum(_attempted_steps(visit) for visit in session_visits),
        _rate_sample_eligible=True,
    )
    _clear_owned(board)
    board.rows["CANDIDATES"].extend(
        candidate_row(visit) for visit in projected_visits)
    board.rows["SENTINEL & RETENTION"].extend(
        retention_row(visit) for visit in projected_visits)
    teacher_history = {}
    board.rows["SOUP & TEACHER"].extend(
        teacher_row(visit, teacher_history) for visit in projected_visits)
    summaries, families = mastery_rows(projected_visits)
    board.rows["GRADES & MASTERY"].extend(summaries)
    board.rows["BRIDGE FAMILIES"].extend(families)
    board.rows["SYSTEM & QUALIFICATION"].extend(
        system_rows(current, projected_visits))
    board.state.update(
        phase=current.get("phase") or board.state.get("phase"),
        prefix=grade(current),
        step=current.get("candidate_optimizer_step") or board.state.get("step"),
    )
    board._bamf_terminal_projection_token = token
