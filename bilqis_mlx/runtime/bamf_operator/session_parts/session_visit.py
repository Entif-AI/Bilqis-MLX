"""One terminal BAMF visit, separated from the session coordinator."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceRejectedVisit:
    capability: str


_TERMINAL_PREPARED_STATUSES = frozenset({
    "HELD",
    "RESOURCE_HOLD",
    "ACTION_REQUIRED",
    "ACQUISITION_REARMED",
    "GRADE_TRANSITIONED",
    "CERTIFICATION_FAILED",
    "CERTIFICATION_SUPERSEDED",
    "CERTIFICATION_POLICY_REQUIRED",
})


def _assert_current(binding):
    if binding is not None:
        binding.assert_current()


def _cadence(selection):
    return (getattr(selection, "metadata", None) or {}).get("cadence")


def _teacher_selection_fields(selection):
    metadata = getattr(selection, "metadata", None)
    if not isinstance(metadata, dict):
        return {}
    keys = (
        "teacher_selection_reason", "teacher_selection_policy",
        "teacher_policy_evidence_before", "vnext_canary",
        "actual_authority_changed",
    )
    aliases = {
        "teacher_selection_reason": "selection_reason",
        "teacher_selection_policy": "selection_policy",
    }
    return {
        key: metadata.get(aliases.get(key, key))
        for key in keys
        if metadata.get(aliases.get(key, key)) is not None
    }


def _record_resource_rejection(run_dir, prepared, record_rejection, binding):
    _assert_current(binding)
    identity = prepared.selection.visit.identity
    cadence = _cadence(prepared.selection)
    record_rejection(run_dir, prepared.parent, {
        **prepared.resource,
        "capability": prepared.capability,
        "visit_id": identity.visit_id,
        "teacher_visit": identity.to_record(),
        "selected_policy_key": identity.policy_key,
        **_teacher_selection_fields(prepared.selection),
        **({"cadence": cadence} if cadence is not None else {}),
    })
    return ResourceRejectedVisit(prepared.capability)


def _record_candidate_rejection(
        run_dir, prepared, record_rejection, record_cadence_attempt):
    parent, selection = prepared.parent, prepared.selection
    step, decision = prepared.step, prepared.decision
    cadence = _cadence(selection)
    record_rejection(run_dir, parent, {
        "schema": "bilqis.bamf.c16.3-rejection/v2",
        "rejection_attempt_ordinal": prepared.rejection_attempt_ordinal,
        "rejection_journal_ordinal": prepared.rejection_journal_ordinal,
        "visit_id": selection.visit.identity.visit_id,
        "teacher_visit": selection.visit.identity.to_record(),
        "selected_option_id": selection.option_id,
        "selected_policy_key": selection.visit.identity.policy_key,
        "candidate_optimizer_step": (
            step.transaction.parent.optimizer_step + step.transaction.update_steps),
        "retained_optimizer_step": parent.retained_state.optimizer_step,
        "retention_reason": decision.reason,
        "capability": prepared.capability,
        "decision": decision.to_record(),
        "resource": prepared.resource,
        "candidate_evidence": prepared.candidate_evidence,
        "how_outcome": prepared.how_outcome,
        "structural_weaknesses": list(prepared.structural_weaknesses),
        **_teacher_selection_fields(selection),
        **({"cadence": cadence} if cadence is not None else {}),
    })
    if cadence is not None and record_cadence_attempt is not None:
        record_cadence_attempt(
            run_dir, cadence, prepared.capability, "REJECTED")
    return "REJECTED"


def _publish_accepted(
        run_dir, reserve_gib, prepared, *, progress, observer,
        run_authority_binding, accept_publish, measure_phase, emit_progress,
        record_cadence_attempt, load_generation=None):
    parent, selection = prepared.parent, prepared.selection
    step, decision, retained = prepared.step, prepared.decision, prepared.retained
    successor = prepared.successor
    from .evidence_mode import strict_mode_enabled
    strict = strict_mode_enabled()
    runtime_observer = observer
    if runtime_observer is not None:
        stage = getattr(runtime_observer, "stage", None)
        observe = runtime_observer.update if strict or not callable(stage) else stage
        observe(phase="PUBLISHING")
    if strict:
        emit_progress(progress, "publishing accepted successor checkpoint")
    _assert_current(run_authority_binding)
    publication_observer = None
    if strict and runtime_observer is not None:
        publication_observer = lambda metrics: runtime_observer.update(**{
            "publication_" + key: value
            for key, value in metrics.to_record().items()
        })
    if strict:
        with measure_phase(runtime_observer, "publishing_wall_seconds"):
            accept_publish(
                run_dir, successor, retained, decision=decision,
                feature_sha256=successor.extents.factor_map_digest,
                reserve_gib=reserve_gib,
                training_authorities=step.transaction.training_authorities,
                publication_observer=publication_observer)
    else:
        accept_publish(
            run_dir, successor, retained, decision=decision,
            feature_sha256=successor.extents.factor_map_digest,
            reserve_gib=reserve_gib,
            training_authorities=step.transaction.training_authorities,
            publication_observer=None)
    if strict and load_generation is not None:
        load_generation(run_dir)
    cadence = _cadence(selection)
    if cadence is not None and record_cadence_attempt is not None:
        record_cadence_attempt(
            run_dir, cadence, prepared.capability, "RETAINED")
    health = getattr(prepared, "learning_health", None)
    if strict and runtime_observer is not None and isinstance(health, dict):
        runtime_observer.learning_health_by_capability[health["capability_id"]] = health
        runtime_observer.update(learning_health=health)
    return "ACCEPTED"


def visit(
        run_dir, reserve_gib, *, steps_per_visit, batch_size=32, progress,
        source_prefetch_workers, source_prefetch_executor,
        source_prefetch_metrics, observer, run_authority_binding,
        prepare_visit, record_rejection,
        accept_publish, load_generation, measure_phase, emit_progress,
        record_cadence_attempt=None, resource_holds=frozenset()):
    from .evidence_mode import strict_mode_enabled
    strict = strict_mode_enabled()
    prepared = prepare_visit(
        run_dir, steps_per_visit=steps_per_visit, batch_size=batch_size,
        reserve_gib=reserve_gib,
        progress=progress,
        source_prefetch_workers=source_prefetch_workers,
        source_prefetch_executor=source_prefetch_executor,
        source_prefetch_metrics=source_prefetch_metrics,
        **({"observer": observer} if observer is not None else {}),
        **({"resource_holds": resource_holds} if resource_holds else {}))
    if prepared.status in _TERMINAL_PREPARED_STATUSES:
        return prepared.status
    if prepared.status == "RESOURCE_REJECTED":
        if observer is not None:
            stage = getattr(observer, "stage", None)
            (stage if callable(stage) else observer.update)(phase="REJECTING")
        if strict:
            with measure_phase(observer, "rejection_wall_seconds"):
                return _record_resource_rejection(
                    run_dir, prepared, record_rejection, run_authority_binding)
        else:
            return _record_resource_rejection(
                run_dir, prepared, record_rejection, run_authority_binding)
    if not prepared.decision.accepted:
        if observer is not None:
            stage = getattr(observer, "stage", None)
            (stage if callable(stage) else observer.update)(phase="REJECTING")
        if strict:
            with measure_phase(observer, "rejection_wall_seconds"):
                return _record_candidate_rejection(
                    run_dir, prepared, record_rejection, record_cadence_attempt)
        else:
            return _record_candidate_rejection(
                run_dir, prepared, record_rejection, record_cadence_attempt)
    return _publish_accepted(
        run_dir, reserve_gib, prepared, progress=progress, observer=observer,
        run_authority_binding=run_authority_binding, accept_publish=accept_publish,
        measure_phase=measure_phase, emit_progress=emit_progress,
        record_cadence_attempt=record_cadence_attempt,
        load_generation=load_generation)


__all__ = ("visit",)
