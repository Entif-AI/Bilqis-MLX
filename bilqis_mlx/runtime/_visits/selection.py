"""Lesson selection, guidance, and evidence bookkeeping for one visit step."""
from __future__ import annotations


def select(d, s, step, prepared, fresh, option_rows, preservation, retention_support):
    lesson_seed = d._runtime_state._seed(s.receipt, capability=s.cap, step=step + 1)
    with d._runtime_timing_trace.trace_span("STEP_LESSON_SELECT", capability=s.cap,
                                            visit_step=step + 1):
        lesson_control = None
        if s.learning_settings is not None:
            prior = list(prepared["prior"]) if prepared is not None else []
            if prepared is None and int(s.policy.get("old", 0)) > 0 and s.old_capabilities:
                selected = s.old_capabilities[(s.school.visits + step) % len(s.old_capabilities)]
                prior = d._runtime_assessment._draw_live_rows(
                    s.source_root, s.graph, course=s.course,
                    executable_release=s.executable_release, capability=selected,
                    each=max(s.batch_size, 6),
                    seed=d._runtime_state._seed(
                        s.receipt, capability="EXPERIMENT_OLD:" + selected, step=step))
            picked, control = d._learning_learning_experiment.select_source_lesson(
                fresh, prior, s.policy, seed=lesson_seed, batch_size=s.batch_size,
                targets=s.priority, target_exposures=s.miss_exposures,
                priority_target_ids=s.champion_candidate_ids,
                reserved_support_slots=len(preservation) + len(retention_support))
            lesson_control = {**control, "eligible_prior_capabilities": len(s.old_capabilities)}
            target_ids = set(control["weakness_target_ids"])
            window = [row for row in s.priority if row["id"] in target_ids]
            s.champion_prioritized += sum(
                row["id"] in s.champion_candidate_ids for row in window)
        else:
            prior = []
            picked = d._learning_lesson_guidance.choose_lesson_batch(
                fresh, s.policy, lesson_seed, batch_size=s.batch_size)
            target_capacity = sum(row["capability"] == s.cap for row in picked)
            window = d._learning_teacher_feedback.select_weakness_targets(
                s.priority, d._learning_teacher_feedback.WeaknessTargetRequest(
                    exposures=s.miss_exposures, capacity=target_capacity))
            picked, delivered_targets = d._learning_learning_experiment.reserve_weakness_targets(
                picked, window)
            window = list(delivered_targets)
            target_ids = {row["id"] for row in window}
    delivered_preservation = delivered_retention_support = ()
    if s.learning_settings is not None:
        fresh_support_ids = set(
            lesson_control.get("fresh_support_ids", ()) if lesson_control is not None else ())
        support_rows = (*preservation, *retention_support)
        with d._runtime_timing_trace.trace_span(
                "STEP_FRAGILE_PRESERVATION_INJECT", capability=s.cap, visit_step=step + 1):
            picked, delivered_support = d._runtime_candidate_evidence._inject_preservation_rows(
                picked, support_rows, reserved_ids=target_ids | fresh_support_ids)
        fragile_ids = {row["id"] for row in preservation}
        retention_ids = {row["id"] for row in retention_support}
        delivered_preservation = tuple(row for row in delivered_support if row["id"] in fragile_ids)
        delivered_retention_support = tuple(
            row for row in delivered_support if row["id"] in retention_ids)
    if prepared is not None:
        enrichment_rows = tuple(prepared["teaching_enrichment_rows"])
    else:
        with d._runtime_timing_trace.trace_span(
                "STEP_TEACHING_ENRICHMENT", capability=s.cap, visit_step=step + 1):
            enrichment_rows = d._teaching_enrichment_rows(
                s.source_root, s.graph, s.course, s.cap,
                seed=d._runtime_state._seed(
                    s.receipt, capability="TEACHING_ENRICHMENT:" + s.cap, step=step + 1),
                enabled=s.boolean_association_bridge, release=s.executable_release)
    s.enrichment_examples += len(enrichment_rows)
    if lesson_control is not None:
        lesson_control["planned_old_grade_examples"] = lesson_control["effective_old_grade_examples"]
        earlier_grades = {item.partition(".")[0] for item in s.old_capabilities}
        lesson_control["effective_old_grade_examples"] = sum(
            row["capability"].partition(".")[0] in earlier_grades for row in picked)
        lesson_control["selected_answer_kinds"] = sorted({
            row.get("answer_kind", "binary") for row in picked})
        lesson_control["fragile_preservation_requested"] = len(preservation)
        lesson_control["fragile_preservation_delivered"] = len(delivered_preservation)
        lesson_control["fragile_preservation_capabilities"] = sorted({
            row["capability"] for row in delivered_preservation})
        lesson_control["fragile_preservation_patterns"] = sorted({
            row["capability"] + ":" + "".join("1" if value else "0" for value in row["operand_truths"])
            for row in delivered_preservation})
        lesson_control["fragile_preservation_source"] = "FRESH_SOURCE_TRUTH_TABLE_SIBLINGS"
        lesson_control["retention_support_requested"] = len(retention_support)
        lesson_control["retention_support_delivered"] = len(delivered_retention_support)
        lesson_control["retention_support_capabilities"] = sorted({
            row["capability"] for row in delivered_retention_support})
        lesson_control["retention_support_source"] = "FRESH_SOURCE_FAMILY"
        s.policy_control_receipts.append(lesson_control)
    for row in window:
        identity = row["id"]
        s.miss_exposures[identity] = s.miss_exposures.get(identity, 0) + 1
    s.replayed_misses += len(window)
    with d._runtime_timing_trace.trace_span(
            "STEP_DIAGNOSTIC_AND_GUIDANCE", capability=s.cap, visit_step=step + 1):
        if s.methodology_unavailable is None:
            try:
                offered, delivered = d._methodology_lesson_rows(s.cap, fresh, s.priority, picked)
                s.methodology_steps.append(d._diagnostics_teaching.inspect_lesson_step(
                    s.executable_release.curriculum, s.cap, offered, delivered))
            except ValueError as exc:
                s.methodology_unavailable = str(exc)
        typed_lesson = any(row.get("answer_kind", "binary") != "binary" for row in picked)
        if s.learning_settings is not None and typed_lesson:
            guidance = d._learning_lesson_guidance._typed_confidence_guidance(
                s.mx, (*s.confidence_champions, *s.frozen_soups), picked, s.receipt["config"],
                scope_size=len(s.executable_release.execution_plan.capabilities),
                teacher_distill=float(s.policy.get("distill", 0.0)), lesson_grade=s.lesson_grade)
        else:
            guidance = d._learning_lesson_guidance._confidence_guidance(
                s.mx, (*s.confidence_champions, *s.frozen_soups), picked, s.receipt["config"],
                s.receipt["answer_ids"], scope_size=len(s.executable_release.execution_plan.capabilities),
                teacher_distill=float(s.policy.get("distill", 0.0)), lesson_grade=s.lesson_grade)
    if guidance is not None:
        import numpy as np
        influences = ([item[1] for item in guidance.values()]
                      if isinstance(guidance, dict) else [guidance[1]])
        s.confidence_examples += sum(int(np.count_nonzero(item)) for item in influences)
        s.confidence_total_weight += sum(float(np.sum(item)) for item in influences)
        s.confidence_applied_steps += 1
    training_rows = [*picked, *enrichment_rows]
    if s.autonomy_teaching_option is not None:
        s.delivered_autonomy_rows.extend(
            row for row in training_rows if row.get("id") in s.autonomy_option_specimen_ids)
    training_guidance = d._extend_binary_guidance(guidance, enrichment_rows)
    s.capture.delivery(
        s.executable_release, s.cap, step + 1, training_rows, option_rows=option_rows,
        priority=window, preservation=delivered_preservation,
        support=delivered_retention_support, enrichment=enrichment_rows,
        prior=prior if s.learning_settings is not None else (),
        mentors={"champion_shas": [item.get("checkpoint_sha256") for item in s.confidence_champions],
                 "soups": s.soup_vote_receipts, "distill": s.policy.get("distill")},
        guidance=training_guidance, controls=lesson_control, seed=lesson_seed)
    return training_rows, training_guidance
