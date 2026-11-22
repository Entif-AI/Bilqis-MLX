"""Bounded durable + live BAMF evidence for the terminal cockpit."""
from __future__ import annotations

from collections import OrderedDict, deque
import json
from pathlib import Path


MAX_OBSERVATION_BYTES = 64 * 1024
MAX_VISITS = 8
MAX_HISTORY_VISITS = 64
SCHEMAS = frozenset(
    f"bilqis.bamf.trainer-observed/v{version}" for version in range(1, 8))
_DURABLE_EVENTS = frozenset({"BAMF_C16_3_ACCEPTED", "BAMF_CANDIDATE_REJECTED"})


def _measured_target(how: dict, capability: str):
    scores = how.get("scores")
    if not isinstance(scores, list):
        return None
    row = next((item for item in scores
                if isinstance(item, list) and len(item) == 4 and item[0] == capability), None)
    if row is None or not all(type(value) is int for value in row[1:]):
        return None
    before, after, total = row[1:]
    if total <= 0 or not 0 <= before <= total or not 0 <= after <= total:
        return None
    return {"state": "MEASURED", "before": before, "after": after, "total": total}


def _durable_visit(event: dict, run_id: str):
    kind = event.get("event")
    if kind not in _DURABLE_EVENTS:
        return None
    accepted = kind == "BAMF_C16_3_ACCEPTED"
    envelope = event if accepted else event.get("evidence")
    if not isinstance(envelope, dict):
        return None
    how = envelope.get("how_outcome")
    how = how if isinstance(how, dict) else {}
    capability = event.get("capability") or envelope.get("capability")
    if not isinstance(capability, str) or not capability:
        return None
    decision = how.get("decision")
    decision = decision if isinstance(decision, dict) else envelope.get("decision")
    decision = decision if isinstance(decision, dict) else {}
    context = how.get("context")
    context = context if isinstance(context, dict) else {}
    selected_policy = how.get("selected_policy")
    selected_policy = selected_policy if isinstance(selected_policy, dict) else None
    realized_action = how.get("realized_action")
    realized_action = realized_action if isinstance(realized_action, dict) else None
    protected_capabilities = how.get("protected_capabilities")
    protected_capabilities = (
        list(protected_capabilities)
        if isinstance(protected_capabilities, (list, tuple)) else None)
    evaluated_capabilities = decision.get("evaluated_capability_ids")
    evaluated_count = (
        len(evaluated_capabilities)
        if isinstance(evaluated_capabilities, (list, tuple)) else None)
    candidate_step = (
        event.get("optimizer_step") if accepted
        else envelope.get("candidate_optimizer_step"))
    attempt = (
        event.get("candidate_attempt_ordinal") if accepted
        else envelope.get("rejection_attempt_ordinal"))
    visit_id = event.get("visit_id") or envelope.get("visit_id")
    evidence = {
        "state": "COMPLETE",
        "grade_id": context.get("grade") or capability.split(".", 1)[0],
        "capability_id": capability,
        "teacher_policy_key": event.get("selected_policy_key") or envelope.get("selected_policy_key"),
        "selected_option_id": event.get("selected_option_id") or envelope.get("selected_option_id"),
        "decision": "ACCEPTED" if accepted else "REJECT",
        "reason": decision.get("reason") or envelope.get("retention_reason") or "-",
    }
    target = _measured_target(how, capability)
    if target is not None:
        evidence["learning_target"] = target
    return {
        "observation_id": "durable:" + str(event.get("event_id") or visit_id or attempt),
        "revision": 0,
        "run_id": run_id,
        "visit_id": visit_id,
        "visit_index": attempt,
        "capability_id": capability,
        "phase": "COMPLETED",
        "outcome": "ACCEPTED" if accepted else "REJECTED",
        "candidate_optimizer_step": candidate_step,
        "candidate_step": how.get("attempted_steps"),
        "candidate_horizon": how.get("attempted_steps"),
        "retention_completed": evaluated_count,
        "retention_total": evaluated_count,
        "retention_phase": context.get("phase"),
        "retention_decision": decision.get("decision"),
        "selected_policy": selected_policy,
        "realized_action": realized_action,
        "protected_capabilities": protected_capabilities,
        "visit_evidence": evidence,
        "candidate_steps": [],
        "_durable_terminal_history": True,
    }


def _read_durable_history(run_dir: Path, run_id: str):
    path = run_dir / "events.jsonl"
    recent = deque(maxlen=MAX_HISTORY_VISITS)
    try:
        with path.open("rb") as stream:
            for raw in stream:
                if not any(name.encode() in raw for name in _DURABLE_EVENTS):
                    continue
                try:
                    event = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                visit = _durable_visit(event, run_id)
                if visit is not None:
                    recent.append(visit)
    except OSError:
        pass
    return tuple(recent)


def _read_live_observation(run_dir: Path, run_id: str):
    try:
        with (run_dir / "trainer-observed.json").open("rb") as stream:
            raw = stream.read(MAX_OBSERVATION_BYTES + 1)
        if len(raw) > MAX_OBSERVATION_BYTES:
            return ()
        payload = json.loads(raw)
        visits = payload.get("visits")
        if payload.get("schema") not in SCHEMAS or not isinstance(visits, list):
            return ()
    except (OSError, ValueError, TypeError, AttributeError):
        return ()
    return tuple(
        row for row in visits[-MAX_VISITS:]
        if isinstance(row, dict) and row.get("run_id") == run_id)


def _identity(visit: dict):
    visit_id = visit.get("visit_id")
    if isinstance(visit_id, str) and visit_id:
        return ("visit", visit_id)
    return (
        "shape", visit.get("capability_id"), visit.get("candidate_optimizer_step"),
        visit.get("outcome"),
    )


def _overlay_visit(durable: dict, live: dict) -> dict:
    """Overlay disposable live telemetry without erasing richer durable evidence."""
    result = dict(durable)
    for key, value in live.items():
        if value is not None or key not in result:
            result[key] = value
    durable_evidence = durable.get("visit_evidence")
    live_evidence = live.get("visit_evidence")
    if isinstance(durable_evidence, dict) and isinstance(live_evidence, dict):
        evidence = dict(durable_evidence)
        for key, value in live_evidence.items():
            if value is not None or key not in evidence:
                evidence[key] = value
        result["visit_evidence"] = evidence
    return result


def read_bamf_terminal_observation(run_dir: Path):
    """Return durable history overlaid by the newest disposable live observations."""
    try:
        pointer = json.loads((run_dir / "bamf-state.json").read_text())
        run_id = pointer.get("run_id")
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    if not isinstance(run_id, str) or not run_id:
        return None
    combined = OrderedDict()
    for visit in _read_durable_history(run_dir, run_id):
        combined[_identity(visit)] = visit
    for visit in _read_live_observation(run_dir, run_id):
        identity = _identity(visit)
        prior = combined.get(identity)
        combined[identity] = (
            _overlay_visit(prior, visit) if isinstance(prior, dict) else visit)
    return run_id, tuple(combined.values())
