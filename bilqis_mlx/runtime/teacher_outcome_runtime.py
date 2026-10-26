"""Prometheus adapter for the portable teacher-outcome contract."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import random

from bilqis_mlx.learning.teacher_multifidelity import (
    DEFAULT_ACTIVATION_POLICY,
    DEFAULT_SHADOW_POLICY,
    evaluate_shadow,
    qualify_activation,
)
from bilqis_mlx.learning.teacher_distribution import learned_proposals
from bilqis_mlx.learning.teacher_outcomes import (
    current_health,
    observe,
    predict,
    proposed_action,
    student_region,
)
from bilqis_mlx.learning.teacher_proposals import acquire, candidate_proposals
from bilqis_mlx.learning import learning_experiment as _learning_experiment
from bilqis_mlx.learning import student_ops as _student_ops
from bilqis_mlx.learning import teacher_feedback as _teacher_feedback
from bilqis_mlx.learning.teacher_strategy_population import (
    effective_policy_features,
    effective_policy_key,
)


@dataclass(frozen=True)
class PreparedCandidate:
    region: dict
    action: dict
    prediction: dict
    shadow_rungs: tuple[int, ...]


class TeacherOutcomeRuntimeError(str, Enum):
    PREPARATION_MISSING = "TEACHER_VNEXT_PREPARATION_MISSING"


def previsit_diagnostics(receipt: dict, capability: str, *,
                         unresolved_miss_count: int,
                         champion_candidate_count: int) -> tuple[tuple, dict]:
    previous_methodology = next((
        member.get("lesson_methodology")
        for member in reversed(receipt.get("delivery_outbox", ()))
        if member.get("capability") == capability and
        "lesson_methodology" in member
    ), None)
    warnings = _teacher_feedback.active_warning_signals(
        receipt.get("last_exam"), previous_methodology, capability)
    return warnings, {
        "warnings": warnings,
        "unresolved_miss_count": unresolved_miss_count,
        "champion_candidate_count": champion_candidate_count,
    }


def _score(scores: dict, capability: str) -> tuple[int | None, int | None]:
    value = scores.get(capability)
    if not isinstance(value, dict):
        return None, None
    correct, total = value.get("correct"), value.get("total")
    if type(correct) is not int or type(total) is not int:
        return None, None
    return correct, total


def build_region(receipt: dict, school, teacher: dict, *, capability: str,
                 phase: str, lesson_grade: str, curriculum_scope: str,
                 geometry_epoch: str | None) -> dict:
    scores = (receipt.get("last_exam") or {}).get("scores") or {}
    capability_correct, capability_total = _score(scores, capability)
    grade_rows = [
        value for name, value in scores.items()
        if isinstance(name, str) and name.partition(".")[0] == lesson_grade and
        isinstance(value, dict) and type(value.get("correct")) is int and
        type(value.get("total")) is int
    ]
    grade_correct = sum(value["correct"] for value in grade_rows) if grade_rows else None
    grade_total = sum(value["total"] for value in grade_rows) if grade_rows else None
    grade_capability_scores = {
        name: (value["correct"], value["total"])
        for name, value in scores.items()
        if isinstance(name, str) and name.partition(".")[0] == lesson_grade and
        isinstance(value, dict) and type(value.get("correct")) is int and
        type(value.get("total")) is int
    }
    stagnation = (
        teacher.get("causal_experiment", {}).get("capability_stagnation", {}).get(
            capability + "|" + curriculum_scope, {})
    )
    return student_region(
        capability=capability,
        phase=phase,
        lesson_grade=lesson_grade,
        curriculum_scope=curriculum_scope,
        geometry_epoch=geometry_epoch,
        numeric_maximum=receipt.get("numeric_maximum"),
        capability_correct=capability_correct,
        capability_total=capability_total,
        grade_correct=grade_correct,
        grade_total=grade_total,
        rejection_streak=int(stagnation.get("rejection_streak", 0)),
        attempts_since_retained=int(stagnation.get("attempts_since_retained", 0)),
        mastery_debt_count=len(getattr(school, "carried_mastery_debt", ())),
        grade_capability_scores=grade_capability_scores,
        mastery_debt_capabilities=tuple(getattr(
            school, "carried_mastery_debt", ())),
    )


def action_family(teacher: dict, *, capability: str, phase: str,
                  curriculum_scope: str, policy_key: str) -> str:
    scope = teacher.get("causal_experiment", {}).get("contexts", {}).get(
        capability + "|" + phase + "|" + curriculum_scope, {})
    record = scope.get(policy_key)
    if isinstance(record, dict) and int(record.get("retained", 0)) > 0:
        return "INCUMBENT_REPLAY"
    if isinstance(record, dict) and int(record.get("trials", 0)) > 0:
        return "CONTEXTUAL_CHALLENGER"
    return "GLOBAL_CHALLENGER"


def build_action(teacher: dict, *, capability: str, phase: str,
                 curriculum_scope: str, policy_key: str, policy: dict,
                 candidate_steps: int | None = None,
                 batch_size: int | None = None) -> dict:
    parameters = effective_policy_features(policy)
    if candidate_steps is not None:
        parameters["candidate_steps"] = candidate_steps
    if batch_size is not None:
        parameters["batch_size"] = batch_size
    return proposed_action(
        family=action_family(
            teacher, capability=capability, phase=phase,
            curriculum_scope=curriculum_scope, policy_key=policy_key),
        effective_policy_key=effective_policy_key(policy),
        policy_key=policy_key,
        parameters=parameters,
    )


def prediction_before(teacher: dict, *, region: dict, action: dict) -> dict:
    return predict(teacher, region=region, action=action)


def prepare_candidate(receipt: dict, school, teacher: dict, *, capability: str,
                      phase: str, lesson_grade: str, curriculum_scope: str,
                      geometry_epoch: str | None, policy_key: str, policy: dict,
                      candidate_steps: int, batch_size: int,
                      shadow_enabled: bool) -> PreparedCandidate:
    region = build_region(
        receipt, school, teacher, capability=capability, phase=phase,
        lesson_grade=lesson_grade, curriculum_scope=curriculum_scope,
        geometry_epoch=geometry_epoch)
    action = build_action(
        teacher, capability=capability, phase=phase,
        curriculum_scope=curriculum_scope, policy_key=policy_key,
        policy=policy, candidate_steps=candidate_steps, batch_size=batch_size)
    return PreparedCandidate(
        region=region,
        action=action,
        prediction=prediction_before(teacher, region=region, action=action),
        shadow_rungs=(active_rungs(DEFAULT_SHADOW_POLICY, candidate_steps)
                      if shadow_enabled else ()),
    )


def prepare_from_visit(receipt, school, teacher, capability, phase, lesson_grade,
                       curriculum_scope, geometry_epoch, policy_key, policy,
                       candidate_steps, batch_size, enabled):
    if not enabled:
        return None
    return prepare_candidate(
        receipt, school, teacher, capability=capability, phase=phase,
        lesson_grade=lesson_grade, curriculum_scope=curriculum_scope,
        geometry_epoch=geometry_epoch, policy_key=policy_key, policy=policy,
        candidate_steps=candidate_steps, batch_size=batch_size,
        shadow_enabled=True)


def select_policy_and_prepare(
        engine, teacher, rng, receipt, school, *, capability: str,
        phase: str, lesson_grade: str, curriculum_scope: str,
        geometry_epoch: str | None, diagnostics: dict,
        learning_settings, candidate_steps: int, batch_size: int):
    if learning_settings is not None:
        policy_key, policy, selection = _learning_experiment.contextual_pick(
            engine, teacher, capability, phase, rng,
            curriculum_scope=curriculum_scope, diagnostics=diagnostics,
            return_metadata=True,
            student_checkpoint_sha256=school.current_student.sha256)
    else:
        policy_key, policy = engine.pick(teacher, lesson_grade, rng)
        selection = {
            "diagnostic_context_consumed": False,
            "diagnostic_context_key": None,
        }
    prepared = prepare_from_visit(
        receipt, school, teacher, capability, phase, lesson_grade,
        curriculum_scope, geometry_epoch, policy_key, policy,
        candidate_steps, batch_size, learning_settings is not None)
    return policy_key, policy, selection, prepared


def shadow_target_probe(mx, params, target_rows, parent_predictions,
                        receipt: dict, *, capability: str,
                        optimizer_step: int) -> tuple[int, int]:
    predictions = _student_ops._predictions(
        mx, params, list(target_rows), receipt["config"], receipt["answer_ids"])
    paired = _learning_experiment.paired_outcomes(
        target_rows, parent_predictions, predictions)
    return optimizer_step, paired[capability]["after"] - paired[capability]["before"]


def _shadow_reviews(teacher: dict) -> tuple[dict, ...]:
    model = teacher.get("outcome_model")
    if not isinstance(model, dict):
        return ()
    recent = model.get("recent")
    if not isinstance(recent, list):
        return ()
    return tuple(
        row["shadow_review"] for row in recent
        if isinstance(row, dict) and isinstance(row.get("shadow_review"), dict)
    )


def finalize_candidate(
        teacher: dict, *, prepared: PreparedCandidate, outcome: dict,
        attempted_optimizer_updates: int, retained_optimizer_updates: int,
        wall_seconds: float, shadow_target_probes, acquisition_seed: int) -> dict:
    """Record one candidate and compute only neural-inert vNext recommendations."""
    region, action, prediction = (
        prepared.region, prepared.action, prepared.prediction)
    parameters = action.get("parameters", {})
    candidate_steps = int(parameters["candidate_steps"])
    batch_size = int(parameters["batch_size"])
    capability = region["capability"]
    phase = region["phase"]
    curriculum_scope = region["curriculum_scope"]
    final_retained = outcome.get("decision") == "PROVISIONAL"
    shadow = evaluate_shadow(
        DEFAULT_SHADOW_POLICY,
        probes=tuple((*shadow_target_probes,
                      (candidate_steps, outcome["local_correct_delta"]))),
        final_retained=final_retained,
        full_budget_steps=candidate_steps)
    observation = observe(
        teacher, region=region, action=action,
        retained=final_retained,
        rejection_reason=outcome["reason"],
        target_delta=outcome["local_correct_delta"],
        protected_net_delta=outcome["protected_net_correct_delta"],
        worst_protected_loss=outcome["worst_protected_loss"],
        attempted_steps=attempted_optimizer_updates,
        retained_steps=retained_optimizer_updates,
        wall_seconds=wall_seconds,
        predicted_retention_probability=prediction["retention_probability"],
        shadow_review=shadow)
    after = predict(teacher, region=region, action=action)
    health = current_health(teacher)
    activation = qualify_activation(
        _shadow_reviews(teacher), policy=DEFAULT_ACTIVATION_POLICY)
    proposals = list(candidate_proposals(
        teacher, capability=capability, phase=phase,
        curriculum_scope=curriculum_scope,
        candidate_steps=candidate_steps, batch_size=batch_size))
    learned = learned_proposals(
        teacher, region=region, rng=random.Random(acquisition_seed + 1),
        candidate_steps=candidate_steps, batch_size=batch_size)
    proposals.extend(learned["proposals"])
    proposal_shadow = acquire(
        teacher, region=region, proposals=tuple(proposals),
        rng=random.Random(acquisition_seed))
    return {
        "teacher_outcome_observation": observation,
        "teacher_outcome_prediction_before": prediction,
        "teacher_outcome_prediction_after": after,
        "teacher_health": health,
        "teacher_multifidelity_shadow": shadow,
        "teacher_multifidelity_activation": activation,
        "teacher_proposal_shadow": proposal_shadow,
        "teacher_learned_distribution_shadow": learned,
    }


def finalize_from_visit(teacher, prepared, outcome, attempted_updates,
                        retained_updates, wall_seconds, shadow_target_probes,
                        acquisition_seed):
    if prepared is None:
        raise ValueError(TeacherOutcomeRuntimeError.PREPARATION_MISSING.value)
    return finalize_candidate(
        teacher, prepared=prepared, outcome=outcome,
        attempted_optimizer_updates=attempted_updates,
        retained_optimizer_updates=retained_updates,
        wall_seconds=wall_seconds, shadow_target_probes=shadow_target_probes,
        acquisition_seed=acquisition_seed)


def finalize_if_available(teacher, prepared, outcome, attempted_updates,
                          retained_updates, wall_seconds, shadow_target_probes,
                          acquisition_seed):
    if outcome is None:
        return {}
    return finalize_from_visit(
        teacher, prepared, outcome, attempted_updates, retained_updates,
        wall_seconds, shadow_target_probes, acquisition_seed)
