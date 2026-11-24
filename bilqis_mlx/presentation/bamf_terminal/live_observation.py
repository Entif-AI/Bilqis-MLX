"""Read and reconcile bounded live observations with durable activity."""
from __future__ import annotations

from collections import OrderedDict
import json
from pathlib import Path

MAX_OBSERVATION_BYTES = 64 * 1024
MAX_VISITS = 8
SCHEMAS = frozenset(
    f"bilqis.bamf.trainer-observed/v{version}" for version in range(1, 8))


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


def merge_live_observation(run_dir, run_id, durable):
    combined = OrderedDict()
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
    return tuple(combined.values())
