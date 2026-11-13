"""Fresh and fixed source evidence for candidate retention."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SOURCE
from .capability_authority import evaluate_progression_authority
from .capability_retention import (
    candidate_work_disposition, configuration_outcome, retain_candidate,
)

import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.fixed_frontier as _bilqis_mlx_fixed_frontier
import bilqis_mlx.learning.learning_experiment as _learning_learning_experiment
import bilqis_mlx.learning.plasticity_escape as _learning_plasticity_escape
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.profiles.retention as _profiles_retention
import bilqis_mlx.runtime.assessment as _runtime_assessment
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state


from .retention_support import (
    _retention_support_capabilities, _retention_support_schedule, _select_fresh_retention_support_rows,
    _fresh_fragile_preservation_rows, _inject_preservation_rows,
)
from .fixed_frontier_evidence import (
    _fixed_same_grade_rows, _reusable_exam_identity, _frontier_fixed_evidence,
    _fragile_replay_evidence,
)


def _learning_probe_rows(source_root, graph, receipt, course, school, capability,
                         settings, *, schedule_program=None,
                         executable_release=None):
    """Complete admitted target grade plus bounded cross-grade protection."""
    eligible = set(_curriculum_scheduler.assessment_capabilities(
        schedule_program if schedule_program is not None else course,
        school)) | {capability}
    scores = (receipt.get("last_exam") or {}).get("scores") or {}
    from bilqis_mlx.learning.learning_experiment import whole_grade_protection
    selected = whole_grade_protection(
        eligible, capability, scores,
        cap_limit=settings.protected_cap_limit, rotation=school.visits)
    sampled = selected | {capability}
    # The target must show a positive change before a candidate is promoted.
    # A six-item panel is too coarse near mastery. Draw enough *fresh* source
    # questions to match the fixed examination's capability sample size,
    # capped at the existing maximum; keep protected probes inexpensive.
    exam_target_size = scores.get(capability, {}).get("total")
    target_each = (
        max(settings.probe_each, min(48, exam_target_size))
        if type(exam_target_size) is int and exam_target_size > 0
        else min(48, max(settings.probe_each, settings.probe_each * 2))
    )
    rows = []
    for name in sorted(sampled):
        rows.extend(_runtime_assessment._draw_live_rows(
            source_root, graph, course=course, capability=name,
            executable_release=executable_release,
            each=(target_each if name.partition(".")[0] ==
                  capability.partition(".")[0] else settings.probe_each),
            seed=_runtime_state._seed(receipt, capability="LEARNING_PROBE:"+name)))
    if {r["capability"] for r in rows} != sampled:
        raise ValueError("LEARNING_EXPERIMENT_PROBE_SCOPE_INCOMPLETE")
    return rows, selected, len(eligible)-len(sampled)


def _same_grade_fixed_evidence(
        mx, run_dir, receipt, course, school, capability, parent, candidate,
        settings, config, answer_ids):
    fixed_rows = _fixed_same_grade_rows(
        run_dir, receipt, course, school, capability, settings)
    if not fixed_rows:
        return {
            "status": "NOT_MEASURED",
            "reason": "NO_COMPARABLE_COMPLETE_GRADE_EXAM",
        }
    parent_fixed = _learning_student_ops._predictions(
        mx, parent, list(fixed_rows), config, answer_ids)
    candidate_fixed = _learning_student_ops._predictions(
        mx, candidate, list(fixed_rows), config, answer_ids)
    scores = _learning_learning_experiment.paired_outcomes(fixed_rows, parent_fixed, candidate_fixed)
    return {
        "status": "MEASURED",
        "grade": capability.partition(".")[0],
        "cohort_sha256": _bilqis_mlx_fixed_frontier.frontier_exam(receipt)["cohort_sha256"],
        "before": sum(value["before"] for value in scores.values()),
        "after": sum(value["after"] for value in scores.values()),
        "total": sum(value["total"] for value in scores.values()),
        "capabilities": scores,
    }


def _candidate_fixed_evidence(mx, run_dir, receipt, course, school, capability,
                              parent, candidate, settings):
    """Score only the fixed evidence needed after fresh grade gain is proven."""
    config, answer_ids = receipt["config"], receipt["answer_ids"]
    (frontier_rows, fixed, frontier,
     frontier_parent, frontier_candidate) = _frontier_fixed_evidence(
        mx, run_dir, receipt, school, capability, parent, candidate,
        config, answer_ids)
    if not frontier_rows:
        fixed = _same_grade_fixed_evidence(
            mx, run_dir, receipt, course, school, capability, parent, candidate,
            settings, config, answer_ids)

    replay = _fragile_replay_evidence(
        mx, run_dir, receipt, parent, candidate, config, answer_ids,
        frontier_parent, frontier_candidate)
    return fixed, replay, frontier


def _candidate_grade_evidence(mx, run_dir, receipt, course, school, capability,
                              parent, candidate, probe_rows, target_parent,
                              settings, plasticity_escape=None):
    """Complete missing candidate scores only after a target gain is observed.

    Parent/candidate predictions are never reused across candidate weights,
    AdamW steps, source questions or source-cohort identities. A target failure
    is conclusive rejection without running redundant peer and exam inference.
    """
    config, answer_ids = receipt["config"], receipt["answer_ids"]
    target_rows = [row for row in probe_rows if row["capability"] == capability]
    target_candidate = _learning_student_ops._predictions(mx, candidate, target_rows, config, answer_ids)
    target_pair = _learning_learning_experiment.paired_outcomes(target_rows, target_parent, target_candidate)
    required = tuple(sorted(
        name for name in _curriculum_scheduler.assessment_capabilities(_runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school)
        if name.partition(".")[0] == capability.partition(".")[0]))
    if target_pair[capability]["after"] <= target_pair[capability]["before"]:
        return (target_pair, set(), (capability,), {
            "status": "NOT_MEASURED", "reason": "TARGET_DID_NOT_GAIN"},
            {"status": "NOT_MEASURED", "reason": "TARGET_DID_NOT_GAIN"},
            {"status": "NOT_MEASURED", "reason": "TARGET_DID_NOT_GAIN"},
            "TARGET_ONLY_REJECTED")

    # This checkpoint has already been evaluated on its target. Score only
    # missing grade peers and independently selected cross-grade sentinels.
    missing = _learning_learning_experiment.missing_grade_capabilities(required, target_pair)
    remaining = [row for row in probe_rows
                 if row["capability"] in missing or
                 row["capability"].partition(".")[0] != capability.partition(".")[0]]
    parent_scores = {**target_parent}
    candidate_scores = {**target_candidate}
    if remaining:
        parent_scores.update(_learning_student_ops._predictions(mx, parent, remaining, config, answer_ids))
        candidate_scores.update(_learning_student_ops._predictions(
            mx, candidate, remaining, config, answer_ids))
    pair = _learning_learning_experiment.paired_outcomes(probe_rows, parent_scores, candidate_scores)
    if _learning_learning_experiment.missing_grade_capabilities(required, pair):
        raise ValueError("LEARNING_EXPERIMENT_INCOMPLETE_SAME_GRADE_PROMOTION")
    protected = set(pair)-set(required)
    protected.update(name for name in required if name != capability)
    grade_net = sum(pair[name]["after"]-pair[name]["before"] for name in required)
    if grade_net < 0 and not _learning_plasticity_escape.allows_early_grade_net(
            plasticity_escape, pair, required):
        return (pair, protected, required,
                {"status": "NOT_MEASURED",
                 "reason": "SAME_GRADE_NET_REGRESSION"},
                {"status": "NOT_MEASURED",
                 "reason": "SAME_GRADE_NET_REGRESSION"},
                {"status": "NOT_MEASURED",
                 "reason": "SAME_GRADE_NET_REGRESSION"},
                "GRADE_NET_REJECTED")

    fixed, replay, frontier = _candidate_fixed_evidence(
        mx, run_dir, receipt, course, school, capability, parent, candidate,
        settings)
    return (pair, protected, required, fixed, replay, frontier,
            "COMPLETE_SAME_GRADE")
