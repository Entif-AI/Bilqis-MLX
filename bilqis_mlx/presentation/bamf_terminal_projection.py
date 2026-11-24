"""Refresh the terminal cockpit from disposable BAMF trainer observations."""
from __future__ import annotations

from pathlib import Path

from .bamf_terminal_rows import (
    MARKER, candidate_row, grade, mastery_rows, retention_row, system_rows,
    teacher_row,
)
from .bamf_terminal_accounting import bamf_command_accounting_active
from .bamf_reference_growth import ReferenceGrowth
from .bamf_terminal_source import (
    logical_visit_identity, read_bamf_terminal_observation,
)


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



def _attempted_steps(visit) -> int:
    outcome = visit.get("outcome")
    value = (
        visit.get("candidate_step") if outcome == "RUNNING"
        else visit.get("candidate_horizon")
    )
    return value if type(value) is int and value >= 0 else 0


def _update_session_state(board, session_visits, terminal_visits) -> None:
    if bamf_command_accounting_active(board):
        accounting = board._bamf_command_accounting
        running_steps = sum(
            _attempted_steps(visit) for visit in session_visits
            if visit.get("outcome") == "RUNNING")
        board.state.update(
            visits=accounting["visits"],
            retained_visits=accounting["retained_visits"],
            attempted_steps=accounting["attempted_steps"] + running_steps,
            retained_steps=accounting["retained_steps"],
            _rate_sample_eligible=True,
        )
        return
    board.state.update(
        visits=len(terminal_visits),
        retained_visits=sum(
            visit.get("outcome") == "ACCEPTED" for visit in terminal_visits),
        attempted_steps=sum(_attempted_steps(visit) for visit in session_visits),
        _rate_sample_eligible=True,
    )


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
    prior_run = getattr(board, "_bamf_terminal_observed_run_id", None)
    if prior_run != run_id:
        if prior_run is not None:
            board._bamf_reference_growth = ReferenceGrowth()
            board._bamf_terminal_projection_token = None
        board._bamf_terminal_observed_history = {}
        board._bamf_terminal_observed_run_id = run_id
        board._bamf_session_visit_baseline = None
    growth = getattr(board, "_bamf_reference_growth", None)
    if growth is None:
        growth = board._bamf_reference_growth = ReferenceGrowth()
    if not visits:
        if getattr(board, "_bamf_session_visit_baseline", None) is None:
            board._bamf_session_visit_baseline = set()
        return
    token = tuple(
        (logical_visit_identity(visit), visit.get("revision"), visit.get("outcome"))
        for visit in visits)
    if token == getattr(board, "_bamf_terminal_projection_token", None):
        return
    current = visits[-1]
    history = getattr(board, "_bamf_terminal_observed_history", {})
    for visit in visits:
        identity = logical_visit_identity(visit)
        observation_id = visit.get("observation_id")
        if identity[0] == "visit" and isinstance(observation_id, str):
            history.pop(("observation", observation_id), None)
            history.pop(observation_id, None)
        history[identity] = visit
    limit = board.rows["CANDIDATES"].maxlen or 512
    while len(history) > limit:
        history.pop(next(iter(history)))
    projected_visits = tuple(history.values())
    identities = {logical_visit_identity(visit) for visit in projected_visits}
    baseline = getattr(board, "_bamf_session_visit_baseline", None)
    if baseline is None:
        baseline = set(identities)
        board._bamf_session_visit_baseline = baseline
        growth.prime(projected_visits)
    session_visits = tuple(
        visit for visit in projected_visits
        if logical_visit_identity(visit) not in baseline)
    terminal_visits = tuple(
        visit for visit in session_visits
        if visit.get("outcome") in {"ACCEPTED", "REJECTED"})
    _update_session_state(board, session_visits, terminal_visits)
    _clear_owned(board)
    board.rows["CANDIDATES"].extend(
        candidate_row(visit) for visit in projected_visits)
    board.rows["SENTINEL & RETENTION"].extend(
        retention_row(visit) for visit in projected_visits)
    teacher_history = {}
    board.rows["SOUP & TEACHER"].extend(
        teacher_row(visit, teacher_history) for visit in projected_visits)
    summaries, families = mastery_rows(projected_visits)
    for visit in terminal_visits:
        growth.observe(visit)
    growth.apply_rows(summaries, families)
    growth.publish(board)
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
