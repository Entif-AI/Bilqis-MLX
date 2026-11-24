"""#1333 BAMF-native MAIN/RECOVERY cadence inside one active generated grade."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.priority_competence import instructional_members

from .active_grade_cadence_contracts import (
    ActiveGradeCadenceAuthorization,
    ActiveGradeCadenceDisposition,
    ActiveGradeCadencePhase,
    CADENCE_POLICY_EPOCH,
    MAX_RECOVERY_ROUNDS,
    _issue_cadence_authorization,
)
from .active_grade_cadence_boundary import _latest_boundary, _persist_boundary
from .active_grade_cadence_custody import read_current_cadence
from .active_grade_cadence_policy import (
    context_matches,
    deficits,
    member_capabilities,
    member_census_digest,
    new_state,
    recovery_members,
)
from .active_grade_cadence_projection import (
    consume_attempt,
    reconcile_terminal_attempts,
    replay_seed,
)


_RECOVERY_PHASES = (
    ActiveGradeCadencePhase.RECOVERY_1,
    ActiveGradeCadencePhase.RECOVERY_2,
)
def _invalid(reason: str):
    ErrorBus.Raise(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


if len(_RECOVERY_PHASES) != MAX_RECOVERY_ROUNDS:
    _invalid("BAMF_ACTIVE_GRADE_CADENCE_POLICY_MISMATCH")


def _terminal_attempts(run_dir: Path, state):
    from .active_grade_cadence_replay import _authenticated_cadence_attempts
    return _authenticated_cadence_attempts(run_dir.resolve(), state)


def _next_phase(state):
    if state.phase is ActiveGradeCadencePhase.MAIN:
        return _RECOVERY_PHASES[0], 1
    if state.phase in _RECOVERY_PHASES:
        index = _RECOVERY_PHASES.index(state.phase) + 1
        if index < len(_RECOVERY_PHASES):
            return _RECOVERY_PHASES[index], index + 1
    return ActiveGradeCadencePhase.BOUNDARY, MAX_RECOVERY_ROUNDS + 1


def _attempt_epoch(attempts) -> int:
    values = [
        record.get("cadence_epoch")
        for record, _capability, _outcome in attempts
        if type(record.get("cadence_epoch")) is int
    ]
    return max(values, default=-1)


def _seed_boundary(run_dir, state, frontier, census, boundary):
    return new_state(
        run_dir, state, frontier,
        phase=ActiveGradeCadencePhase.BOUNDARY,
        phase_round=MAX_RECOVERY_ROUNDS + 1,
        phase_capability_ids=(),
        deficit_evidence_sha256=boundary["deficit_evidence_sha256"],
        member_census_sha256=census,
        recovery_attempt_counts=dict(boundary["recovery_attempt_counts"]),
        recovery_retained_counts=dict(boundary["recovery_retained_counts"]),
        recovery_rejected_counts=dict(boundary["recovery_rejected_counts"]),
        cadence_epoch=boundary["cadence_epoch"],
        phase_sha256=boundary["phase_sha256"],
    )


def _restore_state(run_dir, state, lawful_frontier, member_order, census,
                   deficit_digest, attempts):
    context_changed = state is None or not context_matches(
        state, lawful_frontier, census)
    if context_changed:
        boundary = _latest_boundary(run_dir, lawful_frontier, census)
        seeded = None
        if (boundary is not None
                and boundary["cadence_epoch"] >= _attempt_epoch(attempts)):
            seeded = _seed_boundary(
                run_dir, state, lawful_frontier, census, boundary)
        if seeded is None:
            seeded = replay_seed(
                run_dir, state, lawful_frontier, census, attempts)
        if seeded is not None:
            state = seeded
        else:
            reset_exposure = (
                state is None
                or state.active_grade_activation_sha256
                != lawful_frontier.active_grade_activation_sha256
                or state.policy_epoch != CADENCE_POLICY_EPOCH)
            state = new_state(
                run_dir, state, lawful_frontier,
                phase=ActiveGradeCadencePhase.MAIN, phase_round=0,
                phase_capability_ids=member_order,
                deficit_evidence_sha256=deficit_digest,
                member_census_sha256=census,
                cadence_epoch=max(
                    0 if state is None else state.cadence_epoch + 1,
                    _attempt_epoch(attempts) + 1),
                recovery_attempt_counts=(
                    {} if reset_exposure else dict(state.recovery_attempt_counts)),
                recovery_retained_counts=(
                    {} if reset_exposure else dict(state.recovery_retained_counts)),
                recovery_rejected_counts=(
                    {} if reset_exposure else dict(state.recovery_rejected_counts)),
            )
    state = reconcile_terminal_attempts(run_dir, state, attempts)
    if state.deficit_evidence_sha256 != deficit_digest:
        if state.phase is ActiveGradeCadencePhase.BOUNDARY:
            state = new_state(
                run_dir, state, lawful_frontier,
                phase=ActiveGradeCadencePhase.MAIN,
                phase_round=0,
                phase_capability_ids=member_order,
                deficit_evidence_sha256=deficit_digest,
                member_census_sha256=census,
                cadence_epoch=state.cadence_epoch + 1,
                recovery_attempt_counts={},
                recovery_retained_counts={},
                recovery_rejected_counts={},
            )
        else:
            state = new_state(
                run_dir, state, lawful_frontier,
                phase=state.phase, phase_round=state.phase_round,
                phase_capability_ids=state.phase_capability_ids,
                attempted_capability_ids=state.attempted_capability_ids,
                deficit_evidence_sha256=deficit_digest,
                member_census_sha256=census,
                cadence_epoch=state.cadence_epoch,
                recovery_attempt_counts=dict(state.recovery_attempt_counts),
                recovery_retained_counts=dict(state.recovery_retained_counts),
                recovery_rejected_counts=dict(state.recovery_rejected_counts),
            )
    return state


def _issue_phase(run_dir, state, lawful_frontier, member_order, census,
                 deficit_counts, deficit_digest, competence):
    while True:
        ready_set = set(lawful_frontier.ready_capability_ids)
        ready = tuple(
            capability for capability in member_order if capability in ready_set)
        deferred = ready_set - set(instructional_members(ready, competence))
        complete = {
            item.capability_id for item in lawful_frontier.capabilities
            if getattr(item.disposition, "value", item.disposition)
            == "EVIDENCE_COMPLETE"
        }
        attempted = set(state.attempted_capability_ids)
        unsatisfied = tuple(
            capability for capability in state.phase_capability_ids
            if capability not in attempted and capability not in complete
            and capability not in deferred)
        authorized = tuple(
            capability for capability in unsatisfied if capability in ready_set)
        if authorized:
            return _issue_cadence_authorization(
                state, authorized, ActiveGradeCadenceDisposition.TEACHING)
        active_state = getattr(
            lawful_frontier.active_grade_state, "value",
            lawful_frontier.active_grade_state)
        if active_state in {"COMPLETE", "GLOBAL_FIXED_POINT"}:
            if state.phase is not ActiveGradeCadencePhase.BOUNDARY:
                state = new_state(
                    run_dir, state, lawful_frontier,
                    phase=ActiveGradeCadencePhase.BOUNDARY,
                    phase_round=MAX_RECOVERY_ROUNDS + 1,
                    phase_capability_ids=(),
                    deficit_evidence_sha256=deficit_digest,
                    member_census_sha256=census)
            return _issue_cadence_authorization(
                state, (), ActiveGradeCadenceDisposition.GRADE_COMPLETE)
        if unsatisfied or not ready:
            return _issue_cadence_authorization(
                state, (), ActiveGradeCadenceDisposition.HELD)
        if state.phase is ActiveGradeCadencePhase.BOUNDARY:
            return _issue_cadence_authorization(
                state, (), ActiveGradeCadenceDisposition.RECOVERY_EXHAUSTED)
        phase, phase_round = _next_phase(state)
        members = (() if phase is ActiveGradeCadencePhase.BOUNDARY else
                   recovery_members(state, ready, deficit_counts, member_order,
                                    competence))
        source_state = state
        state = new_state(
            run_dir, state, lawful_frontier,
            phase=phase, phase_round=phase_round,
            phase_capability_ids=members,
            deficit_evidence_sha256=deficit_digest,
            member_census_sha256=census)
        if phase is ActiveGradeCadencePhase.BOUNDARY:
            if source_state.phase is ActiveGradeCadencePhase.RECOVERY_2:
                _persist_boundary(run_dir, state)
            return _issue_cadence_authorization(
                state, (), ActiveGradeCadenceDisposition.RECOVERY_EXHAUSTED)


def issue_active_grade_cadence(run_dir: Path, epoch, lawful_frontier, *, competence=None):
    """Issue the current #1333 subset; #1315 remains the legality owner."""
    run_dir = Path(run_dir)
    member_order = member_capabilities(lawful_frontier)
    census = member_census_digest(lawful_frontier)
    deficit_counts, deficit_digest = deficits(epoch, member_order)
    state = read_current_cadence(run_dir)
    attempts = _terminal_attempts(run_dir, state)
    state = _restore_state(
        run_dir, state, lawful_frontier, member_order, census, deficit_digest, attempts)
    return _issue_phase(
        run_dir, state, lawful_frontier, member_order, census,
        deficit_counts, deficit_digest, competence or {})


def record_active_grade_cadence_attempt(
        run_dir: Path, cadence_record: dict, capability_id: str,
        terminal_outcome: str) -> None:
    """Project one already-authenticated terminal visit into cadence custody."""
    if not isinstance(cadence_record, dict) or not isinstance(capability_id, str):
        _invalid("BAMF_ACTIVE_GRADE_CADENCE_ATTEMPT_INVALID")
    run_dir = Path(run_dir)
    state = read_current_cadence(run_dir)
    attempts = _terminal_attempts(run_dir, state)
    if not any(
            recorded_capability == capability_id
            and record == cadence_record
            and recorded_outcome == terminal_outcome
            for record, recorded_capability, recorded_outcome in attempts):
        _invalid("BAMF_ACTIVE_GRADE_CADENCE_TERMINAL_AUTHORITY_MISSING")
    if state is None:
        _invalid("BAMF_ACTIVE_GRADE_CADENCE_ATTEMPT_DRIFT")
    consume_attempt(
        run_dir, state, cadence_record, capability_id, terminal_outcome)


def rearm_active_grade_acquisition(
        run_dir: Path, authorization: ActiveGradeCadenceAuthorization,
        lawful_frontier):
    """Return a sub-entry certification boundary to ordinary MAIN learning."""
    if type(authorization) is not ActiveGradeCadenceAuthorization:
        _invalid("BAMF_ACTIVE_GRADE_CADENCE_REARM_AUTHORITY_REQUIRED")
    authorization.verify()
    state = authorization.state
    if (
        authorization.disposition is not ActiveGradeCadenceDisposition.RECOVERY_EXHAUSTED
        or state.phase is not ActiveGradeCadencePhase.BOUNDARY
        or authorization.authorized_capability_ids
    ):
        _invalid("BAMF_ACTIVE_GRADE_CADENCE_REARM_AUTHORITY_REQUIRED")
    current = read_current_cadence(Path(run_dir))
    if current is None or current.cadence_sha256 != state.cadence_sha256:
        _invalid("BAMF_ACTIVE_GRADE_CADENCE_REARM_STALE")
    members = member_capabilities(lawful_frontier)
    census = member_census_digest(lawful_frontier)
    if not context_matches(current, lawful_frontier, census):
        _invalid("BAMF_ACTIVE_GRADE_CADENCE_REARM_STALE")
    return new_state(
        Path(run_dir), current, lawful_frontier,
        phase=ActiveGradeCadencePhase.MAIN,
        phase_round=0,
        phase_capability_ids=members,
        deficit_evidence_sha256=current.deficit_evidence_sha256,
        member_census_sha256=census,
        recovery_attempt_counts=dict(current.recovery_attempt_counts),
        recovery_retained_counts=dict(current.recovery_retained_counts),
        recovery_rejected_counts=dict(current.recovery_rejected_counts),
        cadence_epoch=current.cadence_epoch + 1,
    )


__all__ = (
    "issue_active_grade_cadence", "rearm_active_grade_acquisition",
    "record_active_grade_cadence_attempt",
)
