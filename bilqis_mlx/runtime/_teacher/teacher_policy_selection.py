"""Runtime adapter for contextual teacher selection and bounded vNext canaries."""
from __future__ import annotations

import bilqis_mlx.learning.learning_experiment as _learning_experiment
import bilqis_mlx.learning.teacher_breeding as _teacher_breeding
import bilqis_mlx.learning.teacher_strategy_population as _strategy_population
import bilqis_mlx.learning.teacher_vnext_replay as _teacher_vnext
import bilqis_mlx.runtime.timing_trace as _timing_trace


def _policy_evidence_before(teacher, scope, policy):
    effective_key = _strategy_population.effective_policy_key(policy)
    evidence = _strategy_population.effective_context_scope(teacher, scope).get(
        effective_key, {})
    trials = int(evidence.get("trials", 0))
    retained = int(evidence.get("retained", 0))
    record = {
        "schema": "bilqis.bamf.teacher-policy-evidence/v1",
        "evidence_level": "EXACT_CONTEXT",
        "effective_policy_key": effective_key,
        "trials": trials,
        "retained": retained,
    }
    if trials >= _teacher_vnext.MINIMUM_EVIDENCE_OBSERVATIONS:
        record["retention_probability"] = retained / trials
    return record


def _canary_decision(teacher, cap, school, rng, teacher_curriculum_scope,
                     lesson_grade, total_capabilities, legacy_reason):
    """Compute the vNext decision only from the population it can actually use."""
    context_key = cap + "|" + school.stage + "|" + teacher_curriculum_scope
    channel = teacher.get("causal_experiment", {})
    scope = channel.get("contexts", {}).get(context_key, {})
    bypass_status = {
        "FRESH_MUTATED_CHALLENGER": "BYPASSED_BESPOKE_EXPLORATION",
        "PORTABLE_RETAINED_CHALLENGER": "BYPASSED_PORTABLE_RETAINED_CHALLENGER",
        "PLASTICITY_RETRY": "BYPASSED_PLASTICITY_RETRY",
    }.get(legacy_reason)
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import strict_mode_enabled
    # Legacy population ranking mutates its live inventory. BAMF's fixed
    # population pass is read-only and cannot affect a bypassed canary.
    if (bypass_status is None or strict_mode_enabled()
            or teacher.get("selection_contract") != _strategy_population.BAMF_SUCCESSOR_SELECTION):
        active, inventory, _retired = _teacher_breeding.selection_population(
            teacher, grade=lesson_grade, capability=cap,
            curriculum_scope=teacher_curriculum_scope, scope=scope, channel=channel,
            context_key=context_key, student_checkpoint_sha256=school.current_student.sha256,
            total_capabilities=total_capabilities)
        sibling_penalties = {
            effective: penalty for effective in active
            if (penalty := _strategy_population.sibling_cooldown_penalty(
                channel, cap, teacher_curriculum_scope, effective)) > 0
        }
    ordinal = int(channel.get("events", 0)) + 1
    if bypass_status is not None:
        canary = {
            "schema": _teacher_vnext.SCHEMA,
            "policy_version": "teacher-vnext-canary/v1",
            "candidate_ordinal": ordinal, "scheduled": False,
            "actual_authority_changed": False,
            "status": bypass_status,
            "policy_key": None,
        }
    else:
        canary = _teacher_vnext.select_canary(
            teacher, capability=cap, phase=school.stage,
            curriculum_scope=teacher_curriculum_scope,
            candidate_ordinal=ordinal, rng=rng,
            active_effective_policy_keys=active, inventory=inventory,
            effective_policy_penalties=sibling_penalties)
    return canary


def ordinary_previsit_diagnostics(option, *, structural_debt):
    """Project bounded diagnostic categories from already-issued evidence."""
    competence = getattr(option, "competence", None)

    def deficit(score):
        return None if score is None else score.correct < score.total

    return {"native_previsit": {
        "fixed_reference_deficit": deficit(getattr(competence, "reference", None)),
        "target_sample_deficit": deficit(getattr(competence, "target", None)),
        "reference_conflict": bool(getattr(competence, "reference_conflict", False)),
        "structural_debt": structural_debt,
    }}


def select_visit_policy(engine, teacher, cap, school, rng, learning_settings,
                        teacher_curriculum_scope, previsit_diagnostics,
                        lesson_grade, total_capabilities=None,
                        plasticity_escape=None):
    """Select one policy while preserving contextual and vNext authority rules."""
    with _timing_trace.trace_span("POLICY_SELECT", capability=cap):
        if learning_settings is None:
            if teacher.get("selection_contract") == _strategy_population.BAMF_SUCCESSOR_SELECTION:
                active, inventory = _strategy_population.active_effective_strategy_keys(teacher, lesson_grade, {})
                key, policy = _strategy_population.pick_existing_active(engine, teacher, lesson_grade, rng, active, inventory)
            else:
                key, policy = engine.pick(teacher, lesson_grade, rng)
            return key, policy, {
                "diagnostic_context_consumed": False,
                "diagnostic_context_key": None,
                "selection_reason": "INHERITED_BANDIT",
                "selection_policy": "bilqis.mlx.teacher-selection/inherited-v1",
            }
        key, policy, metadata = _learning_experiment.contextual_pick(
            engine, teacher, cap, school.stage, rng,
            curriculum_scope=teacher_curriculum_scope,
            diagnostics=previsit_diagnostics, return_metadata=True,
            student_checkpoint_sha256=school.current_student.sha256,
            total_capabilities=total_capabilities, lesson_grade=lesson_grade,
            plasticity_active=bool((plasticity_escape or {}).get("active")))
        legacy_key, legacy_reason = key, metadata.get("selection_reason")
        canary = _canary_decision(
            teacher, cap, school, rng, teacher_curriculum_scope,
            lesson_grade, total_capabilities, legacy_reason)
        context_key = cap + "|" + school.stage + "|" + teacher_curriculum_scope
        scope = teacher.get("causal_experiment", {}).get("contexts", {}).get(context_key, {})
        metadata = dict(metadata)
        metadata["vnext_canary"] = canary
        metadata["actual_authority_changed"] = bool(
            canary.get("actual_authority_changed"))
        if canary.get("status") == "SELECTED":
            key = canary["policy_key"]
            policy = teacher["strategies"][key]
            metadata.update({
                "legacy_policy_key": legacy_key,
                "legacy_selection_reason": legacy_reason,
                "selection_reason": "VNEXT_CANARY",
                "selection_policy": _teacher_vnext.SELECTION_POLICY,
            })
        metadata["teacher_policy_evidence_before"] = _policy_evidence_before(
            teacher, scope, policy)
        return key, policy, metadata
