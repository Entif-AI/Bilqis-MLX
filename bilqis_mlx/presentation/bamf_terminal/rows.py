"""Truth-preserving table rows for the BAMF terminal cockpit."""
from __future__ import annotations

from bilqis_mlx.presentation.school50.formatting import _display, _scaled_lr, _whole
from bilqis_mlx.presentation.teacher_vnext import teacher_fields
from .scores import complete_local_pair, paired_scores, protected_deltas


MARKER = "_bamf_terminal_observed"
NOT_MEASURED = "N/M"
PENDING = "PEND"


def number(value):
    return value if type(value) in (int, float) else None


def seconds(value):
    value = number(value)
    return NOT_MEASURED if value is None or value < 0 else f"{value:.1f}s"


def gib(value):
    value = number(value)
    return "-" if value is None or value < 0 else f"{value / 1024 ** 3:.1f} GiB"


def score(visit):
    evidence = visit.get("visit_evidence")
    target = evidence.get("learning_target") if isinstance(evidence, dict) else None
    if not isinstance(target, dict) or target.get("state") != "MEASURED":
        target = evidence.get("target") if isinstance(evidence, dict) else None
    if not isinstance(target, dict) or target.get("state") != "MEASURED":
        target = visit.get("retention_target")
    if not isinstance(target, dict) or target.get("state") != "MEASURED":
        return None
    before, after, total = (
        target.get("before"), target.get("after"), target.get("total"))
    if not all(type(value) is int for value in (before, after, total)):
        return None
    if total <= 0 or not 0 <= before <= total or not 0 <= after <= total:
        return None
    return before, after, total


def grade(visit):
    evidence = visit.get("visit_evidence")
    value = evidence.get("grade_id") if isinstance(evidence, dict) else None
    if isinstance(value, str) and value:
        return value
    capability = visit.get("capability_id")
    if isinstance(capability, str) and "." in capability:
        return capability.split(".", 1)[0]
    return "-"


def policy(visit):
    evidence = visit.get("visit_evidence")
    value = evidence.get("teacher_policy_key") if isinstance(evidence, dict) else None
    if not value:
        value = visit.get("selected_policy_key")
    return str(value)[:10] if value else "-"


def selected_policy(visit):
    value = visit.get("selected_policy")
    return value if isinstance(value, dict) else {}


def reason(visit):
    evidence = visit.get("visit_evidence")
    if isinstance(evidence, dict):
        value = evidence.get("human_reason") or evidence.get("reason")
        if value:
            return str(value)
    return str(visit.get("retention_reason") or "-")


def warnings(visit):
    health = visit.get("learning_health")
    if not isinstance(health, dict):
        return NOT_MEASURED
    active = [
        str(item.get("signal"))
        for item in health.get("warnings", ())
        if isinstance(item, dict) and
        str(item.get("status", "")).startswith("OBSERVED")
    ]
    return ",".join(active) if active else "NONE"


def health(visit):
    value = visit.get("learning_health")
    if not isinstance(value, dict):
        return NOT_MEASURED
    return str(value.get("qualification_state") or value.get("state") or "-")


def latest_step_number(visit, field):
    steps = visit.get("candidate_steps")
    if not isinstance(steps, list):
        return None
    for step in reversed(steps):
        if isinstance(step, dict):
            value = number(step.get(field))
            if value is not None:
                return value
    return None


def candidate_row(visit):
    measured = score(visit)
    strategy = selected_policy(visit)
    score_line = (
        f"{measured[0]}/-/{measured[1]}/{measured[2]}"
        if measured is not None else
        PENDING if visit.get("retention_decision") is None else NOT_MEASURED)
    loss = (
        number(visit.get("loss_total"))
        if number(visit.get("loss_total")) is not None
        else latest_step_number(visit, "loss_total"))
    return {
        MARKER: True, "grade": grade(visit),
        "capability": visit.get("capability_id") or "-",
        "attempt": visit.get("visit_index", "-"), "strategy": policy(visit),
        "lr": _scaled_lr(strategy.get("lr")),
        "score_line": score_line, "reward": NOT_MEASURED,
        "loss": _display(loss) if loss is not None else NOT_MEASURED,
        "gradient": NOT_MEASURED, "method": "BAMF", "old": _whole(strategy.get("old")),
        "result": str(visit.get("outcome") or "-"),
        "reason": reason(visit), "warnings": warnings(visit),
    }


def retention_row(visit):
    measured = score(visit)
    evidence = visit.get("visit_evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    target = (
        f"{measured[0]}>{measured[1]}/{measured[2]}"
        if measured is not None else
        PENDING if visit.get("retention_decision") is None else NOT_MEASURED)
    delta = measured[1] - measured[0] if measured is not None else None
    decision = str(
        evidence.get("decision")
        or visit.get("retention_decision")
        or visit.get("outcome")
        or "-"
    )
    completed, total = visit.get("retention_completed"), visit.get("retention_total")
    progress = (
        f"{completed}/{total}" if type(completed) is int and type(total) is int
        else "-")
    protected_capabilities = visit.get("protected_capabilities")
    protected_count = (
        str(len(protected_capabilities))
        if isinstance(protected_capabilities, (list, tuple)) else
        str(visit.get("retention_protected_count"))
        if type(visit.get("retention_protected_count")) is int else
        str(evidence.get("protected_scope_state") or "-")[:3].upper())
    deltas = protected_deltas(visit)
    return {
        MARKER: True, "grade": grade(visit),
        "capability": visit.get("capability_id") or "-",
        "attempt": visit.get("visit_index", "-"), "target": target,
        "target_delta": (
            f"{delta:+d}" if type(delta) is int else
            PENDING if visit.get("retention_decision") is None else NOT_MEASURED),
        "protected": f"{deltas[0]:+d}" if deltas is not None and deltas[0] else
        "0" if deltas is not None else NOT_MEASURED,
        "worst": str(deltas[1]) if deltas is not None else NOT_MEASURED,
        "decision": decision, "result": decision,
        "evidence": f"{progress} | protected n={protected_count} | {reason(visit)}",
    }


def teacher_row(visit, history=None):
    strategy = selected_policy(visit)
    retention_decision = visit.get("retention_decision")
    retention_phase = visit.get("retention_phase")
    capability = visit.get("capability_id")
    policy_key = policy(visit)
    projected = (
        teacher_fields({
            "grade": grade(visit),
            "capability": capability,
            "teacher_policy": policy_key,
            "teacher_selection_reason": visit.get("teacher_selection_reason"),
            "teacher_selection_policy": visit.get("teacher_selection_policy"),
            "teacher_policy_evidence_before": visit.get("teacher_policy_evidence_before"),
            "vnext_canary": visit.get("vnext_canary"),
            "actual_authority_changed": visit.get("actual_authority_changed"),
            "candidate_retention": {
                "phase": retention_phase,
                "decision": retention_decision,
            },
        }, history)
        if (history is not None and isinstance(capability, str) and capability
            and policy_key != "-" and isinstance(retention_phase, str)
            and retention_decision in {"PROVISIONAL", "REJECT"})
        else {}
    )
    retention_pending = retention_decision not in {"PROVISIONAL", "REJECT"}
    projected_health = (
        projected.get("health")
        or (PENDING if retention_pending else health(visit)))
    return {
        MARKER: True, "grade": grade(visit),
        "capability": visit.get("capability_id") or "-",
        "attempt": visit.get("visit_index", "-"), "policy": policy(visit),
        "lr": _scaled_lr(strategy.get("lr")),
        "depth": _whole(strategy.get("depth")),
        "contrast": _whole(strategy.get("contrast")),
        "old": _whole(strategy.get("old")),
        "preview": _display(strategy.get("preview")),
        "distill": _display(strategy.get("distill")),
        "credit": NOT_MEASURED,
        "p_ret": projected.get("p_ret", PENDING if retention_pending else NOT_MEASURED),
        "health": projected_health,
    }


def mastery_rows(visits):
    latest, grades = {}, {}
    accepted = None
    for visit in visits:
        if visit.get("outcome") != "ACCEPTED":
            continue
        accepted = visit
        capability = visit.get("capability_id")
        scores = paired_scores(visit)
        if not scores and isinstance(capability, str) and (measured := score(visit)):
            scores = {capability: measured}
        for subject, measured in scores.items():
            owner = grade(visit) if subject == capability else subject.partition(".")[0]
            latest[subject] = (visit, owner, measured)
            grades[owner] = visit
    families = []
    for capability, (visit, owner, measured) in latest.items():
        families.append({
            MARKER: True, "grade": owner, "family": capability,
            "start": f"{measured[0]}/{measured[2]}",
            "before": f"{measured[0]}/{measured[2]}",
            "after": f"{measured[1]}/{measured[2]}",
            "gain": f"{measured[1] - measured[0]:+d}",
            "attempt": visit.get("visit_index", "-"),
            "step": visit.get("candidate_optimizer_step", "-"),
            "outcome": ("STALE PAIR" if visit is not accepted else
                        "RETAINED PAIR" if visit.get("_durable_terminal_history") else
                        "OBSERVED PAIR"),
        })
    summaries = []
    for owner, visit in grades.items():
        scores = {cap: measured for cap, (source, group, measured) in latest.items()
                  if source is visit and group == owner}
        complete = complete_local_pair(visit, owner, scores) if visit is accepted else None
        summaries.append({
            MARKER: True, "grade": owner, "visit": visit.get("visit_index", "-"),
            "step": visit.get("candidate_optimizer_step", "-"),
            "attempt": visit.get("visit_index", "-"),
            "start": f"{complete[0]}/{complete[2]}" if complete else NOT_MEASURED,
            "latest": f"{complete[1]}/{complete[2]}" if complete else NOT_MEASURED,
            "best": NOT_MEASURED, "to100": NOT_MEASURED,
            "right_pct": NOT_MEASURED,
            "outcome": ("RETAINED PAIR" if complete and visit.get("_durable_terminal_history")
                        else "OBSERVED PAIR" if complete else "PARTIAL PAIR"),
        })
    return summaries, families


def system_rows(current, visits):
    steps = current.get("candidate_steps")
    step = steps[-1] if isinstance(steps, list) and steps else {}
    activity = str(current.get("activity") or current.get("phase") or "-")
    elapsed = number(current.get("activity_elapsed_ms"))
    activity_time = (
        f"{elapsed / 1000:.1f}s" if elapsed is not None else NOT_MEASURED)
    progress = (
        f"{current.get('candidate_step', '-')} / "
        f"{current.get('candidate_horizon', '-')}")
    accepted = sum(visit.get("outcome") == "ACCEPTED" for visit in visits)
    rejected = sum(visit.get("outcome") == "REJECTED" for visit in visits)
    owner = grade(current)
    return [
        {MARKER: True, "kind": "WINDOW", "grade": owner,
         "detail": f"terminal observed visits {len(visits)} | accepted {accepted} | rejected {rejected}"},
        {MARKER: True, "kind": "RESOURCE", "grade": owner,
         "detail": f"peak RSS {gib(current.get('peak_rss_bytes'))} | disk free {gib(current.get('disk_free_bytes'))}"},
        {MARKER: True, "kind": "VISIT PERF", "grade": owner,
         "detail": (
             f"plan {seconds(current.get('planning_wall_seconds'))} | "
             f"retain {seconds(current.get('retention_wall_seconds'))} | "
             f"champ {seconds(current.get('championship_wall_seconds'))} | "
             f"publish {seconds(current.get('publishing_wall_seconds'))}")},
        {MARKER: True, "kind": "STEP PERF", "grade": owner,
         "detail": (
             f"{progress} | wall {seconds(step.get('candidate_step_wall_seconds'))} | "
             f"B11 {seconds(step.get('b11_autodiff_wall_seconds'))} | "
             f"batch {seconds(step.get('c08_logical_batch_wall_seconds'))}")},
        {MARKER: True, "kind": "ACTIVITY", "grade": owner,
         "detail": f"{activity} | {activity_time}"},
    ]
