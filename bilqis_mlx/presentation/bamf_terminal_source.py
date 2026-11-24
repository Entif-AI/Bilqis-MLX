"""Bounded durable + live BAMF evidence for the terminal cockpit."""
from __future__ import annotations

from collections import OrderedDict, deque
import json
from pathlib import Path
import threading


MAX_OBSERVATION_BYTES = 64 * 1024
MAX_VISITS = 8
MAX_HISTORY_VISITS = 64
SCHEMAS = frozenset(
    f"bilqis.bamf.trainer-observed/v{version}" for version in range(1, 8))
_DURABLE_EVENTS = frozenset({"BAMF_C16_3_ACCEPTED", "BAMF_CANDIDATE_REJECTED"})
_DURABLE_EVENT_MARKERS = tuple(name.encode() for name in _DURABLE_EVENTS)


class _DurableHistoryCache:
    def __init__(self):
        self.entries = dict()
        self.lock = threading.Lock()

    def clear(self):
        with self.lock:
            self.entries.clear()


_DURABLE_HISTORY = _DurableHistoryCache()


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


def _event_resource(event: dict, envelope: dict, accepted: bool) -> dict:
    value = event.get("resource") if accepted else envelope.get("resource")
    return value if isinstance(value, dict) else {}


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
    resource = _event_resource(event, envelope, accepted)
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
        "baseline_coverage": decision.get("baseline_coverage"),
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
        "loss_total": resource.get("loss_total"),
        "selected_policy": selected_policy,
        "realized_action": realized_action,
        "teacher_selection_reason": envelope.get("teacher_selection_reason"),
        "teacher_selection_policy": envelope.get("teacher_selection_policy"),
        "teacher_policy_evidence_before": envelope.get("teacher_policy_evidence_before"),
        "vnext_canary": envelope.get("vnext_canary"),
        "actual_authority_changed": envelope.get("actual_authority_changed"),
        "protected_capabilities": protected_capabilities,
        "paired_scores": how.get("scores"),
        "visit_evidence": evidence,
        "candidate_steps": [],
        "_durable_terminal_history": True,
    }


def _scan_durable_append(path: Path, run_id: str, offset: int, recent):
    """Consume only complete newly appended JSONL records from ``offset``."""
    next_offset = offset
    try:
        with path.open("rb") as stream:
            stream.seek(offset)
            while True:
                start = stream.tell()
                raw = stream.readline()
                if not raw:
                    next_offset = stream.tell()
                    break
                if not raw.endswith(b"\n"):
                    # The trainer may be between write() calls.  Re-read this
                    # record after the next append instead of permanently
                    # skipping a temporarily incomplete event.
                    next_offset = start
                    break
                next_offset = stream.tell()
                if not any(marker in raw for marker in _DURABLE_EVENT_MARKERS):
                    continue
                try:
                    event = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                visit = _durable_visit(event, run_id)
                if visit is not None:
                    recent.append(visit)
    except OSError:
        return offset
    return next_offset


def _read_durable_history(run_dir: Path, run_id: str):
    """Incrementally tail the append-only event log instead of rescanning it."""
    path = run_dir / "events.jsonl"
    key = (str(path), run_id)
    try:
        stat = path.stat()
    except OSError:
        with _DURABLE_HISTORY.lock:
            _DURABLE_HISTORY.entries.pop(key, None)
        return ()
    identity = (stat.st_dev, stat.st_ino)
    with _DURABLE_HISTORY.lock:
        cached = _DURABLE_HISTORY.entries.get(key)
        reset = (
            not isinstance(cached, dict)
            or cached.get("identity") != identity
            or stat.st_size < cached.get("observed_size", 0)
            or (
                stat.st_size == cached.get("observed_size")
                and stat.st_mtime_ns != cached.get("mtime_ns")
            )
        )
        if reset:
            recent = deque(maxlen=MAX_HISTORY_VISITS)
            offset = 0
        else:
            recent = cached["recent"]
            offset = cached["offset"]
            if (stat.st_size == cached["observed_size"]
                    and stat.st_mtime_ns == cached["mtime_ns"]
                    and cached["offset"] == stat.st_size):
                return tuple(recent)
        offset = _scan_durable_append(path, run_id, offset, recent)
        try:
            observed = path.stat()
        except OSError:
            observed = stat
        _DURABLE_HISTORY.entries[key] = {
            "identity": identity,
            "offset": offset,
            "observed_size": observed.st_size,
            "mtime_ns": observed.st_mtime_ns,
            "recent": recent,
        }
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


def logical_visit_identity(visit: dict):
    """Stable logical identity across live and durable representations."""
    visit_id = visit.get("visit_id")
    if isinstance(visit_id, str) and visit_id:
        return ("visit", visit_id)
    observation_id = visit.get("observation_id")
    if isinstance(observation_id, str) and observation_id:
        return ("observation", observation_id)
    return (
        "shape", visit.get("capability_id"), visit.get("candidate_optimizer_step"),
        visit.get("visit_index"),
    )


def _teacher_policy_key(visit: dict):
    evidence = visit.get("visit_evidence")
    if isinstance(evidence, dict):
        value = evidence.get("teacher_policy_key")
        if isinstance(value, str) and value:
            return value
    selected = visit.get("selected_policy")
    if isinstance(selected, dict):
        value = selected.get("policy_key")
        if isinstance(value, str) and value:
            return value
    return None


def _legacy_match_key(visit: dict):
    capability = visit.get("capability_id")
    step = visit.get("candidate_optimizer_step")
    if not isinstance(capability, str) or type(step) is not int:
        return None
    return capability, step, _teacher_policy_key(visit)


def _only(values):
    """Return the sole value, or None when cardinality is zero or plural."""
    iterator = iter(values)
    try:
        value = next(iterator)
    except StopIteration:
        return None
    try:
        next(iterator)
    except StopIteration:
        return value
    return None


def _legacy_durable_match(live: dict, durable_by_key: dict):
    """Match a pre-visit-id live row only when the durable candidate is unique."""
    key = _legacy_match_key(live)
    if key is None:
        return None
    capability, optimizer_step, policy_key = key
    exact = durable_by_key.get(key, ())
    unique = _only(exact)
    if unique is not None:
        return unique
    if policy_key is not None:
        return None
    broad = []
    for candidate_key, visits in durable_by_key.items():
        candidate_capability, candidate_step, _candidate_policy = candidate_key
        if candidate_capability == capability and candidate_step == optimizer_step:
            broad.extend(visits)
    return _only(broad)


def _overlay_visit(durable: dict, live: dict) -> dict:
    """Overlay telemetry while terminal durable identity/outcome stays authoritative."""
    result = dict(durable)
    terminal_fields = {"visit_id", "phase", "outcome"}
    for key, value in live.items():
        if key in terminal_fields:
            continue
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
    durable = _read_durable_history(run_dir, run_id)
    durable_by_key = {}
    for visit in durable:
        combined[logical_visit_identity(visit)] = visit
        key = _legacy_match_key(visit)
        if key is not None:
            durable_by_key.setdefault(key, []).append(visit)
    for live in _read_live_observation(run_dir, run_id):
        identity = logical_visit_identity(live)
        prior = combined.get(identity)
        if not isinstance(prior, dict) and not live.get("visit_id"):
            matched = _legacy_durable_match(live, durable_by_key)
            if matched is not None:
                durable_identity = logical_visit_identity(matched)
                prior = combined.pop(durable_identity, matched)
                identity = durable_identity
        combined[identity] = (
            _overlay_visit(prior, live) if isinstance(prior, dict) else live)
    return run_id, tuple(combined.values())


__all__ = ("logical_visit_identity", "read_bamf_terminal_observation")
