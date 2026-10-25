"""Fresh and fixed source evidence for candidate retention."""
from __future__ import annotations

import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.fixed_frontier as _bilqis_mlx_fixed_frontier
import bilqis_mlx.learning.learning_experiment as _learning_learning_experiment
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.profiles.retention as _profiles_retention
import bilqis_mlx.runtime.assessment as _runtime_assessment
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state


def _retention_support_capabilities(admitted, active_grades,
                                    capability: str) -> tuple[str, ...]:
    """Return fresh-source support matching the surfaces retention protects."""
    admitted = tuple(admitted)
    active_grades = tuple(active_grades)
    if (not active_grades or not isinstance(capability, str) or
            "." not in capability):
        return ()
    target_grade = capability.partition(".")[0]
    frontier_grade = active_grades[-1]
    support_grade = (
        frontier_grade if target_grade != frontier_grade else target_grade)
    return tuple(sorted(
        name for name in admitted
        if name != capability and name.partition(".")[0] == support_grade))


def _select_fresh_retention_support_rows(
        rows, *, rotation: int) -> tuple[dict, ...]:
    """Choose one complete fresh source family for preservation rehearsal."""
    if type(rotation) is not int or rotation < 0:
        raise ValueError("RETENTION_SUPPORT_ROTATION_INVALID")
    groups = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("RETENTION_SUPPORT_ROW_INVALID")
        groups.setdefault(row.get("source_id", row["id"]), []).append(row)
    if not groups:
        return ()
    keys = sorted(groups, key=str)
    return tuple(groups[keys[rotation % len(keys)]])


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


def _fixed_same_grade_rows(run_dir, receipt, course, school, capability, settings):
    """Reuse the last independently scored full-grade cohort, if available.

    No new test rows are generated here. The persisted cohort, rubric and
    content hash must all verify before the parent/challenger screen can
    claim a fixed-exam grade comparison.
    """
    own_grade = capability.partition(".")[0]
    exam = receipt.get("last_exam") or {}
    if (exam.get("assessment_grade") != own_grade or
            exam.get("grade_exam_epoch") != school.grade_exam_epoch):
        return ()
    required = {cap for cap in _curriculum_scheduler.assessment_capabilities(_runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school)
                if cap.partition(".")[0] == own_grade}
    exam_scores = exam.get("scores") or {}
    if not required <= set(exam_scores):
        return ()
    cohort = _runtime_assessment._verify_saved_cohort(run_dir, receipt, course)
    if cohort is None:
        raise ValueError("LEARNING_EXPERIMENT_FIXED_GRADE_COHORT_MISSING")
    rows = tuple(r for r in cohort.rows if r["capability"] in required)
    if (len(rows) != len({r["id"] for r in rows}) or
            len(rows) > len(required) * 48 or
            any(type(exam_scores[cap].get("total")) is not int or
                exam_scores[cap]["total"] < 1 or
                sum(row["capability"] == cap for row in rows) !=
                exam_scores[cap]["total"] for cap in required)):
        raise ValueError("LEARNING_EXPERIMENT_FIXED_GRADE_COHORT_INCOMPLETE")
    return rows


def _reusable_exam_identity(receipt, school, *, rubric_sha256,
                            assessment_scope_sha256):
    """Return the exact already-scored exam identity for an unchanged student."""
    exam = receipt.get("last_exam") or {}
    student = school.current_student
    if (exam.get("assessment_grade") != school.grade or
            exam.get("grade_exam_epoch") != school.grade_exam_epoch or
            exam.get("student_sha256") != student.sha256 or
            exam.get("optimizer_step") != student.optimizer_step or
            exam.get("exam_rubric_sha256") != rubric_sha256 or
            exam.get("assessment_scope_sha256") != assessment_scope_sha256):
        return None
    cohort_sha = exam.get("cohort_sha256")
    if (not isinstance(cohort_sha, str) or len(cohort_sha) != 64 or
            any(c not in "0123456789abcdef" for c in cohort_sha)):
        raise ValueError("HUMAN_TRAINER_REUSABLE_EXAM_COHORT_IDENTITY_INVALID")
    return (student.sha256, student.optimizer_step, cohort_sha,
            rubric_sha256, assessment_scope_sha256)


def _frontier_fixed_evidence(
        mx, run_dir, receipt, school, capability, parent, candidate,
        config, answer_ids):
    fixed = {"status": "NOT_MEASURED",
             "reason": "NO_COMPARABLE_COMPLETE_GRADE_EXAM"}
    frontier = {"status": "NOT_MEASURED",
                "reason": "NO_FIXED_WHOLE_SCHOOL_FRONTIER"}
    frontier_parent = frontier_candidate = {}
    from bilqis_mlx.fixed_frontier import load_frontier, screen_frontier, frontier_exam
    exam = frontier_exam(receipt)
    frontier_rows, frontier_parent = load_frontier(
        run_dir, receipt, parent_sha256=exam.get("student_sha256"),
        parent_optimizer_step=exam.get("optimizer_step"))
    if frontier_rows and (exam.get("student_sha256") != school.current_student.sha256 or
                          exam.get("optimizer_step") != school.current_student.optimizer_step):
        if (type(exam.get("optimizer_step")) is not int or
                school.current_student.optimizer_step <= exam["optimizer_step"]):
            raise ValueError("FIXED_FRONTIER_PARENT_IDENTITY_DRIFT")
        frontier_parent = _learning_student_ops._predictions(
            mx, parent, list(frontier_rows), config, answer_ids)
    if frontier_rows:
        grade = capability.partition(".")[0]
        grade_rows = tuple(
            row for row in frontier_rows
            if row["capability"].partition(".")[0] == grade)
        if grade_rows:
            grade_parent = {
                row["id"]: frontier_parent[row["id"]] for row in grade_rows}
            grade_candidate = _learning_student_ops._predictions(
                mx, candidate, list(grade_rows), config, answer_ids)
            grade_scores = _learning_learning_experiment.paired_outcomes(
                grade_rows, grade_parent, grade_candidate)
            fixed = {
                "status": "MEASURED", "grade": grade,
                "cohort_sha256": exam["cohort_sha256"],
                "before": sum(value["before"] for value in grade_scores.values()),
                "after": sum(value["after"] for value in grade_scores.values()),
                "total": sum(value["total"] for value in grade_scores.values()),
            }
            frontier_candidate = dict(grade_candidate)
        else:
            fixed = {
                "status": "NOT_MEASURED",
                "reason": "ACTIVE_GRADE_ABSENT_FROM_FIXED_FRONTIER",
            }
        other_rows = tuple(
            row for row in frontier_rows if row not in grade_rows)
        if other_rows:
            frontier_candidate.update(_learning_student_ops._predictions(
                mx, candidate, list(other_rows), config, answer_ids))
        frontier = screen_frontier(
            frontier_rows, frontier_parent, frontier_candidate,
            frontier_exam(receipt)["cohort_sha256"])
    return frontier_rows, fixed, frontier, frontier_parent, frontier_candidate


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
    }


def _fragile_replay_evidence(
        mx, run_dir, receipt, parent, candidate, config, answer_ids,
        frontier_parent, frontier_candidate):
    from bilqis_mlx.learning.fragile_replay import load_replay_rows, screen_replay
    policy = _profiles_retention.fragile_preservation_policy()
    replay_rows = load_replay_rows(
        run_dir, receipt,
        capabilities=policy.capabilities)
    if not replay_rows:
        return {
            "status": "NOT_MEASURED",
            "reason": "FRAGILE_PRESERVATION_EXAM_NOT_YET_ADMITTED",
        }
    ids = {row["id"] for row in replay_rows}
    replay_parent = (
        {rid: frontier_parent[rid] for rid in ids}
        if ids <= frontier_parent.keys() else
        _learning_student_ops._predictions(mx, parent, list(replay_rows), config, answer_ids))
    replay_candidate = (
        {rid: frontier_candidate[rid] for rid in ids}
        if ids <= frontier_candidate.keys() else
        _learning_student_ops._predictions(mx, candidate, list(replay_rows), config, answer_ids))
    return screen_replay(
        replay_rows, replay_parent, replay_candidate,
        _bilqis_mlx_fixed_frontier.frontier_exam(receipt)["cohort_sha256"])


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
                              settings):
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
    if grade_net < 0:
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


def _fresh_fragile_preservation_rows(run_dir, source_root, graph, receipt,
                                     course, school, capability, *, step,
                                     batch_size, fixed_rows=None,
                                     executable_release=None):
    """Generate fresh semantic siblings for the configured fragile safety rows.

    Rehearsal is active only after a source-verified replay exam exists.
    The fixed examination rows themselves are never delivered to the optimizer.
    """
    from bilqis_mlx.learning.fragile_replay import load_replay_rows, fresh_preservation_rows
    policy = _profiles_retention.fragile_preservation_policy()
    fixed = (tuple(fixed_rows) if fixed_rows is not None else
             load_replay_rows(run_dir, receipt, capabilities=policy.capabilities))
    if not fixed:
        return ()
    admitted = set(_curriculum_scheduler.assessment_capabilities(
        _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school))
    requested = tuple(name for name in policy.capabilities if name in admitted)
    return fresh_preservation_rows(
        fixed, capabilities=requested, rotation=max(0, step - 1) * policy.per_capability_target,
        batch_size=batch_size, retention_policy=policy,
        seed_for=lambda name, attempt: _runtime_state._seed(
            receipt, capability=f"FRAGILE_PRESERVE:{name}:{attempt}", step=step),
        draw_rows=lambda **kwargs: _runtime_assessment._draw_live_rows(
            source_root, graph, executable_release=executable_release, course=course, **kwargs))


def _inject_preservation_rows(chosen, preservation, *, reserved_ids=()):
    """Reserve preservation slots without displacing selected weakness targets."""
    result = list(chosen)
    reserved = set(reserved_ids)
    consumed = set()
    for index, row in enumerate(result):
        identity = row.get("id")
        if identity in reserved:
            consumed.add(index)
            reserved.remove(identity)
    delivered = []
    for item in preservation:
        replacement = next((
            index for index, row in enumerate(result)
            if index not in consumed and row.get("gold") == item.get("gold")
        ), None)
        if replacement is None:
            replacement = next((
                index for index in range(len(result)) if index not in consumed
            ), None)
        if replacement is None:
            break
        result[replacement] = item
        consumed.add(replacement)
        delivered.append(item)
    if len(delivered) != len(preservation):
        raise ValueError("FRAGILE_PRESERVATION_BATCH_CAPACITY_EXHAUSTED")
    return result, tuple(delivered)
