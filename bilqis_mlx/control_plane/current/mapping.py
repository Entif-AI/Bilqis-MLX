"""Parent-independent current-generation CP07 records."""
from ..native_contracts import (
    AuthenticatedGeneration, CoverageState, data_value, invalid, materialized_at,
    missing_value, record_meta, run_ref,
)
from ..native_mapping import (
    _accepted_target_score, _append_resource_sample, _append_teacher_snapshot,
)
from bilqis_mlx.mission_control import (
    CandidateDecision, CandidateOutcome, CapabilitySnapshot, LearningEpisode,
    OperatorView, RunContext, UnavailableEnvelope, UnavailableReason,
)


def accepted_current_records(generation: AuthenticatedGeneration):
    """Project accepted tip state without reading an ancestor generation."""
    run = run_ref(generation)
    manifest = generation.manifest
    optimizer_step = manifest["optimizer"].get("step")
    if type(optimizer_step) is not int or optimizer_step < 0:
        invalid("CONTROL_PLANE_NATIVE_HISTORY_OPTIMIZER_STEP_INVALID")
    transition = manifest.get("transition")
    stage = transition.get("kind") if isinstance(transition, dict) else None
    stage = stage if isinstance(stage, str) and stage else "UNKNOWN"
    context = RunContext(
        record_meta(f"run-context:{run.run_id}:{run.generation}", run, generation),
        "ACCEPTED", optimizer_step, stage)
    operator_view = OperatorView(
        record_meta(f"operator-view:{run.run_id}:{run.generation}", run, generation),
        "READY", stage, None, (context.meta.record_id,))
    records = [context, operator_view]
    _append_teacher_snapshot(generation, run, records)
    resource_present = False
    for native in generation.outbox:
        if native.get("event") != "BAMF_C16_3_ACCEPTED":
            continue
        capability = native.get("capability")
        event_id = native.get("event_id")
        if (not isinstance(capability, str) or not capability
                or not isinstance(event_id, str)
                or native.get("optimizer_step") != optimizer_step):
            invalid("CONTROL_PLANE_NATIVE_C16_ACCEPTED_INVALID")
        logical_time = materialized_at(native, run.generation)
        visit_id = native.get("visit_id")
        if not isinstance(visit_id, str) or not visit_id:
            visit_id = event_id
        records.append(LearningEpisode(
            record_meta(
                f"episode:{visit_id}", run, generation, native=native,
                evidence_refs=(f"native-event:{event_id}",), coverage=CoverageState.PARTIAL),
            visit_id, capability, visit_id, "COMPLETED", logical_time, logical_time))
        records.append(CandidateDecision(
            record_meta(
                f"candidate:{event_id}", run, generation, native=native,
                evidence_refs=(f"native-event:{event_id}",), coverage=CoverageState.PARTIAL),
            generation.acceptance["candidate_identity_sha256"], capability,
            CandidateOutcome.ACCEPTED,
            str(generation.acceptance.get("retention_reason") or "ACCEPTED")))
        score_correct, score_total, grade = _accepted_target_score(native, capability)
        records.append(CapabilitySnapshot(
            record_meta(
                f"capability:{run.run_id}:{run.generation}:{capability}", run, generation,
                native=native, evidence_refs=(f"native-event:{event_id}",),
                coverage=CoverageState.PARTIAL),
            capability, grade or "UNKNOWN", "VISIT_ACCEPTED",
            data_value(score_correct) if score_correct is not None else missing_value(),
            data_value(score_total) if score_total is not None else missing_value(),
            missing_value()))
        resource_present = _append_resource_sample(
            generation, run, native, records, []) or resource_present
    if not resource_present:
        records.append(UnavailableEnvelope(
            record_meta(
                f"resource-unavailable:{run.run_id}:{run.generation}", run, generation,
                coverage=CoverageState.UNKNOWN),
            f"resource:{run.run_id}", UnavailableReason.UNKNOWN,
            f"bamf-manifest:{generation.manifest_sha256}"))
    return tuple(records)


__all__ = ("accepted_current_records",)
