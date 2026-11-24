"""Paired score evidence used by the terminal, without scoring the model."""
from __future__ import annotations


def _pair(before, after, total):
    if (all(type(value) is int for value in (before, after, total))
            and total > 0 and 0 <= before <= total and 0 <= after <= total):
        return before, after, total
    return None


def paired_scores(visit):
    """Keep the complete durable pair rather than only the taught target."""
    raw = visit.get("paired_scores")
    if not isinstance(raw, (list, tuple)):
        return {}
    result = {}
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) != 4:
            return {}
        capability, before, after, total = row
        pair = _pair(before, after, total)
        if not isinstance(capability, str) or capability in result or pair is None:
            return {}
        result[capability] = pair
    return result


def protected_deltas(visit):
    """Return net change and worst signed loss only for a measured scope."""
    protected = visit.get("protected_capabilities")
    scores = paired_scores(visit)
    if isinstance(protected, (list, tuple)):
        if not all(isinstance(cap, str) for cap in protected):
            return None
        if len(set(protected)) != len(protected):
            return None
        if all(cap in scores for cap in protected):
            deltas = [scores[cap][1] - scores[cap][0] for cap in protected]
            return sum(deltas), min(0, *deltas) if deltas else 0
    evidence = visit.get("visit_evidence")
    rows = evidence.get("protected") if isinstance(evidence, dict) else None
    count = len(protected) if isinstance(protected, (list, tuple)) else visit.get(
        "retention_protected_count")
    if not isinstance(rows, list) or type(count) is not int or len(rows) != count:
        return None
    measured = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("state") != "MEASURED":
            return None
        cap = row.get("capability_id")
        pair = _pair(row.get("before"), row.get("after"), row.get("total"))
        if not isinstance(cap, str) or cap in measured or pair is None:
            return None
        measured[cap] = pair[1] - pair[0]
    if isinstance(protected, (list, tuple)) and set(protected) != set(measured):
        return None
    return sum(measured.values()), min(0, *measured.values()) if measured else 0


def complete_local_pair(visit, owner, scores):
    """Aggregate one measured local scope, not a whole-grade exam."""
    evidence = visit.get("visit_evidence")
    coverage = evidence.get("baseline_coverage") if isinstance(evidence, dict) else None
    groups = coverage.get("group_denominators") if isinstance(coverage, dict) else None
    if not isinstance(groups, list):
        return None
    for group in groups:
        if not isinstance(group, dict) or group.get("group") != owner:
            continue
        total = group.get("total")
        if type(total) is int and total == group.get("measured") == len(scores) and total > 0:
            return tuple(sum(pair[i] for pair in scores.values()) for i in range(3))
    return None
