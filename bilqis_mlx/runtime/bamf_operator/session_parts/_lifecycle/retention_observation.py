"""Strict retention evidence and cheap live progress observation helpers."""
import hashlib
import json


def _contract_digest(payload) -> str:
    wire = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(wire.encode()).hexdigest()


def observe_retention_scope(observer, decision):
    if observer is None:
        return
    fields = {
        "retention_evaluated_capability_count": len(
            getattr(decision, "evaluated_capability_ids", ())),
        "retention_protection_plan_sha256": getattr(
            decision, "retention_protection_plan_sha256", None),
        "retention_broad_certification_trigger": getattr(
            decision, "broad_certification_trigger", None),
    }
    stage = getattr(observer, "stage", None)
    (stage if callable(stage) else observer.update)(**fields)


def distributed_retention_metrics(steps, evaluation, decision, observer, resource):
    """Bind post-C05 retained-learning facts to distributed execution receipts."""
    costs = tuple(
        step.realized_cost for step in steps
        if isinstance(getattr(step, "realized_cost", None), dict)
        and "c08_distributed_manifest_digest" in step.realized_cost)
    if not costs:
        return
    record = getattr(observer, "record", {}) if observer is not None else {}
    evaluation_seconds = (
        record.get("retention_wall_seconds") if isinstance(record, dict) else None)
    if (type(evaluation_seconds) not in (int, float)
            or type(evaluation_seconds) is bool or evaluation_seconds < 0):
        return
    scores = getattr(getattr(evaluation, "decision", None), "outcome_scores", ())
    gains = tuple(
        (after - before) / total
        for _capability, before, after, total in scores
        if type(total) is int and total > 0)
    retained_gain = (
        sum(gains) / len(gains) if decision.accepted and gains else 0.0)
    candidate_wall_seconds = sum(float(
        cost.get("candidate_step_wall_seconds", cost.get("wall_seconds", 0.0)))
        for cost in costs)
    elapsed = candidate_wall_seconds + float(evaluation_seconds)
    source_contract_digest = _contract_digest([{
        "retained_generation": cost["c08_distributed_retained_generation"],
        "retained_manifest_sha256":
            cost["c08_distributed_retained_manifest_sha256"],
        "logical_batch_digest": cost["c08_distributed_logical_batch_digest"],
        "source_release": cost["c08_distributed_source_release"],
        "curriculum_release": cost["c08_distributed_curriculum_release"],
    } for cost in costs])
    evaluation_contract_digest = _contract_digest({
        "policy_sha256": evaluation.decision.policy_sha256,
        "retention_protection_plan_sha256": getattr(
            decision, "retention_protection_plan_sha256", None),
        "evaluated_capability_ids": tuple(
            getattr(decision, "evaluated_capability_ids", ())),
        "broad_certification_trigger": getattr(
            decision, "broad_certification_trigger", None),
    })
    resource.update({
        "c08_distributed_manifest_digests": tuple(
            cost["c08_distributed_manifest_digest"] for cost in costs),
        "c08_distributed_evaluation_seconds": float(evaluation_seconds),
        "c08_distributed_accepted_steps_per_hour": (
            resource["optimizer_steps"] * 3600.0 / elapsed
            if decision.accepted and elapsed > 0 else 0.0),
        "c08_distributed_retained_capability_gain": retained_gain,
        "c08_distributed_source_contract_digest": source_contract_digest,
        "c08_distributed_evaluation_contract_digest":
            evaluation_contract_digest,
    })


def _complete_observer_evidence(
        observer, capture, run_dir, candidate_evidence, decision):
    if observer is None:
        return
    try:
        methodology = getattr(capture, "learning_methodology", None)
        if callable(methodology):
            observer.update(learning_methodology=methodology())
        from ..evidence_parts.projection import complete_visit_evidence
        record = getattr(observer, "record", {})
        current_visit = (
            record.get("visit_evidence") if isinstance(record, dict) else None
        ) or {"schema": "bilqis.bamf.visit-evidence/v1", "state": "PARTIAL"}
        observer.update(visit_evidence=complete_visit_evidence(
            run_dir, current_visit, candidate_evidence, decision))
    except Exception:
        pass


def retention_resource(
        run_dir, steps, context, identity_metrics, candidate_evidence,
        resource_observation):
    resource = resource_observation(
        run_dir, tuple(steps), getattr(context, "_source_preparation_metrics", None),
        identity_metrics=identity_metrics)
    persistence = (
        candidate_evidence.get("persistence", {})
        if isinstance(candidate_evidence, dict) else {})
    resource.update({
        "evidence_bytes_written": persistence.get("bytes_written", 0),
        "evidence_file_fsyncs": persistence.get("file_fsyncs", 0),
        "evidence_directory_fsyncs": persistence.get("directory_fsyncs", 0),
        "evidence_objects": persistence.get("evidence_objects", 0),
        "evidence_persistence_seconds": persistence.get("persistence_seconds", 0.0),
    })
    final_cost = getattr(steps[-1], "realized_cost", {}) if steps else {}
    loss_total = final_cost.get("loss_total") if isinstance(final_cost, dict) else None
    if type(loss_total) in (int, float):
        resource["loss_total"] = float(loss_total)
    return resource


def retention_progress_observer(observer, progress, emit_progress, fields, *, strict):
    if observer is not None:
        stage = getattr(observer, "stage", None)
        if strict or not callable(stage):
            observer.update(**fields)
        else:
            semantic_fields = {
                key: fields[key]
                for key in (
                    "retention_completed", "retention_total",
                    "retention_subject", "retention_role")
                if key in fields
            }
            if semantic_fields:
                stage(**semantic_fields)
    completed = fields.get("retention_completed") if isinstance(fields, dict) else None
    total = fields.get("retention_total") if isinstance(fields, dict) else None
    subject = fields.get("retention_subject") if isinstance(fields, dict) else None
    role = fields.get("retention_role") if isinstance(fields, dict) else None
    if (type(completed) is int and type(total) is int
            and isinstance(subject, str) and isinstance(role, str)):
        emit_progress(
            progress, f"retention {completed}/{total}: {subject} · {role}")


def finalize_retention_evidence(
        strict, observer, capture, run_dir, decision, measure_observed_phase_fn):
    if not strict:
        return None, capture.summary()
    with measure_observed_phase_fn(observer, "evidence_finalization_wall_seconds"):
        candidate_evidence = capture.finalize(
            accepted=decision.accepted, decision=decision.to_record())
    _complete_observer_evidence(
        observer, capture, run_dir, candidate_evidence, decision)
    return candidate_evidence, None


__all__ = (
    "distributed_retention_metrics", "finalize_retention_evidence",
    "observe_retention_scope", "retention_progress_observer", "retention_resource",
)
