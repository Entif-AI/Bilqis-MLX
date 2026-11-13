"""Shared visit helpers kept independent from orchestration phase ownership."""
from __future__ import annotations


RETENTION_REQUIRES_ACTIVE_GRADE_ERROR = "RETENTION_REQUIRES_ACTIVE_GRADE"
TEACHER_EXPOSURE_HISTORY_INVALID = "TEACHER_EXPOSURE_HISTORY_INVALID"


def retention_frontier_grade(school) -> str:
    active = tuple(school.active_grades)
    if not active:
        raise ValueError(RETENTION_REQUIRES_ACTIVE_GRADE_ERROR)
    return active[-1]


def teacher_exposures_after_candidate(receipt: dict, attempted: dict, *, decision: str) -> dict:
    if decision not in {"REJECT", "PROVISIONAL"}:
        raise ValueError(TEACHER_EXPOSURE_HISTORY_INVALID)
    prior = receipt.get("teacher_miss_exposures", {})
    if (not isinstance(prior, dict) or not isinstance(attempted, dict) or
            any(not isinstance(identity, str) or type(count) is not int or count < 0
                for mapping in (prior, attempted) for identity, count in mapping.items())):
        raise ValueError(TEACHER_EXPOSURE_HISTORY_INVALID)
    if any(attempted.get(identity, 0) < count for identity, count in prior.items()):
        raise ValueError(TEACHER_EXPOSURE_HISTORY_INVALID)
    return dict(attempted)


def teaching_enrichment_rows(d, source_root, graph, course, capability, *, seed: int,
                             enabled: bool, release=None):
    if release is not None:
        from bilqis_mlx.factory.teaching import optional_teaching_rows
        return optional_teaching_rows(
            source_root, graph, release, d._source_adapters_school.live_source_registry(),
            capability=capability, seed=seed, enabled=enabled)
    return d._source_adapters_school.live_source_registry().optional_teaching_rows(
        course, capability=capability, source_root=source_root, graph=graph,
        seed=seed, enabled=enabled)


def extend_binary_guidance(guidance, rows):
    if guidance is None or not rows:
        return guidance
    import numpy as np
    soft_target, strength = guidance
    extra_target = np.eye(2, dtype=np.float32)[
        [1 if row["gold"] == "TRUE" else 0 for row in rows]]
    return (
        np.concatenate((np.asarray(soft_target, dtype=np.float32), extra_target), axis=0),
        np.concatenate((np.asarray(strength, dtype=np.float32),
                        np.zeros(len(rows), dtype=np.float32))))


def skip_perfect_target_visit(d, run_dir, receipt, school, course, capability,
                              probe_total, optimizer_step, *, teacher=None):
    skipped_school = d._curriculum_scheduler.visit(
        d._runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course),
        school, capability, school.current_student)
    result = d._runtime_checkpoints._advance(
        run_dir, receipt, skipped_school, teacher=teacher, persist=False)
    event = {
        "event": "SCHOOL_PERFECT_TARGET_VISIT_SKIPPED", "capability": capability,
        "grade": capability.partition(".")[0], "active_grade": skipped_school.grade,
        "generation": result["generation"], "optimizer_step": optimizer_step,
        "target_probe_correct": probe_total, "target_probe_total": probe_total,
        "retained_optimizer_updates": 0, "reason": "NO_POSSIBLE_STRICT_TARGET_GAIN",
    }
    result["_pending_visit_events"] = [*receipt.get("_pending_visit_events", ()), event]
    return result


def skip_stagnant_target_visit(d, run_dir, receipt, school, course, capability,
                               optimizer_step):
    skipped_school = d._curriculum_scheduler.visit(
        d._runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course),
        school, capability, school.current_student)
    result = d._runtime_checkpoints._advance(run_dir, receipt, skipped_school, persist=False)
    event = {
        "event": "SCHOOL_STAGNANT_CAPABILITY_VISIT_SKIPPED", "capability": capability,
        "grade": capability.partition(".")[0], "active_grade": skipped_school.grade,
        "generation": result["generation"], "optimizer_step": optimizer_step,
        "retained_optimizer_updates": 0, "teacher_updated": False,
        "reason": "CURRENT_SESSION_STAGNATION_QUARANTINE", "required_mastery_debt": True,
    }
    result["_pending_visit_events"] = [*receipt.get("_pending_visit_events", ()), event]
    return result


def selection_feedback(d, teacher, capability, curriculum_scope, policy,
                       outcome, before, after, context_credit):
    reward = after - before
    credit = d._learning_learning_experiment.selection_credit(reward, outcome, context_credit)
    health = None if outcome is None else (
        d._learning_teacher_strategy_population.durable_policy_cooldown_status(
            teacher.get("causal_experiment", {}), capability, curriculum_scope,
            d._learning_teacher_strategy_population.effective_policy_key(policy)))
    return reward, credit, health


def teacher_event_fields(d, policy_selection, policy_health):
    result = {
        "teacher_selection_policy": policy_selection["selection_policy"],
        "teacher_selection_reason": policy_selection["selection_reason"],
        "teacher_strategy_population": {
            key: policy_selection.get(key)
            for key in ("strategy_archive_count", "active_effective_strategy_count",
                        "active_effective_strategy_capacity", "dormant_effective_strategy_count",
                        "live_effective_strategy_count", "strategy_population_capacity",
                        "retired_effective_strategy_count", "checkpoint_retired_effective_strategy_count",
                        "realized_action_ecology_count") if policy_selection.get(key) is not None},
    }
    if policy_selection.get("mutation_parent_policy_key"):
        result["teacher_mutation_parent"] = {
            "policy_key": policy_selection["mutation_parent_policy_key"],
            "basis": policy_selection.get("mutation_parent_basis"),
            "changed_fields": policy_selection.get("mutation_changed_fields", []),
            "mode": policy_selection.get("mutation_mode"),
        }
    if policy_health and policy_health["active"]:
        result["teacher_policy_health"] = policy_health
    return result


def prepare_visit_feedback(d, receipt, cap, champion_candidates, champion_candidate_ids):
    priority = [r for r in receipt.get("teacher_misses", ()) if r["capability"] == cap]
    deferred_misses = []
    if receipt.get("numeric_maximum") is not None:
        priority, deferred_misses = d._profiles_catalog.partition_numeric_scope(
            priority, receipt["numeric_maximum"])
    priority_ids = {row["id"] for row in priority}
    priority.extend(row for row in champion_candidates if row["id"] not in priority_ids)
    miss_exposures = dict(receipt.get("teacher_miss_exposures", {}))
    if any(type(count) is not int or count < 0 for count in miss_exposures.values()):
        raise ValueError("HUMAN_TRAINER_MISS_EXPOSURE_STATE_INVALID")
    previous_methodology = next((
        member.get("lesson_methodology") for member in reversed(receipt.get("delivery_outbox", ()))
        if member.get("capability") == cap and "lesson_methodology" in member), None)
    warnings = d._learning_teacher_feedback.active_warning_signals(
        receipt.get("last_exam"), previous_methodology, cap)
    diagnostics = {"warnings": warnings, "unresolved_miss_count": len(priority),
                   "champion_candidate_count": len(champion_candidate_ids)}
    return priority, deferred_misses, miss_exposures, warnings, diagnostics


def direct_mentor_votes(confidence_champions):
    votes, capabilities = {}, []
    for mentor in confidence_champions:
        for source_grade, count in mentor.get("source_grade_votes", {}).items():
            votes[source_grade] = votes.get(source_grade, 0) + count
        capabilities.extend(mentor.get("capabilities", ()))
    return votes, capabilities


def methodology_lesson_rows(capability: str, fresh, priority, picked):
    offered, offered_by_id = [], {}
    for row in (*fresh, *priority):
        if row.get("capability") != capability:
            continue
        identity = row.get("id")
        if identity in offered_by_id:
            if offered_by_id[identity] != row:
                raise ValueError("LESSON_EVIDENCE_OFFERED_IDENTITY_CONFLICT")
            continue
        offered_by_id[identity] = row
        offered.append(row)
    return offered, [row for row in picked if row.get("capability") == capability]


def visit_retention_scope(d, run_dir, receipt, course, school, cap, learning_settings,
                          *, candidate_steps=1, fragile_fixed_rows=()):
    old_capabilities = (
        d._learning_learning_experiment.earlier_grade_capabilities(
            d._runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course),
            school.champions, cap,
            carried_mastery_debt=getattr(school, "carried_mastery_debt", ()))
        if learning_settings is not None else ())
    retention_support = ()
    if (learning_settings is not None and getattr(school, "active_grades", ()) and
            getattr(school, "schema", None) is not None):
        admitted = d._curriculum_scheduler.assessment_capabilities(
            d._runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school)
        preserved = tuple(sorted({
            row.get("capability") for row in fragile_fixed_rows
            if isinstance(row, dict) and isinstance(row.get("capability"), str)}))
        retention_support = d._runtime_candidate_evidence._retention_support_schedule(
            admitted, getattr(school, "active_grades", ()), cap, steps=candidate_steps,
            rotation=int(getattr(school, "visits", 0)), already_preserved=preserved)
    return old_capabilities, retention_support


def prepare_retention_trial(d, mx, run_dir, receipt, course, school, cap, learning_settings,
                            source_root, graph, executable_release, params, optimizer,
                            original_learning_rate, teacher):
    parent_parameters, parent_optimizer = params, optimizer
    probe_rows = protected_caps = parent_predictions = None
    if learning_settings is not None:
        with d._runtime_timing_trace.trace_span("RETENTION_PROBE_BUILD", capability=cap):
            probe_rows, protected_caps, _ = d._runtime_candidate_evidence._learning_probe_rows(
                source_root, graph, receipt, course, school, cap, learning_settings,
                schedule_program=d._runtime_release_adoption._schedule_for_receipt(
                    run_dir, receipt, course), executable_release=executable_release)
        target_rows = [row for row in probe_rows if row["capability"] == cap]
        with d._runtime_timing_trace.trace_span("RETENTION_PARENT_PREDICT", capability=cap,
                                                row_count=len(target_rows)):
            parent_predictions = d._learning_student_ops._predictions(
                mx, parent_parameters, target_rows, receipt["config"], receipt["answer_ids"])
        if target_rows and all(parent_predictions[row["id"]] == row["gold"] for row in target_rows):
            parent_optimizer.learning_rate = original_learning_rate
            skipped = d._skip_perfect_target_visit(
                run_dir, receipt, school, course, cap, len(target_rows),
                int(parent_optimizer.state["step"].item()), teacher=teacher)
            return probe_rows, protected_caps, parent_predictions, params, optimizer, skipped
        with d._runtime_timing_trace.trace_span("FORK_CANDIDATE", capability=cap):
            params, optimizer = d._learning_learning_experiment.fork_student(
                mx, parent_parameters, parent_optimizer)
    return probe_rows, protected_caps, parent_predictions, params, optimizer, None


def discover_champion_weakness(d, mx, champions, params, rows, receipt, cap):
    with d._runtime_timing_trace.trace_span("CHAMPION_WEAKNESS_DISCOVERY", capability=cap):
        candidates = d._learning_lesson_guidance._champion_directed_rows(
            mx, champions, params, rows, receipt["config"], receipt["answer_ids"])
    return candidates, {row["id"] for row in candidates}


def load_visit_mentors(d, run_dir, receipt, lesson_grade, graph, program, cap):
    with d._runtime_timing_trace.trace_span("MENTOR_SOURCES_LOAD", capability=cap):
        return d._learning_lesson_guidance._mentor_sources_for_visit(
            run_dir, receipt, lesson_grade, graph, len(program.grades))
