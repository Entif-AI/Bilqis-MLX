"""Retention and accepted-successor helpers for the BAMF operator session."""
from __future__ import annotations

from .retention_observation import (
    distributed_retention_metrics as _distributed_retention_metrics,
    finalize_retention_evidence as _finalize_retention_evidence,
    observe_retention_scope as _observe_retention_scope,
    retention_progress_observer as _retention_progress_observer,
    retention_resource as _retention_resource,
)


def _teacher_selection_fields(selection):
    metadata = getattr(selection, "metadata", None)
    if not isinstance(metadata, dict):
        return {}
    aliases = {
        "teacher_selection_reason": "selection_reason",
        "teacher_selection_policy": "selection_policy",
    }
    keys = (
        "teacher_selection_reason", "teacher_selection_policy",
        "teacher_policy_evidence_before", "vnext_canary",
        "actual_authority_changed",
    )
    return {
        key: metadata.get(aliases.get(key, key))
        for key in keys
        if metadata.get(aliases.get(key, key)) is not None
    }


def _stage_learning_first_retention(observer, capability, evaluation, decision):
    """Project already-computed ordinary retention semantics without diagnostics."""
    if observer is None:
        return
    stage = getattr(observer, "stage", None)
    if not callable(stage):
        return
    owner_decision = getattr(evaluation, "decision", None)
    scores = getattr(owner_decision, "outcome_scores", ())
    target = next((
        {
            "state": "MEASURED",
            "before": before,
            "after": after,
            "total": total,
        }
        for scored_capability, before, after, total in scores
        if scored_capability == capability
        and all(type(value) is int for value in (before, after, total))
    ), None)
    evaluated = getattr(decision, "evaluated_capability_ids", ())
    stage(
        retention_target=target,
        retention_protected_count=(
            max(0, len(evaluated) - 1) if isinstance(evaluated, tuple) else None),
    )


def _rejected_structural_weaknesses(
        run_dir, context, selection, candidate_evidence, decision, how_outcome):
    from .evidence_mode import strict_evidence_enabled
    from bilqis_mlx.runtime.source_execution import SourceExecutionContext
    if not isinstance(context, SourceExecutionContext):
        return ()
    if strict_evidence_enabled():
        from bilqis_mlx.runtime.structural_weakness_replay import (
            derive_rejected_weaknesses,
        )
        return derive_rejected_weaknesses(
            run_dir, context, selection, candidate_evidence,
            rejection_reason=decision.reason,
            outcome_sha256=how_outcome["outcome_sha256"])
    from bilqis_mlx.runtime.structural_weakness_replay import (
        derive_live_rejected_weaknesses,
    )
    return derive_live_rejected_weaknesses(
        context, selection, selection.offer.rows(),
        rejection_reason=decision.reason,
        outcome_sha256=how_outcome["outcome_sha256"])


def _evaluate_retention(
        run_dir, parent, context, atlas_path, selection, capability, cache, step,
        identity_before, progress, observer, strict, *, evaluate_candidate,
        issue_decision, identity_delta, emit_progress,
        measure_observed_phase_fn, derive_plasticity_escape):
    from contextlib import nullcontext
    if observer is not None:
        stage = getattr(observer, "stage", None)
        observe = observer.update if strict or not callable(stage) else stage
        observe(phase="RETENTION")
    if strict:
        emit_progress(progress, "evaluating retention evidence")
    retention_phase = (
        measure_observed_phase_fn(observer, "retention_wall_seconds")
        if strict else nullcontext())
    with retention_phase:
        release = getattr(context, "release", None)
        plasticity_escape = (
            derive_plasticity_escape(parent, selection, release)
            if derive_plasticity_escape is not None and release is not None else None)
        retention_observer = lambda fields: _retention_progress_observer(
            observer, progress, emit_progress, fields, strict=strict)
        evaluation = evaluate_candidate(
            context, step.transaction, atlas_path, capability, run_dir=run_dir,
            accepted_parent=parent, execution_cache=cache,
            **({"plasticity_escape": plasticity_escape}
               if plasticity_escape is not None else {}),
            **({"observer": retention_observer}
               if strict and observer is not None else {}))
        decision = issue_decision(evaluation)
        if strict:
            _observe_retention_scope(observer, decision)
        else:
            _stage_learning_first_retention(
                observer, capability, evaluation, decision)
        if not decision.accepted:
            from bilqis_mlx.errors.authority import authority_label
            emit_progress(progress, "retention decision: " + authority_label(
                getattr(decision, "reason", None), blocking_capability=getattr(
                    getattr(evaluation, "decision", None), "blocking_capability", None),
                blocking_scope=getattr(
                    getattr(evaluation, "decision", None), "blocking_scope", None)))
        identity_metrics = identity_delta(identity_before) if strict else None
        retained = (
            evaluation.candidate_state if decision.accepted else evaluation.parent_state)
    return (
        evaluation, decision, retained, identity_metrics, plasticity_escape,
    )


def _stage_learning_first_outcome(observer, strict, how_outcome, decision):
    if strict or observer is None:
        return
    stage = getattr(observer, "stage", None)
    if not callable(stage):
        return
    outcome_context = (
        how_outcome.get("context") if isinstance(how_outcome, dict) else None)
    stage(
        retention_phase=(
            outcome_context.get("phase")
            if isinstance(outcome_context, dict) else None),
        retention_decision=getattr(decision, "decision", None),
        retention_reason=getattr(decision, "reason", None),
    )


def retention_result(
        run_dir, parent, context, atlas_path, selection, capability, cache, steps,
        capture, rejection_journal_ordinal, rejection_attempt_ordinal,
        identity_before, progress, observer, *, evaluate_candidate,
        issue_decision, identity_delta, resource_observation,
        derive_successor, bind_baseline_successor, finalize_generation_authority,
        prepared_visit_type, emit_progress,
        measure_observed_phase_fn, derive_plasticity_escape=None):
    step = steps[-1]
    from .evidence_mode import strict_mode_enabled
    strict = strict_mode_enabled()
    evaluation, decision, retained, identity_metrics, plasticity_escape = (
        _evaluate_retention(
            run_dir, parent, context, atlas_path, selection, capability, cache, step,
            identity_before, progress, observer, strict,
            evaluate_candidate=evaluate_candidate,
            issue_decision=issue_decision,
            identity_delta=identity_delta,
            emit_progress=emit_progress,
            measure_observed_phase_fn=measure_observed_phase_fn,
            derive_plasticity_escape=derive_plasticity_escape))
    candidate_evidence, learning_summary = _finalize_retention_evidence(
        strict, observer, capture, run_dir, decision, measure_observed_phase_fn)
    resource = (
        _retention_resource(
            run_dir, steps, context, identity_metrics, candidate_evidence,
            resource_observation)
        if strict else None)
    if strict:
        _distributed_retention_metrics(
            steps, evaluation, decision, observer, resource)
    from bilqis_mlx.runtime.outcomes.issuance import (
        build_outcome, carry_credit_to_successor, credited_visit,
    )
    how_outcome = build_outcome(
        run_dir, selection, evaluation, decision, candidate_evidence,
        learning_summary=learning_summary)
    _stage_learning_first_outcome(observer, strict, how_outcome, decision)
    structural_weaknesses = (() if decision.accepted else _rejected_structural_weaknesses(
        run_dir, context, selection, candidate_evidence, decision, how_outcome))
    successor, learning_health = _accepted_successor(
        decision, run_dir, parent, context, atlas_path, selection, capability,
        cache, retained, step.transaction, observer,
        rejection_journal_ordinal, resource, candidate_evidence, capture, how_outcome,
        derive_successor, bind_baseline_successor, evaluation,
        credited_visit, carry_credit_to_successor, plasticity_escape,
        finalize_generation_authority)
    return prepared_visit_type(
        "ACCEPTED" if decision.accepted else "REJECTED", parent,
        selection=selection, step=step, steps=tuple(steps), decision=decision,
        retained=retained, capability=capability, successor=successor,
        identity_metrics=identity_metrics, resource=resource,
        candidate_evidence=candidate_evidence, how_outcome=how_outcome,
        structural_weaknesses=structural_weaknesses,
        retention_evaluation=(evaluation if not decision.accepted else None),
        learning_health=learning_health,
        rejection_journal_ordinal=rejection_journal_ordinal,
        rejection_attempt_ordinal=rejection_attempt_ordinal)


def _instruction_event(run_dir, parent, cache, capability, *, teacher_state=None):
    from bilqis_mlx.errors import BilqisError
    try:
        from bilqis_mlx.learning.teacher_lineage import instruction_history
        from bilqis_mlx.runtime.priority_rejection_replay import rejection_recency
        history_state, seen = instruction_history(
            parent.teacher_state if teacher_state is None else teacher_state)
        _, rejected = rejection_recency(run_dir, parent, cache)
        return {
            "event": "BAMF_INSTRUCTION_HISTORY",
            "schema": "bilqis.bamf.instruction-history/v1",
            "state": history_state,
            "capability_ids": sorted(set(seen) | set(rejected) | {capability}),
        }
    except BilqisError:
        raise
    except (AttributeError, TypeError, ValueError, KeyError):
        return {
            "event": "BAMF_INSTRUCTION_HISTORY",
            "schema": "bilqis.bamf.instruction-history/v1",
            "state": "PARTIAL", "capability_ids": [capability],
        }


def _accepted_successor(
        decision, run_dir, parent, context, atlas_path, selection, capability,
        cache, retained, candidate_transaction, observer,
        rejection_journal_ordinal, resource, candidate_evidence, capture, how_outcome,
        derive_successor, bind_baseline_successor, evaluation,
        credited_visit, carry_credit_to_successor, plasticity_escape,
        finalize_generation_authority):
    if not decision.accepted:
        return None, None
    learned_visit = credited_visit(selection.visit, how_outcome)
    instruction_event = _instruction_event(
        run_dir, parent, cache, capability,
        teacher_state=selection.visit.projection.teacher_state)
    from .evidence_mode import strict_evidence_enabled
    learning_health = None
    health_state = None
    if strict_evidence_enabled():
        try:
            from ..learning_health_runtime import accepted_learning_health_state
            health_state, learning_health = accepted_learning_health_state(
                run_dir, parent, selection, candidate_evidence, decision, retained, capture,
                plasticity_escape=plasticity_escape)
        except (AttributeError, TypeError, ValueError, KeyError):
            health_state = None
    events = ({
        "event": "BAMF_C16_3_ACCEPTED",
        "optimizer_step": retained.optimizer_step,
        "parent_generation": cache.generation,
        "accepted_manifest_sha256": cache.accepted_manifest_sha256,
        "candidate_attempt_ordinal": rejection_journal_ordinal,
        "capability": capability,
        "visit_id": selection.visit.identity.visit_id,
        "selected_policy_key": selection.visit.identity.policy_key,
        "selected_option_id": selection.option_id,
        "resource": resource, "candidate_evidence": candidate_evidence,
        "how_outcome": how_outcome,
        **_teacher_selection_fields(selection),
        **({"cadence": getattr(selection, "metadata", {}).get("cadence")}
           if isinstance(getattr(selection, "metadata", None), dict)
           and selection.metadata.get("cadence") is not None else {}),
    }, instruction_event)
    successor = derive_successor(
        run_dir, retained, learned_visit, delivery_events=events,
        candidate_transaction=candidate_transaction)
    if health_state is not None:
        from dataclasses import replace
        successor = replace(successor, learning_health_state=health_state)
    successor = carry_credit_to_successor(learned_visit, successor, parent)
    successor = bind_baseline_successor(evaluation, successor)
    from ..championship import (
        bind_accepted_championship_successor,
        championship_boundary_capabilities,
    )
    championship_scope = (
        championship_boundary_capabilities(selection, capability)
        if strict_evidence_enabled() else ())
    if championship_scope:
        from bilqis_mlx.runtime._factory_retention_support import _training_exclusions
        from bilqis_mlx.runtime.factory_retention_owner import CURRENT_EVIDENCE_STAGE
        successor = bind_accepted_championship_successor(
            run_dir, parent, cache, successor, context, atlas_path,
            capability, evaluation,
            checkpoint_origin_group=getattr(selection, "lesson_grade", None),
            training=_training_exclusions(candidate_transaction),
            evidence_stage=CURRENT_EVIDENCE_STAGE,
            observer=(lambda fields: observer.update(**fields)) if observer is not None else None,
            boundary_capabilities=championship_scope)
    if (getattr(evaluation, "candidate_generation_authority_sha256", None) is not None
            and getattr(candidate_transaction, "motif_transition", None) is not None):
        finalize_generation_authority(
            evaluation, decision, parent, candidate_transaction, successor)
    return successor, learning_health


__all__ = ("retention_result",)
