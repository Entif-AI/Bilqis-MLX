"""Authenticated accepted-generation records mapped into CP02 view contracts."""
from __future__ import annotations

from bilqis_mlx.mission_control import (
    CandidateDecision, CandidateOutcome, CapabilitySnapshot, CoverageState,
    LearningEpisode, RunContext, UnavailableEnvelope, UnavailableReason,
)

from .event_stream import EventFamily
from .native_contracts import (
    AuthenticatedGeneration, accepted_student_sha256, data_value, derived_event_id, invalid,
    materialized_at, missing_value, record_meta, run_ref,
)


def _candidate_outcome(retention: dict) -> CandidateOutcome:
    decision = retention.get("decision")
    if decision in {"REJECT", "REJECTED"}:
        return CandidateOutcome.REJECTED
    if decision in {"PROVISIONAL", "HELD"}:
        return CandidateOutcome.HELD
    if decision in {"ACCEPT", "ACCEPTED", "RETAINED"}:
        return CandidateOutcome.ACCEPTED
    return CandidateOutcome.ACTION_REQUIRED


def _append_c16_accepted(generation, parent, run, native, records, events):
    capability = native.get("capability")
    visit = generation.teacher_state.get("last_visit")
    if not isinstance(capability, str) or not isinstance(visit, dict):
        invalid("CONTROL_PLANE_NATIVE_C16_ACCEPTED_INVALID")
    if native.get("optimizer_step") != generation.manifest["optimizer"].get("step"):
        invalid("CONTROL_PLANE_NATIVE_C16_ACCEPTED_INVALID")
    from bilqis_mlx.learning.teacher_visit_identity import TeacherVisitIdentity

    identity = TeacherVisitIdentity.from_record(visit)
    if parent is None:
        invalid("CONTROL_PLANE_NATIVE_C16_ACCEPTED_PARENT_REQUIRED")
    state = parent.teacher_state
    expected = TeacherVisitIdentity(
        parent.run_identity["run_identity_sha256"], parent.run_identity["run_seed"],
        parent.manifest["generation"], parent.manifest_sha256,
        state["teacher_identity"], state["teacher_epoch"],
        accepted_student_sha256(parent),
        state["next_seed"], state["cursor"], capability, identity.policy_key,
    )
    if identity != expected:
        invalid("CONTROL_PLANE_NATIVE_C16_ACCEPTED_INVALID")
    event_id = native["event_id"]
    logical_time = materialized_at(native, run.generation)
    episode = LearningEpisode(
        record_meta(
            f"episode:{identity.visit_id}", run, generation, native=native,
            evidence_refs=(f"native-event:{event_id}",),
            coverage=CoverageState.PARTIAL),
        identity.visit_id, capability, identity.visit_id, "COMPLETED",
        logical_time, logical_time)
    candidate = CandidateDecision(
        record_meta(
            f"candidate:{event_id}", run, generation, native=native,
            evidence_refs=(f"native-event:{event_id}",),
            coverage=CoverageState.PARTIAL),
        generation.acceptance["candidate_identity_sha256"], capability,
        CandidateOutcome.ACCEPTED,
        str(generation.acceptance.get("retention_reason") or "ACCEPTED"))
    capability_record = CapabilitySnapshot(
        record_meta(
            f"capability:{run.run_id}:{run.generation}:{capability}",
            run, generation, native=native,
            evidence_refs=(f"native-event:{event_id}",),
            coverage=CoverageState.PARTIAL),
        capability, "UNKNOWN", "VISIT_ACCEPTED",
        missing_value(), missing_value(), missing_value())
    records.extend((episode, candidate, capability_record))
    events.extend((
        (EventFamily.LESSON_VISIT_COMPLETED, episode,
         derived_event_id(event_id, "episode")),
        (EventFamily.CANDIDATE_RETAINED, candidate, event_id),
        (EventFamily.CAPABILITY_CHANGED, capability_record,
         derived_event_id(event_id, "capability")),
    ))


def _append_teacher_visit(generation, run, native, records, events):
    capability = native.get("capability")
    if not isinstance(capability, str):
        return
    event_id = native["event_id"]
    start = native.get("source_time")
    if type(start) is not int or start < 0:
        start = materialized_at(native, run.generation)
    episode = LearningEpisode(
        record_meta(
            f"episode:{event_id}", run, generation, native=native,
            evidence_refs=(f"native-event:{event_id}",)),
        event_id, capability, event_id, "COMPLETED", start,
        materialized_at(native, run.generation))
    records.append(episode)
    events.append((EventFamily.LESSON_VISIT_COMPLETED, episode, event_id))
    retention = native.get("candidate_retention")
    if not isinstance(retention, dict):
        return
    outcome = _candidate_outcome(retention)
    candidate = CandidateDecision(
        record_meta(
            f"candidate:{event_id}", run, generation, native=native,
            evidence_refs=(f"native-event:{event_id}",)),
        str(retention.get("candidate_id") or event_id), capability, outcome,
        str(retention.get("reason") or retention.get("decision") or "UNKNOWN"))
    records.append(candidate)
    family = (EventFamily.CANDIDATE_REJECTED
              if outcome is CandidateOutcome.REJECTED
              else EventFamily.CANDIDATE_RETAINED
              if outcome in {CandidateOutcome.ACCEPTED, CandidateOutcome.HELD}
              else EventFamily.CANDIDATE_ASSESSED)
    events.append((family, candidate, derived_event_id(event_id, "candidate")))


def _append_capability_best(generation, run, native, records, events):
    scores = native.get("scores")
    grade = native.get("grade")
    if not isinstance(scores, dict):
        return
    for capability_id in native.get("capabilities", ()):
        score = scores.get(capability_id)
        if (not isinstance(capability_id, str) or not isinstance(score, dict)
                or type(score.get("correct")) is not int
                or type(score.get("total")) is not int):
            continue
        snapshot = CapabilitySnapshot(
            record_meta(
                f"capability:{run.run_id}:{run.generation}:{capability_id}",
                run, generation, native=native,
                evidence_refs=(f"native-event:{native['event_id']}",)),
            capability_id, grade if isinstance(grade, str) and grade else "UNKNOWN",
            "BEST_COMMITTED", data_value(score["correct"]),
            data_value(score["total"]), missing_value())
        records.append(snapshot)
        events.append((
            EventFamily.CAPABILITY_CHANGED, snapshot,
            derived_event_id(native["event_id"], "capability:" + capability_id)))


def accepted_records(
    generation: AuthenticatedGeneration,
    parent: AuthenticatedGeneration | None = None,
):
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
    generation_unavailable = UnavailableEnvelope(
        record_meta(
            f"generation-unavailable:{run.run_id}:{run.generation}", run, generation,
            coverage=CoverageState.UNKNOWN),
        f"generation:{run.run_id}", UnavailableReason.UNKNOWN,
        f"bamf-manifest:{generation.manifest_sha256}")
    resource_unavailable = UnavailableEnvelope(
        record_meta(
            f"resource-unavailable:{run.run_id}:{run.generation}", run, generation,
            coverage=CoverageState.UNKNOWN),
        f"resource:{run.run_id}", UnavailableReason.UNKNOWN,
        f"bamf-manifest:{generation.manifest_sha256}")
    records = [context, generation_unavailable, resource_unavailable]
    events = [(EventFamily.RUN_STATE_CHANGED, context,
               f"native-run:{generation.manifest_sha256}")]
    for native in generation.outbox:
        kind = native.get("event")
        if kind == "BAMF_C16_3_ACCEPTED":
            _append_c16_accepted(generation, parent, run, native, records, events)
        elif kind == "SCHOOL_TEACHER_VISIT_COMMITTED":
            _append_teacher_visit(generation, run, native, records, events)
        elif kind == "SCHOOL_CAPABILITY_BEST_COMMITTED":
            _append_capability_best(generation, run, native, records, events)
    return tuple(records), tuple(events)


__all__ = ("accepted_records",)
