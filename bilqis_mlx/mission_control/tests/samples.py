"""Literal samples spanning every CP02 top-level record type."""
from __future__ import annotations

from bilqis_mlx.mission_control.envelopes import (
    ErrorEnvelope, EventEnvelope, PartialEnvelope, StaleEnvelope,
    StreamPosition, UnavailableEnvelope, UnavailableReason, event_cursor_sha256,
)
from bilqis_mlx.mission_control.events import (
    CandidateDecision, CandidateOutcome, CorrectionEvent, FrameCompileReceipt,
    LearningEpisode, SalienceEvent,
)
from bilqis_mlx.mission_control.model import (
    AuthorityClass, CoverageState, DataValue, RecordMeta, RunRef,
    ValueOrigin, ValueState,
)
from bilqis_mlx.mission_control.observability import (
    GenerationManifest, MemorySnapshot, NeuralRuntimeSample, ResourceSample,
    SemanticAtlasSnapshot, TeacherSnapshot,
)
from bilqis_mlx.mission_control.operator import (
    ActionParameter, ActionReceiptState, OperatorActionReceipt,
    OperatorActionRequest,
)
from bilqis_mlx.mission_control.snapshots import (
    CapabilitySnapshot, CurriculumFrontier, OperatorView, RunContext,
    SchoolSnapshot,
)


D1, D2, D3, D4 = (char * 64 for char in "1234")
RUN = RunRef("run-7", D4, 7, D1, D2, D2, D3, D4)


def meta(name: str, *, run=RUN, authority=AuthorityClass.DERIVED,
         coverage=CoverageState.COMPLETE) -> RecordMeta:
    return RecordMeta(
        record_id=name, run=run, materialized_at=120, observed_at=118, as_of=118,
        coverage=coverage, authority=authority,
        source_refs=("source:a",), evidence_refs=("evidence:a",),
        receipt_refs=("receipt:a",),
    )


def value(number, units="count", origin=ValueOrigin.MEASURED) -> DataValue:
    return DataValue(ValueState.PRESENT, origin, number, units)


SAMPLES = (
    RunContext(meta("run-context"), "READY", 42, "ASSESS_MAIN"),
    OperatorView(meta("operator-view"), "READY", "ASSESS_MAIN", "B.EXAMPLE", ("school",)),
    SchoolSnapshot(meta("school"), "ACTIVE", "B", ("A", "B"), value(9), value(4)),
    CapabilitySnapshot(meta("capability"), "B.EXAMPLE", "B", "LEARNING",
                       value(7), value(10), value(2)),
    CurriculumFrontier(meta("frontier"), "frontier-7", ("B.NEXT",), ("C.HELD",),
                       ("A.DONE",)),
    LearningEpisode(meta("episode"), "episode-1", "B.EXAMPLE", "visit-1",
                    "COMPLETED", 100, 110),
    CandidateDecision(meta("decision"), "candidate-1", "B.EXAMPLE",
                      CandidateOutcome.ACCEPTED, "SOURCE_GOLD_PASS"),
    SemanticAtlasSnapshot(meta("atlas"), "atlas-bundle", D1, "source-bundle",
                          value(30), value(40), value(10)),
    FrameCompileReceipt(meta("frame"), "frame-1", D1, D2, False, 2),
    NeuralRuntimeSample(meta("runtime"), 42, value(12.5, "ms"),
                        value(1000, "parameters"), value(0.25, "fraction")),
    MemorySnapshot(meta("memory"), value(100, "bytes"), value(1000, "bytes"),
                   value(8), value(2), value(1)),
    TeacherSnapshot(meta("teacher"), "teacher-a", 3, "strategy-2",
                    value(10), value(7), value(3)),
    SalienceEvent(meta("salience"), "salience-1", "B.EXAMPLE",
                  value(3, "ordinal", ValueOrigin.SOURCE_AUTHORITATIVE),
                  value(2, "ordinal", ValueOrigin.DERIVED),
                  value(4, "ordinal", ValueOrigin.INFERRED), "TEACHING"),
    CorrectionEvent(meta("correction"), "correction-1", 4, "source:a", D1, D2,
                    "REQUALIFICATION_REQUIRED"),
    GenerationManifest(meta("generation"), D1, D2, D3, D4, "ACCEPTED"),
    ResourceSample(meta("resources"), value(100, "bytes"), value(1000, "bytes"),
                   value(500, "bytes"), value(1.5, "steps/minute")),
    OperatorActionRequest(meta("action-request"), "request-1", "idem-1", "dry-run",
                          (ActionParameter("mode", "bounded"),), True, 119),
    OperatorActionReceipt(meta("action-receipt"), "request-1", "operation-1",
                          ActionReceiptState.COMPLETED, 120, "postcondition:a", None),
    ErrorEnvelope(meta("error", run=None), "RUN_NOT_FOUND", "run unavailable", None),
    UnavailableEnvelope(meta("unavailable", run=None, coverage=CoverageState.UNKNOWN),
                        "run:missing", UnavailableReason.MISSING, None),
    StaleEnvelope(meta("stale", coverage=CoverageState.PARTIAL), "operator-view", 100, 118),
    PartialEnvelope(meta("partial", coverage=CoverageState.PARTIAL), "school",
                    ("mastered_count",)),
    EventEnvelope(
        meta("event"),
        "event-9",
        StreamPosition(
            "run-7:candidate",
            "epoch-1",
            9,
            event_cursor_sha256(
                stream_id="run-7:candidate",
                epoch_id="epoch-1",
                ordinal=9,
                event_id="event-9",
                payload_schema_version=CandidateDecision.SCHEMA,
                payload_record_id="decision",
                payload_sha256=D1,
            ),
            D4,
        ),
        "candidate",
        CandidateDecision.SCHEMA,
        "decision",
        D1,
        "evidence:event-9",
    ),
)
