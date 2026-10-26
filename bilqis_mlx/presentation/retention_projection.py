"""Operator-row projection for candidate retention evidence."""
from __future__ import annotations


def candidate_retention_row(event: dict, grade: str, attempt: int) -> dict | None:
    retention = event.get("candidate_retention")
    if not isinstance(retention, dict):
        return None
    capability = retention.get("active_capability") or event.get("capability") or "-"
    before = retention.get("active_probe_before")
    after = retention.get("active_probe_after")
    total = retention.get("active_probe_total")
    target = (f"{before}>{after}/{total}"
              if all(type(value) is int for value in (before, after, total)) and total > 0
              else "-")
    local = retention.get("local_correct_delta")
    protected = retention.get("protected_net_correct_delta")
    worst = retention.get("worst_protected_loss")
    reason = str(retention.get("reason") or "UNKNOWN")
    unsampled = retention.get("unsampled_admitted_capabilities")
    evidence = reason
    if type(unsampled) is int:
        evidence += f" | unsampled {unsampled}"
    frontier_grade = retention.get("protected_frontier_grade")
    frontier_delta = retention.get("protected_frontier_grade_net_correct_delta")
    if isinstance(frontier_grade, str) and type(frontier_delta) is int:
        evidence += f" | frontier {frontier_grade} {frontier_delta:+d}"
    return {
        "grade": grade,
        "capability": capability,
        "attempt": attempt,
        "target": target,
        "target_delta": f"{local:+d}" if type(local) is int else "-",
        "protected": f"{protected:+d}" if type(protected) is int else "-",
        "worst": ("0" if worst == 0 else f"-{worst}"
                  if type(worst) is int and worst > 0 else "-"),
        "decision": str(retention.get("decision") or "UNKNOWN"),
        "result": str(retention.get("decision") or "UNKNOWN"),
        "evidence": evidence,
    }
