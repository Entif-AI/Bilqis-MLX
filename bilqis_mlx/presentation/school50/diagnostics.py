from __future__ import annotations

from collections import defaultdict
from .labels import _signal_label

def _candidate_retention_row(event: dict, grade: str, attempt: int) -> dict | None:
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



def _diagnostic_system_rows(event: dict, grade: str) -> tuple[dict, ...]:
    rows = []
    diagnostics = event.get("learning_diagnostics")
    if isinstance(diagnostics, dict):
        warning_labels = [
            f"{_signal_label(warning.get('signal'))}:{warning.get('capability', '?')}"
            for warning in diagnostics.get("active_warnings", ())
            if isinstance(warning, dict)
        ]
        not_measured = sum(
            1 for finding in diagnostics.get("findings", ())
            if isinstance(finding, dict) and finding.get("status") == "NOT_MEASURED")
        unavailable = (
            diagnostics.get("s3_usable") is False
            if "s3_usable" in diagnostics else
            diagnostics.get("history_usable") is False)
        detail = ("active " + ", ".join(warning_labels)
                  if warning_labels else "S3 unavailable" if unavailable else "no active warnings")
        if unavailable and warning_labels:
            detail += " | S3 unavailable"
        rows.append({"kind":"DIAGNOSTIC", "grade":grade,
                     "detail":detail + f" | {not_measured} NOT MEASURED"})
        if unavailable and diagnostics.get("history_issue"):
            rows.append({"kind": "HISTORY ISSUE", "grade": grade,
                         "detail": str(diagnostics["history_issue"])})
        elif diagnostics.get("history_usable") is False and diagnostics.get("history_issue"):
            rows.append({"kind": "HISTORY ISSUE", "grade": grade,
                         "detail": str(diagnostics["history_issue"]) +
                                   " | paired S3 recovered"})
    outcomes = event.get("teacher_outcomes")
    if isinstance(outcomes, list) and outcomes:
        rows.append({"kind":"TEACH OUTCOME", "grade":grade,
                     "detail":_teacher_outcome_text(outcomes)})
    return tuple(rows)



def _teacher_outcome_text(outcomes: list[dict]) -> str:
    measured = _measured_teacher_outcomes(outcomes)
    if measured:
        return "fixed-exam action outcome " + (_measured_outcome_changes(measured) or "measured")
    return _unmeasured_outcome_counts(outcomes)



def _measured_teacher_outcomes(outcomes: list[dict]) -> list[dict]:
    return [item for item in outcomes if isinstance(item, dict) and
            item.get("attribution") == "MEASURED_FIXED_EXAM_UNIQUE_ACTION"]



def _measured_outcome_changes(measured: list[dict]) -> str:
    return ", ".join(
        f"{item.get('capability', '?')} {item.get('delta_correct', 0):+d}"
        for item in measured if type(item.get("delta_correct")) is int)



def _unmeasured_outcome_counts(outcomes: list[dict]) -> str:
    counts = defaultdict(int)
    for item in outcomes:
        if isinstance(item, dict):
            counts[str(item.get("attribution", "UNKNOWN"))] += 1
    return " | ".join(f"{key} x{count}" for key, count in sorted(counts.items()))

# Same six historical panel identities, new-school labels that describe what
# the data actually measures. The old School50 TABLES constant is untouched.
