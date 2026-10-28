"""Source-grounded teaching visits and retained candidate execution."""
from __future__ import annotations

import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.diagnostics.teaching as _diagnostics_teaching
import bilqis_mlx.factory.schedule as _factory_schedule
import bilqis_mlx.learning.champion_confidence as _learning_champion_confidence
import bilqis_mlx.mature_debt as _mature_debt
import bilqis_mlx.learning.championship_runtime as _learning_championship_runtime
import bilqis_mlx.learning.learning_experiment as _learning_learning_experiment
import bilqis_mlx.learning.lesson_guidance as _learning_lesson_guidance
import bilqis_mlx.learning.plasticity_escape as _learning_plasticity_escape
import bilqis_mlx.learning.stagnation_control as _learning_stagnation_control
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.learning.teacher_feedback as _learning_teacher_feedback
import bilqis_mlx.learning.teacher_multifidelity as _learning_teacher_multifidelity
import bilqis_mlx.learning.teacher_strategy_population as _learning_teacher_strategy_population
import bilqis_mlx.profiles.catalog as _profiles_catalog
import bilqis_mlx.profiles.retention as _profiles_retention
import bilqis_mlx.runtime.admission as _runtime_admission
import bilqis_mlx.runtime.assessment as _runtime_assessment
import bilqis_mlx.runtime.candidate_evidence as _runtime_candidate_evidence
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.runtime.timing_trace as _runtime_timing_trace
from .teacher_policy_selection import select_visit_policy as _select_visit_policy
from .teacher_observation_capture import ObservationCapture
import bilqis_mlx.source_adapters.school as _source_adapters_school
import dataclasses as _dataclasses
import json as _json
import pathlib as _pathlib
import random as _random


RETENTION_REQUIRES_ACTIVE_GRADE_ERROR = "RETENTION_REQUIRES_ACTIVE_GRADE"
TEACHER_EXPOSURE_HISTORY_INVALID = "TEACHER_EXPOSURE_HISTORY_INVALID"


def _retention_frontier_grade(school) -> str:
    """Return the latest admitted grade that anchors aggregate retention."""
    active = tuple(school.active_grades)
    if not active:
        raise ValueError(RETENTION_REQUIRES_ACTIVE_GRADE_ERROR)
    return active[-1]


def _teacher_exposures_after_candidate(receipt: dict, attempted: dict,
                                       *, decision: str) -> dict:
    """Preserve teacher-observed target exposure even when neural state rejects.

    Candidate weights and native AdamW are disposable. Which source-grounded
    unresolved rows the teacher actually delivered is observation history and
    must survive a rejected candidate so least-exposed targeting can rotate.
    """
    if decision not in {"REJECT", "PROVISIONAL"}:
        raise ValueError(TEACHER_EXPOSURE_HISTORY_INVALID)
    prior = receipt.get("teacher_miss_exposures", {})
    if (not isinstance(prior, dict) or not isinstance(attempted, dict) or
            any(not isinstance(identity, str) or type(count) is not int or count < 0
                for mapping in (prior, attempted)
                for identity, count in mapping.items())):
        raise ValueError(TEACHER_EXPOSURE_HISTORY_INVALID)
    if any(attempted.get(identity, 0) < count
           for identity, count in prior.items()):
        raise ValueError(TEACHER_EXPOSURE_HISTORY_INVALID)
    return dict(attempted)


def _teaching_enrichment_rows(source_root, graph, course, capability, *,
                              seed: int, enabled: bool, release=None):
    """Ask the capability's source adapter for optional source-grounded teaching."""
    if release is not None:
        from bilqis_mlx.factory.teaching import optional_teaching_rows
        return optional_teaching_rows(source_root, graph, release, _source_adapters_school.live_source_registry(),
            capability=capability, seed=seed, enabled=enabled)
    return _source_adapters_school.live_source_registry().optional_teaching_rows(
        course, capability=capability, source_root=source_root, graph=graph,
        seed=seed, enabled=enabled)


def _extend_binary_guidance(guidance, rows):
    """Keep existing mentor advice on the selected lesson; add zero-weight bridge rows."""
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


def _skip_perfect_target_visit(run_dir, receipt, school, course, capability,
                               probe_total, optimizer_step, *, teacher=None):
    """Advance the in-memory schedule without checkpointing a provisional model."""
    skipped_school = _curriculum_scheduler.visit(_runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school, capability, school.current_student)
    result = _runtime_checkpoints._advance(run_dir, receipt, skipped_school, teacher=teacher, persist=False)
    event = {
        "event": "SCHOOL_PERFECT_TARGET_VISIT_SKIPPED",
        "capability": capability,
        "grade": capability.partition(".")[0],
        "active_grade": skipped_school.grade,
        "generation": result["generation"],
        "optimizer_step": optimizer_step,
        "target_probe_correct": probe_total,
        "target_probe_total": probe_total,
        "retained_optimizer_updates": 0,
        "reason": "NO_POSSIBLE_STRICT_TARGET_GAIN",
    }
    result["_pending_visit_events"] = [
        *receipt.get("_pending_visit_events", ()), event]
    return result


def _skip_stagnant_target_visit(run_dir, receipt, school, course, capability,
                                optimizer_step):
    """Advance past a current-session quarantined capability without teaching."""
    skipped_school = _curriculum_scheduler.visit(_runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school, capability, school.current_student)
    result = _runtime_checkpoints._advance(run_dir, receipt, skipped_school, persist=False)
    event = {
        "event": "SCHOOL_STAGNANT_CAPABILITY_VISIT_SKIPPED",
        "capability": capability,
        "grade": capability.partition(".")[0],
        "active_grade": skipped_school.grade,
        "generation": result["generation"],
        "optimizer_step": optimizer_step,
        "retained_optimizer_updates": 0,
        "teacher_updated": False,
        "reason": "CURRENT_SESSION_STAGNATION_QUARANTINE",
        "required_mastery_debt": True,
    }
    result["_pending_visit_events"] = [
        *receipt.get("_pending_visit_events", ()), event]
    return result


def _selection_feedback(teacher, capability, curriculum_scope, policy,
                        outcome, before, after, context_credit):
    reward = after - before
    credit = _learning_learning_experiment.selection_credit(
        reward, outcome, context_credit)
    health = None if outcome is None else (
        _learning_teacher_strategy_population.durable_policy_cooldown_status(
            teacher.get("causal_experiment", {}), capability, curriculum_scope,
            _learning_teacher_strategy_population.effective_policy_key(policy)))
    return reward, credit, health


def _teacher_event_fields(policy_selection, policy_health):
    result = {
        "teacher_selection_policy": policy_selection["selection_policy"],
        "teacher_selection_reason": policy_selection["selection_reason"],
        "teacher_strategy_population": {
            key: policy_selection.get(key)
            for key in ("strategy_archive_count", "active_effective_strategy_count",
                        "active_effective_strategy_capacity",
                        "dormant_effective_strategy_count", "live_effective_strategy_count",
                        "strategy_population_capacity", "retired_effective_strategy_count",
                        "checkpoint_retired_effective_strategy_count", "realized_action_ecology_count")
            if policy_selection.get(key) is not None},
    }
    if policy_selection.get("mutation_parent_policy_key"):
        result["teacher_mutation_parent"] = {
            "policy_key": policy_selection["mutation_parent_policy_key"],
            "basis": policy_selection.get("mutation_parent_basis"),
            "changed_fields": policy_selection.get("mutation_changed_fields", []), "mode": policy_selection.get("mutation_mode"),
        }
    if policy_health and policy_health["active"]:
        result["teacher_policy_health"] = policy_health
    return result


def _take_visit(mx, run_dir, receipt, manifest, course, engine,
                params, optimizer, graph, *, steps_per_visit, batch_size, reserve_gib,
                source_root=None, learning_settings: _learning_learning_experiment.Settings | None = None,
                boolean_association_bridge: bool = False,
                source_prefetch_executor=None, source_prefetch_workers: int = 0,
                autonomy_teaching_option: str | None = None,
                capture_teacher_observations: bool = True):
    capture = ObservationCapture(run_dir, receipt, enabled=capture_teacher_observations)
    school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
    if (receipt.get("mentor_epoch") is not None and
            receipt.get("championship_school_identity") !=
            _learning_championship_runtime._live_championship_identity(receipt, course, graph, params)):
        raise ValueError("CHAMPIONSHIP_SCHOOL_IDENTITY_RESET_REQUIRED")
    cap = _curriculum_scheduler.next_capability(school)
    if cap is None:
        raise ValueError("HUMAN_TRAINER_NO_SCHEDULED_CAPABILITY")
    stage_before = school.stage
    _runtime_timing_trace.trace_mark(
        "VISIT_START", generation=receipt["generation"], capability=cap,
        phase=stage_before, optimizer_step=int(optimizer.state["step"].item()))
    if cap in set(_learning_stagnation_control.quarantined_capabilities(receipt.get("stagnation_session"))):
        return _skip_stagnant_target_visit(
            run_dir, receipt, school, course, cap,
            int(optimizer.state["step"].item()))
    introduction_pass = school.stage == "MAIN"
    lesson_grade = cap.split(".", 1)[0]
    executable_release = _runtime_admission._read_executable_factory_release_artifact(
        run_dir, receipt)
    program = _factory_schedule.schedule_program_from_executable_release(executable_release)
    if lesson_grade not in {grade.id for grade in program.grades}:
        raise ValueError("HUMAN_TRAINER_UNKNOWN_LESSON_GRADE")
    teacher = _json.loads(_runtime_state._canonical(receipt["teacher"]))
    rng = _random.Random(_runtime_state._seed(receipt, capability=cap))
    teacher_curriculum_scope = (str(receipt.get("curriculum_mode", "")) + "/" +
                                str(receipt.get("numeric_maximum", "")))
    plasticity_escape = _learning_plasticity_escape.activation(
        teacher, cap, teacher_curriculum_scope, school, program, receipt=receipt)
    candidate_steps = _learning_learning_experiment.candidate_step_budget(
        steps_per_visit, teacher, cap,
        curriculum_scope=teacher_curriculum_scope)
    if source_root is None:
        raise ValueError("HUMAN_TRAINER_LIVE_SOURCE_REQUIRED")
    with _runtime_timing_trace.trace_span("VISIT_SOURCE_DRAW", capability=cap):
        rows = _runtime_assessment._draw_live_rows(source_root, graph,
                               seed=_runtime_state._seed(receipt, capability=cap),
                               capability=cap, each=max(32, batch_size),
                               course=course, executable_release=executable_release)
    # Active maxed capability roles advise only inside their own grade.
    # Frozen grade soups remain the separately diluted cross-grade voice.
    confidence_champions, frozen_soups, soup_vote_receipts = _load_visit_mentors(
        run_dir, receipt, lesson_grade, graph, program, cap)
    confidence_examples = 0
    confidence_total_weight = 0.0
    confidence_applied_steps = 0
    direct_capability_votes, direct_capabilities = _direct_mentor_votes(confidence_champions)
    champion_candidates, champion_candidate_ids = _discover_champion_weakness(
        mx, confidence_champions, params, rows, receipt, cap)
    priority, deferred_misses, miss_exposures, warnings, previsit_diagnostics = (
        _prepare_visit_feedback(receipt, cap, champion_candidates, champion_candidate_ids))
    policy_key, policy, policy_selection = _select_visit_policy(
        engine, teacher, cap, school, rng, learning_settings,
        teacher_curriculum_scope, previsit_diagnostics, lesson_grade,
        len(_curriculum_scheduler.assessment_capabilities(program, school)))
    capture.select_option(cap, autonomy_teaching_option)
    capture.propose(executable_release, school, cap, policy_key, policy, policy_selection,
        configured_steps=steps_per_visit, effective_steps=candidate_steps, batch_size=batch_size,
        settings=learning_settings, enrichment=boolean_association_bridge, source_rows=rows,
        teacher=teacher, parent_optimizer_step=int(optimizer.state["step"].item()))
    original_learning_rate = optimizer.learning_rate
    optimizer.learning_rate = float(policy["lr"])
    # Teacher reward must measure transfer on the newly drawn source cohort,
    # not improvement on the exact historical misses that are separately
    # replayed inside optimizer batches below. Otherwise memorizing the replay
    # ledger looks like fresh capability acquisition to the policy learner.
    with _runtime_timing_trace.trace_span("TRAIN_SCORE_BEFORE", capability=cap, row_count=len(rows)):
        before = _learning_student_ops._train_score(mx, params, rows, receipt["config"],
                              receipt["answer_ids"])
    shadow_rungs = (
        _learning_teacher_multifidelity.active_rungs(
            _learning_teacher_multifidelity.DEFAULT_SHADOW_POLICY, candidate_steps)
        if learning_settings is not None else ())
    shadow_probes = []
    parent_parameters, parent_optimizer = params, optimizer
    probe_rows, protected_caps, parent_predictions, params, optimizer, skipped = (
        _prepare_retention_trial(
            mx, run_dir, receipt, course, school, cap, learning_settings,
            source_root, graph, executable_release, params, optimizer,
            original_learning_rate, teacher))
    if skipped is not None:
        capture.finish(skipped["_pending_visit_events"][-1], decision=None, paired=None,
            protected=None, stage="PERFECT_TARGET_SKIP", attempted=0, retained=0)
        return skipped
    last_loss = 0.0
    last_norm = 0.0
    methodology_steps = []
    methodology_unavailable = None
    replayed_misses = 0
    champion_prioritized = 0
    enrichment_examples = 0
    policy_control_receipts = []
    step_before = int(optimizer.state["step"].item())
    fragile_fixed_rows = ()
    if learning_settings is not None:
        from bilqis_mlx.learning.fragile_replay import load_replay_rows
        with _runtime_timing_trace.trace_span("FRAGILE_REPLAY_LOAD", capability=cap):
            fragile_fixed_rows = load_replay_rows(
                run_dir, receipt,
                capabilities=_profiles_retention.fragile_preservation_capabilities())
    old_capabilities, retention_support_capabilities = _visit_retention_scope(
        run_dir, receipt, course, school, cap, learning_settings)
    delivered_autonomy_rows = []
    autonomy_option_specimen_ids = set()
    prefetch_futures = {}
    prefetch_enabled = bool(
        learning_settings is not None and source_prefetch_executor is not None and
        source_prefetch_workers > 0 and autonomy_teaching_option is None)
    if prefetch_enabled:
        from bilqis_mlx.runtime.source_prefetch import SCHEMA as SOURCE_PREFETCH_SCHEMA, prepare_step_sources
        admitted = set(_curriculum_scheduler.assessment_capabilities(_runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school))
        fragile_requested = tuple(
            name for name in _profiles_retention.fragile_preservation_capabilities()
            if name in admitted)
        course_digest = course.digest()
        graph_digest = receipt.get("semantic_graph_sha256") or _runtime_state._fingerprint(graph)

        from .source_prefetch import visit_source_request

        def source_request(step_index):
            return visit_source_request(
                step_index, policy, old_capabilities, school, retention_support_capabilities,
                receipt, cap, fragile_requested, boolean_association_bridge,
                executable_release, course_digest, graph_digest, step_before,
                course, graph, source_root, batch_size, fragile_fixed_rows)

        def submit_source_request(step_index):
            request = source_request(step_index)
            _runtime_timing_trace.trace_mark(
                "STEP_SOURCE_PREFETCH_SUBMIT", capability=cap,
                visit_step=step_index + 1, identity=request["identity"])
            prefetch_futures[step_index] = (
                request, source_prefetch_executor.submit(prepare_step_sources, request))

        for step_index in range(min(source_prefetch_workers, candidate_steps)):
            submit_source_request(step_index)
    for step in range(candidate_steps):
        _runtime_timing_trace.trace_mark("OPTIMIZER_STEP_START", capability=cap, visit_step=step + 1,
                   optimizer_step=int(optimizer.state["step"].item()))
        lesson_control = None
        prepared = None
        if prefetch_enabled:
            request, future = prefetch_futures.pop(step)
            with _runtime_timing_trace.trace_span(
                    "STEP_SOURCE_PREFETCH_WAIT", capability=cap,
                    visit_step=step + 1, identity=request["identity"]):
                prepared = future.result()
            if (prepared.get("schema") != SOURCE_PREFETCH_SCHEMA or
                    prepared.get("identity") != request["identity"]):
                raise ValueError("HUMAN_TRAINER_SOURCE_PREFETCH_IDENTITY_DRIFT")
            next_step = step + source_prefetch_workers
            if next_step < candidate_steps:
                submit_source_request(next_step)
            fresh = list(prepared["fresh"])
        else:
            with _runtime_timing_trace.trace_span("STEP_SOURCE_DRAW", capability=cap, visit_step=step + 1):
                if autonomy_teaching_option is None:
                    fresh = _runtime_assessment._draw_live_rows(source_root, graph,
                        seed=_runtime_state._seed(receipt, capability=cap, step=step+1),
                        capability=cap, each=max(32, batch_size), course=course,
                        executable_release=executable_release)
                else:
                    from bilqis_mlx.factory.teaching import draw_teaching_option_rows
                    fresh = list(draw_teaching_option_rows(
                        source_root, graph, executable_release, _source_adapters_school.live_source_registry(),
                        capability=cap, option_id=autonomy_teaching_option,
                        seed=_runtime_state._seed(receipt, capability=cap, step=step+1),
                        each=max(32, batch_size)))
                    autonomy_option_specimen_ids.update(
                        row["id"] for row in fresh)
        option_rows = tuple(fresh)
        fresh.extend(priority)
        preservation = ()
        retention_support = ()
        if learning_settings is not None:
            if prepared is not None:
                preservation = tuple(prepared["preservation"])
                retention_support = tuple(prepared["retention_support"])
            else:
                with _runtime_timing_trace.trace_span("STEP_FRAGILE_PRESERVATION", capability=cap,
                                visit_step=step + 1):
                    preservation = _runtime_candidate_evidence._fresh_fragile_preservation_rows(
                        run_dir, source_root, graph, receipt, course, school, cap,
                        step=step + 1, batch_size=batch_size,
                        fixed_rows=fragile_fixed_rows,
                        executable_release=executable_release)
                if retention_support_capabilities:
                    support_capability = retention_support_capabilities[
                        (school.visits + step) %
                        len(retention_support_capabilities)]
                    with _runtime_timing_trace.trace_span(
                            "STEP_RETENTION_SUPPORT", capability=cap,
                            support_capability=support_capability,
                            visit_step=step + 1):
                        support_rows = _runtime_assessment._draw_live_rows(
                            source_root, graph, course=course,
                            executable_release=executable_release,
                            capability=support_capability,
                            each=max(batch_size, 6),
                            seed=_runtime_state._seed(
                                receipt,
                                capability="RETENTION_SUPPORT:" + support_capability,
                                step=step + 1))
                        retention_support = (
                            _runtime_candidate_evidence.
                            _select_fresh_retention_support_rows(
                                support_rows, rotation=school.visits + step))
        lesson_seed = _runtime_state._seed(receipt, capability=cap, step=step+1)
        with _runtime_timing_trace.trace_span("STEP_LESSON_SELECT", capability=cap, visit_step=step + 1):
            if learning_settings is not None:
                # The same source-bound old-grade policy applies to Boolean and
                # typed lessons. Never label the target's own grade as old.
                prior = list(prepared["prior"]) if prepared is not None else []
                if prepared is None and int(policy.get("old", 0)) > 0 and old_capabilities:
                    selected = old_capabilities[(school.visits + step) % len(old_capabilities)]
                    prior = _runtime_assessment._draw_live_rows(source_root, graph, course=course,
                        executable_release=executable_release,
                        capability=selected, each=max(batch_size, 6),
                        seed=_runtime_state._seed(receipt, capability="EXPERIMENT_OLD:"+selected, step=step))
                picked, control = _learning_learning_experiment.select_source_lesson(
                    fresh, prior, policy, seed=lesson_seed, batch_size=batch_size,
                    targets=priority, target_exposures=miss_exposures,
                    priority_target_ids=champion_candidate_ids,
                    reserved_support_slots=(
                        len(preservation) + len(retention_support)))
                lesson_control = {**control, "eligible_prior_capabilities":
                                  len(old_capabilities)}
                target_ids = set(control["weakness_target_ids"])
                window = [row for row in priority if row["id"] in target_ids]
                champion_prioritized += sum(
                    row["id"] in champion_candidate_ids for row in window)
            else:
                picked = _learning_lesson_guidance.choose_lesson_batch(
                    fresh, policy, lesson_seed, batch_size=batch_size)
                target_capacity = sum(row["capability"] == cap for row in picked)
                window = _learning_teacher_feedback.select_weakness_targets(
                    priority, _learning_teacher_feedback.WeaknessTargetRequest(
                        exposures=miss_exposures,
                        capacity=target_capacity))
                picked, delivered_targets = _learning_learning_experiment.reserve_weakness_targets(picked, window)
                window = list(delivered_targets)
                target_ids = {row["id"] for row in window}
        delivered_preservation = ()
        delivered_retention_support = ()
        if learning_settings is not None:
            fresh_support_ids = set(
                lesson_control.get("fresh_support_ids", ())
                if lesson_control is not None else ())
            support_rows = (*preservation, *retention_support)
            with _runtime_timing_trace.trace_span("STEP_FRAGILE_PRESERVATION_INJECT", capability=cap,
                            visit_step=step + 1):
                picked, delivered_support = _runtime_candidate_evidence._inject_preservation_rows(
                    picked, support_rows,
                    reserved_ids=target_ids | fresh_support_ids)
            fragile_ids = {row["id"] for row in preservation}
            retention_ids = {row["id"] for row in retention_support}
            delivered_preservation = tuple(
                row for row in delivered_support if row["id"] in fragile_ids)
            delivered_retention_support = tuple(
                row for row in delivered_support if row["id"] in retention_ids)
        if prepared is not None:
            enrichment_rows = tuple(prepared["teaching_enrichment_rows"])
        else:
            with _runtime_timing_trace.trace_span("STEP_TEACHING_ENRICHMENT", capability=cap, visit_step=step + 1):
                enrichment_rows = _teaching_enrichment_rows(
                    source_root, graph, course, cap,
                    seed=_runtime_state._seed(receipt, capability="TEACHING_ENRICHMENT:" + cap,
                               step=step + 1),
                    enabled=boolean_association_bridge, release=executable_release)
        enrichment_examples += len(enrichment_rows)
        if lesson_control is not None:
            lesson_control["planned_old_grade_examples"] = lesson_control[
                "effective_old_grade_examples"]
            earlier_grades = {item.partition(".")[0] for item in old_capabilities}
            lesson_control["effective_old_grade_examples"] = sum(
                row["capability"].partition(".")[0] in earlier_grades for row in picked)
            lesson_control["selected_answer_kinds"] = sorted({
                row.get("answer_kind", "binary") for row in picked})
            lesson_control["fragile_preservation_requested"] = len(preservation)
            lesson_control["fragile_preservation_delivered"] = len(
                delivered_preservation)
            lesson_control["fragile_preservation_capabilities"] = sorted({
                row["capability"] for row in delivered_preservation})
            lesson_control["fragile_preservation_patterns"] = sorted({
                row["capability"] + ":" +
                "".join("1" if value else "0" for value in row["operand_truths"])
                for row in delivered_preservation})
            lesson_control["fragile_preservation_source"] = (
                "FRESH_SOURCE_TRUTH_TABLE_SIBLINGS")
            lesson_control["retention_support_requested"] = len(
                retention_support)
            lesson_control["retention_support_delivered"] = len(
                delivered_retention_support)
            lesson_control["retention_support_capabilities"] = sorted({
                row["capability"] for row in delivered_retention_support})
            lesson_control["retention_support_source"] = (
                "FRESH_SOURCE_FAMILY")
            policy_control_receipts.append(lesson_control)
        for row in window:
            identity = row["id"]
            miss_exposures[identity] = miss_exposures.get(identity, 0) + 1
        replayed_misses += len(window)
        with _runtime_timing_trace.trace_span("STEP_DIAGNOSTIC_AND_GUIDANCE", capability=cap,
                        visit_step=step + 1):
            if methodology_unavailable is None:
                try:
                    methodology_steps.append(_diagnostics_teaching.inspect_lesson_step(
                        executable_release.curriculum, cap, fresh, picked))
                except ValueError as exc:
                    # A diagnostic implementation gap must not invent a new
                    # training gate or silently change the evolved teacher.
                    methodology_unavailable = str(exc)
            typed_lesson = any(row.get("answer_kind", "binary") != "binary" for row in picked)
            if learning_settings is not None and typed_lesson:
                guidance = _learning_lesson_guidance._typed_confidence_guidance(
                    mx, (*confidence_champions, *frozen_soups), picked, receipt["config"],
                    scope_size=len(executable_release.execution_plan.capabilities),
                    teacher_distill=float(policy.get("distill", 0.0)),
                    lesson_grade=lesson_grade)
            else:
                guidance = _learning_lesson_guidance._confidence_guidance(
                    mx, (*confidence_champions, *frozen_soups), picked, receipt["config"],
                    receipt["answer_ids"],
                    scope_size=len(executable_release.execution_plan.capabilities),
                    teacher_distill=float(policy.get("distill", 0.0)),
                    lesson_grade=lesson_grade)
        if guidance is not None:
            import numpy as np
            influences = ([item[1] for item in guidance.values()]
                          if isinstance(guidance, dict) else [guidance[1]])
            confidence_examples += sum(int(np.count_nonzero(item)) for item in influences)
            confidence_total_weight += sum(float(np.sum(item)) for item in influences)
            confidence_applied_steps += 1
        training_rows = [*picked, *enrichment_rows]
        if autonomy_teaching_option is not None:
            delivered_autonomy_rows.extend(
                row for row in training_rows
                if row.get("id") in autonomy_option_specimen_ids)
        training_guidance = _extend_binary_guidance(guidance, enrichment_rows)
        capture.delivery(executable_release, cap, step + 1, training_rows,
            option_rows=option_rows, priority=window, preservation=delivered_preservation,
            support=delivered_retention_support, enrichment=enrichment_rows,
            prior=prior if learning_settings is not None else (),
            mentors={"champion_shas": [item.get("checkpoint_sha256") for item in confidence_champions],
                     "soups": soup_vote_receipts, "distill": policy.get("distill")},
            guidance=training_guidance, controls=lesson_control, seed=lesson_seed)
        with _runtime_timing_trace.trace_span("STEP_TRAIN", capability=cap, visit_step=step + 1,
                        batch_size=len(training_rows)):
            last_loss, last_norm = _learning_student_ops._train_step(
                mx, params, optimizer, training_rows, receipt["config"],
                receipt["answer_ids"], champion_guidance=training_guidance)
        rung = step + 1
        if shadow_rungs and rung in shadow_rungs and rung < candidate_steps:
            with _runtime_timing_trace.trace_span(
                    "TEACHER_SHADOW_RUNG", capability=cap, visit_step=rung):
                rung_score = _learning_student_ops._train_score(
                    mx, params, rows, receipt["config"], receipt["answer_ids"])
            shadow_probes.append((rung, rung_score - before))
        _runtime_timing_trace.trace_mark("OPTIMIZER_STEP_END", capability=cap, visit_step=step + 1,
                   optimizer_step=int(optimizer.state["step"].item()))
    with _runtime_timing_trace.trace_span("TRAIN_SCORE_AFTER", capability=cap, row_count=len(rows)):
        after = _learning_student_ops._train_score(mx, params, rows, receipt["config"],
                             receipt["answer_ids"])
    attempted_step = int(optimizer.state["step"].item())
    if attempted_step != step_before+candidate_steps:
        raise ValueError("HUMAN_TRAINER_OPTIMIZER_STEP_DRIFT")
    candidate_gain = after-before
    if shadow_rungs:
        shadow_probes.append((candidate_steps, candidate_gain))
    realized_action = (
        _learning_learning_experiment.realized_teacher_action(
            policy, candidate_steps=candidate_steps, batch_size=batch_size,
            policy_controls=policy_control_receipts,
            guidance_applied_steps=confidence_applied_steps,
            enrichment_examples=enrichment_examples)
        if learning_settings is not None else None)
    outcome = context_credit = None
    if learning_settings is not None:
        with _runtime_timing_trace.trace_span("RETENTION_CANDIDATE_EVIDENCE", capability=cap):
            pair, probed, current_grade, fixed_grade_evidence, replay, frontier, stage = (
                _runtime_candidate_evidence._candidate_grade_evidence(
                    mx, run_dir, receipt, course, school, cap,
                    parent_parameters, params, probe_rows,
                    parent_predictions, learning_settings, plasticity_escape))
        with _runtime_timing_trace.trace_span("RETENTION_DECIDE", capability=cap):
            outcome = _learning_learning_experiment.decide(
                pair, active_capability=cap, phase=school.stage,
                protected=probed, settings=learning_settings,
                same_grade_capabilities=current_grade,
                fixed_grade_replay=fixed_grade_evidence,
                fixed_frontier_replay=frontier,
                protected_frontier_grade=_retention_frontier_grade(school),
                mature_grades=frozenset(school.champions), mature_grade_debt=_mature_debt.as_mapping(school),
                negative_prototypes=teacher["causal_experiment"]["negative_archetypes"],
                source_cohort_sha256=_runtime_state._fingerprint([
                    (r["id"],r["capability"],r["gold"],r["tokens"]) for r in probe_rows
                    if r["capability"] in pair]),
                fragile_replay=replay, plasticity_escape=plasticity_escape)
        outcome["qualification_stage"] = stage
        from bilqis_mlx.learning.matrix_strain import observe as observe_matrix_strain
        with _runtime_timing_trace.trace_span("MATRIX_STRAIN", capability=cap):
            outcome["matrix_strain"] = observe_matrix_strain(
                mx, run_dir, receipt, parent_parameters, params)
        outcome["unsampled_admitted_capabilities"] = (
            len(set(_curriculum_scheduler.assessment_capabilities(_runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school)) | {cap})-len(pair))
        with _runtime_timing_trace.trace_span("RETENTION_APPLY_DECISION", capability=cap,
                        decision=outcome["decision"]):
            context_credit = _learning_learning_experiment.observe_context(
                teacher, capability=cap, phase=school.stage, policy_key=policy_key,
                decision=outcome, local_gain=candidate_gain,
                curriculum_scope=teacher_curriculum_scope,
                diagnostics=previsit_diagnostics,
                realized_action=realized_action,
                student_checkpoint_sha256=school.current_student.sha256)
            if outcome["decision"] == "PROVISIONAL":
                _learning_learning_experiment.commit_trial(parent_parameters, parent_optimizer, params, optimizer)
            else:
                # The rejected candidate never owned the causal model, its
                # optimizer or the unresolved miss queue. Teacher-observed
                # target exposure is not neural state and remains durable.
                parent_optimizer.learning_rate = original_learning_rate
                miss_exposures = _teacher_exposures_after_candidate(
                    receipt, miss_exposures, decision=outcome["decision"])
                after = before
        params, optimizer = parent_parameters, parent_optimizer
    remaining_priority = priority
    if priority and (outcome is None or outcome["decision"] == "PROVISIONAL"):
        with _runtime_timing_trace.trace_span("MISS_RECONCILE", capability=cap, miss_count=len(priority)):
            miss_guesses = _learning_student_ops._predictions(
                mx, params, priority, receipt["config"], receipt["answer_ids"])
            remaining_priority = _learning_teacher_feedback.reconcile_unresolved_misses(
                priority, priority, miss_guesses)
    remaining_priority_ids = {row["id"] for row in remaining_priority}
    resolved_priority_ids = {row["id"] for row in priority} - remaining_priority_ids
    for identity in resolved_priority_ids:
        miss_exposures.pop(identity, None)
    all_teacher_misses = [
        row for row in receipt.get("teacher_misses", ())
        if row["capability"] != cap
    ] + deferred_misses + remaining_priority
    all_teacher_misses.sort(key=lambda row: (row["capability"], row["id"]))
    reward, bandit_credit, policy_health = _selection_feedback(teacher, cap, teacher_curriculum_scope, policy, outcome, before, after, context_credit)
    with _runtime_timing_trace.trace_span("TEACHER_OBSERVE", capability=cap):
        engine.observe(teacher, lesson_grade, policy_key, bandit_credit)
    _learning_plasticity_escape.record_school_visit(
        teacher, retained=bool(outcome and outcome["decision"] == "PROVISIONAL"))
    expected_retained = (step_before if outcome is not None and
                         outcome["decision"] == "REJECT" else attempted_step)
    attempted_optimizer_updates = attempted_step - step_before
    retained_optimizer_updates = expected_retained - step_before
    if attempted_optimizer_updates < 0:
        raise ValueError("HUMAN_TRAINER_ATTEMPTED_OPTIMIZER_STEP_REGRESSION")
    if retained_optimizer_updates < 0:
        raise ValueError("HUMAN_TRAINER_RETAINED_OPTIMIZER_STEP_REGRESSION")
    if int(optimizer.state["step"].item()) != expected_retained:
        raise ValueError("LEARNING_EXPERIMENT_RETAINED_ADAMW_STEP_DRIFT")
    # No new archive exists yet. The retained checkpoint is the last complete
    # recovery point, NOT a representation of these newly updated RAM weights.
    school = _curriculum_scheduler.visit(_runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school, cap, school.current_student, retention_frontier=_mature_debt.retained_frontier(outcome))
    methodology = _diagnostics_teaching.summarize_teaching_visit(
        course, cap, tuple(methodology_steps),
        introductory=introduction_pass,
        unmeasured_reason=methodology_unavailable)
    teacher_decision = _learning_teacher_feedback.summarize_teacher_decision(_learning_teacher_feedback.TeacherDecisionInput(
        capability=cap, policy_key=policy_key, warnings=warnings,
        unresolved_miss_count=len(priority),
        champion_candidate_count=len(champion_candidate_ids),
        prerequisite_capabilities=(
            executable_release.execution_plan.capability_map[cap].prerequisites),
        methodology=methodology,
        delivered_examples=candidate_steps*batch_size,
        replayed_misses=replayed_misses,
        resolved_exam_misses=len(resolved_priority_ids),
        champion_prioritized=champion_prioritized,
        seed=_runtime_state._seed(receipt, capability=cap),
        diagnostic_context_consumed=policy_selection[
            "diagnostic_context_consumed"],
        diagnostic_context_key=policy_selection["diagnostic_context_key"],
    ))
    lesson_generator, lesson_source_digest = _runtime_assessment.released_lesson_source_identity(
        executable_release, cap)
    event = {
        "event": "SCHOOL_TEACHER_VISIT_COMMITTED",
        "grade": lesson_grade,
        "active_grade": school.grade,
        "generation": receipt["generation"] + 1,
        "capability": cap, "teacher_policy": policy_key,
        "strategy": policy, "loss": last_loss, "gradient_norm": last_norm,
        "source_training_accuracy_before": before,
        "source_training_accuracy_after": after,
        "teacher_reward": reward,
        "teacher_selection_reward": bandit_credit,
        **_teacher_event_fields(policy_selection, policy_health),
        **({"realized_teacher_action": realized_action}
           if realized_action is not None else {}),
        "attempted_optimizer_updates": attempted_optimizer_updates,
        "candidate_step_control": {
            "configured_steps": steps_per_visit,
            "effective_steps": candidate_steps,
            "adaptive": candidate_steps != steps_per_visit,
        },
        "source_prefetch": {
            "schema": "bilqis.mlx.source-prefetch/v1",
            "mode": "PROCESS_POOL" if prefetch_enabled else "SERIAL",
            "workers": source_prefetch_workers if prefetch_enabled else 0,
            "prepared_steps": candidate_steps if prefetch_enabled else 0,
            "serial_steps": 0 if prefetch_enabled else candidate_steps,
            "packet_identity_verified": prefetch_enabled,
            "neural_owner": "MAIN_LANE_ONLY",
        },
        **({"teaching_enrichment": {
            "enabled": True,
            "active_for_visit": len(executable_release.execution_plan.capability_map[cap].teaching_option_ids) > 1,
            "option_ids": list(executable_release.execution_plan.capability_map[cap].teaching_option_ids[1:]),
            "delivered_examples": enrichment_examples,
            "exam_rubric_changed": False,
        }} if boolean_association_bridge else {}),
        **({"lesson_policy_controls": {
            "optimizer_batches_observed": len(policy_control_receipts),
            "old_grade_examples_delivered": sum(
                r["effective_old_grade_examples"] for r in policy_control_receipts),
            "last_batch_controls": policy_control_receipts[-1]}}
           if policy_control_receipts else {}),
        **({"typed_policy_controls": {
            "optimizer_batches_observed": len(policy_control_receipts),
            "old_grade_examples_delivered": sum(
                r["effective_old_grade_examples"] for r in policy_control_receipts),
            "last_batch_controls": policy_control_receipts[-1]}}
           if policy_control_receipts and any(
               kind != "binary" for r in policy_control_receipts
               for kind in r["selected_answer_kinds"]) else {}),
        **({"candidate_retention": outcome, "context_teacher_credit": context_credit,
            "candidate_source_training_gain": candidate_gain,
            "candidate_attempt_optimizer_step": attempted_step,
            "retained_optimizer_updates": retained_optimizer_updates}
           if outcome is not None else {}),
        "generator_version": lesson_generator,
        "generator_code_sha256": lesson_source_digest,
        "lesson_source_sha256": manifest["manifest_sha256"],
        "lesson_seed": _runtime_state._seed(receipt, capability=cap),
        "prior_exam_misses_available": len(priority),
        "prior_exam_misses_deferred_by_scope": len(deferred_misses),
        "prior_exam_misses_remaining": len(remaining_priority),
        "prior_grade_champion_votes": {
            source_grade: votes for source_grade, votes in direct_capability_votes.items()
            if source_grade != lesson_grade},
        "champion_directed_examples_available": len(champion_candidate_ids),
        "champion_confidence": {
            "policy": _learning_champion_confidence.POLICY,
            "frozen_unique_champions": len(confidence_champions),
            "direct_capability_votes": dict(sorted(direct_capability_votes.items())),
            "direct_capabilities": sorted(direct_capabilities),
            "frozen_grade_soups": list(soup_vote_receipts),
            "teacher_distill": float(policy.get("distill", 0.0)),
            "examples_with_gold_agreeing_advice": confidence_examples,
            "total_per_row_influence": round(confidence_total_weight, 8),
            "guided_optimizer_steps": confidence_applied_steps,
        },
        "lesson_methodology": methodology,
        "teacher_decision": teacher_decision,
        "optimizer_step": int(optimizer.state["step"].item()),
        "next_phase": school.stage,
        "checkpoint_status": "PROVISIONAL_UNTIL_NEXT_RECOVERY_BOUNDARY",
        "unavailable_teacher_dimensions": (
            (["old"] if not any(r["eligible_prior_capabilities"]
                                  for r in policy_control_receipts) else []) +
            ["preview"] + ([] if confidence_applied_steps else ["distill"])),
    }
    if autonomy_teaching_option is not None and delivered_autonomy_rows:
        from bilqis_mlx.factory.teaching import describe_delivered_teaching
        delivery = describe_delivered_teaching(
            executable_release, cap, autonomy_teaching_option,
            delivered_autonomy_rows)
        teaching_file = ("autonomy/teaching/" + delivery.specimen_content_sha256 + ".json")
        _runtime_state._durable_json(run_dir / teaching_file, {"rows": delivered_autonomy_rows})
        event["autonomy_teaching"] = {**_dataclasses.asdict(delivery), "specimen_file": teaching_file}
    shadow_review = shadow_activation = None
    if learning_settings is not None and outcome is not None:
        shadow_review = _learning_teacher_multifidelity.evaluate_shadow(
            _learning_teacher_multifidelity.DEFAULT_SHADOW_POLICY,
            probes=shadow_probes,
            final_retained=outcome["decision"] == "PROVISIONAL",
            full_budget_steps=candidate_steps)
        shadow_activation = _learning_teacher_multifidelity.record_review(
            teacher, shadow_review)
        event["teacher_multifidelity_shadow"] = shadow_review
        event["teacher_multifidelity_activation"] = shadow_activation
    capture.finish(event, decision=outcome,
        paired=pair if learning_settings is not None else None,
        protected=probed if learning_settings is not None else None,
        stage=stage if learning_settings is not None else "UNPROTECTED_VISIT",
        attempted=attempted_optimizer_updates, retained=retained_optimizer_updates,
        shadow_review=shadow_review, shadow_activation=shadow_activation)
    stagnation = receipt.get("stagnation_session")
    if stagnation is not None:
        stagnation = _learning_stagnation_control.record_visit(
            stagnation, capability=cap, phase=stage_before,
            decision=outcome.get("decision") if isinstance(outcome, dict) else None,
            retained_optimizer_updates=retained_optimizer_updates,
            generation=event["generation"])
    pending = list(receipt.get("_pending_visit_events", ()))
    pending.append(event)
    with _runtime_timing_trace.trace_span("VISIT_ADVANCE_STATE", capability=cap):
        result = _runtime_checkpoints._advance(run_dir, receipt, school, teacher=teacher, persist=False)
    if retained_optimizer_updates > 0:
        result["last_retained_update_grade"] = lesson_grade
    if learning_settings is not None:
        result["learning_experiment"] = {
            "version": _learning_learning_experiment.VERSION,
            "settings": _dataclasses.asdict(learning_settings),
        }
    result["teacher_misses"] = all_teacher_misses
    result["teacher_miss_exposures"] = miss_exposures
    if stagnation is not None:
        result["stagnation_session"] = stagnation
    result.pop("teacher_miss_cursor", None)
    result["_pending_visit_events"] = pending
    _runtime_timing_trace.trace_mark(
        "VISIT_END", generation=result["generation"], capability=cap,
        optimizer_step=int(optimizer.state["step"].item()),
        decision=outcome.get("decision") if isinstance(outcome, dict) else None)
    return result


def _prepare_visit_feedback(receipt, cap, champion_candidates, champion_candidate_ids):
    """Prepare source-verified replay and observed diagnostics before policy selection."""
    # Every unsuccessful examination construction can become direct teaching
    # material once scoring has completed. No held-out embargo survives.
    priority = [r for r in receipt.get("teacher_misses", ())
                if r["capability"] == cap]
    deferred_misses = []
    if receipt.get("numeric_maximum") is not None:
        priority, deferred_misses = _profiles_catalog.partition_numeric_scope(
            priority, receipt["numeric_maximum"])
    priority_ids = {row["id"] for row in priority}
    priority.extend(
        row for row in champion_candidates if row["id"] not in priority_ids)
    miss_exposures = dict(receipt.get("teacher_miss_exposures", {}))
    if any(type(count) is not int or count < 0 for count in miss_exposures.values()):
        raise ValueError("HUMAN_TRAINER_MISS_EXPOSURE_STATE_INVALID")
    previous_methodology = next((
        member.get("lesson_methodology")
        for member in reversed(receipt.get("delivery_outbox", ()))
        if member.get("capability") == cap and "lesson_methodology" in member
    ), None)
    warnings = _learning_teacher_feedback.active_warning_signals(
        receipt.get("last_exam"), previous_methodology, cap)
    previsit_diagnostics = {
        "warnings": warnings,
        "unresolved_miss_count": len(priority),
        "champion_candidate_count": len(champion_candidate_ids),
    }
    return priority, deferred_misses, miss_exposures, warnings, previsit_diagnostics


def _direct_mentor_votes(confidence_champions):
    """Summarize existing mentor votes for the visit receipt."""
    direct_capability_votes = {}
    direct_capabilities = []
    for mentor in confidence_champions:
        for source_grade, votes in mentor.get("source_grade_votes", {}).items():
            direct_capability_votes[source_grade] = (
                direct_capability_votes.get(source_grade, 0) + votes)
        direct_capabilities.extend(mentor.get("capabilities", ()))
    return direct_capability_votes, direct_capabilities


def _visit_retention_scope(run_dir, receipt, course, school, cap, learning_settings):
    """Resolve admitted prior-grade and support scopes without changing policy."""
    old_capabilities = (
        _learning_learning_experiment.earlier_grade_capabilities(
            _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school.champions,
            cap, carried_mastery_debt=getattr(school, "carried_mastery_debt", ()))
        if learning_settings is not None else ())
    retention_support_capabilities = ()
    if (learning_settings is not None and
            getattr(school, "active_grades", ()) and
            getattr(school, "schema", None) is not None):
        admitted_for_support = _curriculum_scheduler.assessment_capabilities(
            _runtime_release_adoption._schedule_for_receipt(
                run_dir, receipt, course), school)
        retention_support_capabilities = (
            _runtime_candidate_evidence._retention_support_capabilities(
                admitted_for_support, getattr(school, "active_grades", ()), cap))
    return old_capabilities, retention_support_capabilities




def _prepare_retention_trial(mx, run_dir, receipt, course, school, cap, learning_settings, source_root, graph, executable_release, params, optimizer, original_learning_rate, teacher):
    parent_parameters, parent_optimizer = params, optimizer
    probe_rows = protected_caps = parent_predictions = None
    if learning_settings is not None:
        with _runtime_timing_trace.trace_span("RETENTION_PROBE_BUILD", capability=cap):
            probe_rows, protected_caps, unsampled_caps = _runtime_candidate_evidence._learning_probe_rows(
                source_root, graph, receipt, course, school, cap, learning_settings,
                schedule_program=_runtime_release_adoption._schedule_for_receipt(
                    run_dir, receipt, course),
                executable_release=executable_release)
        target_rows = [row for row in probe_rows if row["capability"] == cap]
        with _runtime_timing_trace.trace_span("RETENTION_PARENT_PREDICT", capability=cap,
                        row_count=len(target_rows)):
            parent_predictions = _learning_student_ops._predictions(
                mx, parent_parameters, target_rows, receipt["config"], receipt["answer_ids"])
        if target_rows and all(parent_predictions[row["id"]] == row["gold"]
                               for row in target_rows):
            # A strict positive-gain gate cannot admit a trial whose fresh
            # target panel already scores perfectly. Preserve any accepted
            # in-memory student updates until their normal checkpoint boundary.
            parent_optimizer.learning_rate = original_learning_rate
            skipped = _skip_perfect_target_visit(
                run_dir, receipt, school, course, cap, len(target_rows),
                int(parent_optimizer.state["step"].item()), teacher=teacher)
            return probe_rows, protected_caps, parent_predictions, params, optimizer, skipped
        with _runtime_timing_trace.trace_span("FORK_CANDIDATE", capability=cap):
            params, optimizer = _learning_learning_experiment.fork_student(mx, parent_parameters, parent_optimizer)
    return probe_rows, protected_caps, parent_predictions, params, optimizer, None


def _discover_champion_weakness(mx, confidence_champions, params, rows, receipt, cap):
    with _runtime_timing_trace.trace_span(
            "CHAMPION_WEAKNESS_DISCOVERY", capability=cap):
        champion_candidates = _learning_lesson_guidance._champion_directed_rows(
            mx, confidence_champions, params, rows, receipt["config"],
            receipt["answer_ids"])
    champion_candidate_ids = {row["id"] for row in champion_candidates}
    return champion_candidates, champion_candidate_ids


def _load_visit_mentors(run_dir, receipt, lesson_grade, graph, program, cap):
    with _runtime_timing_trace.trace_span("MENTOR_SOURCES_LOAD", capability=cap):
        confidence_champions, frozen_soups, soup_vote_receipts = _learning_lesson_guidance._mentor_sources_for_visit(
            run_dir, receipt, lesson_grade, graph, len(program.grades))
    return confidence_champions, frozen_soups, soup_vote_receipts
