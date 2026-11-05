"""A10.1 BRAVO evidence-to-lesson compiler over provenance-safe records."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext

from bilqis_mlx.errors import BilqisError, ErrorBus, SCHOOL
from bilqis_mlx.source_adapters.evidence_frames import (
    PUBLIC_FIXTURE, UNCLASSIFIED,
    BamfEvidenceSnapshot, EvidenceDerivation, EvidenceFrame,
    EvidenceRecord, EvidenceRights, EvidenceSemanticAuthority, EventTime,
    SourceSpan, source_family_id, source_manifest_semantic_authority,
    verification_state,
)
from bilqis_mlx.semantics.cognitive_operators import TypedValue
from ._evidence_curriculum.challenge import (
    compile_typed_reconstructions, plan_fresh_challenge,
    split_evidence_families,
)
from ._evidence_curriculum.types import (
    EvidenceChallengePlan, EvidenceHold, EvidenceLesson, EvidenceLessonStatus,
    EvidenceSplitReceipt, LessonCandidateSet, TypedEvidenceReconstruction,
)


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _minutes(
    decimal: str,
    record: EvidenceRecord,
    authority: EvidenceSemanticAuthority,
) -> tuple[str, EvidenceDerivation]:
    if (record.reported_value.unit_ref != authority.hour_unit_ref
            or record.unit_label != authority.hour_unit_ref):
        _fail("BAMF_EVIDENCE_DURATION_UNIT_UNQUALIFIED")
    try:
        value = Decimal(decimal)
    except InvalidOperation:
        _fail("BAMF_EVIDENCE_DURATION_INVALID")
    if not value.is_finite() or value < 0:
        _fail("BAMF_EVIDENCE_DURATION_INVALID")
    with localcontext() as context:
        context.prec = max(1, len(value.as_tuple().digits) + 2)
        minutes = value * Decimal(60)
    normalized = format(minutes, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    normalized = normalized or "0"
    return normalized, EvidenceDerivation(
        authority.unit_operator_id, decimal, authority.hour_unit_ref,
        normalized, "min")


def _render(record: EvidenceRecord) -> str:
    decimal = record.reported_value.decimal
    if decimal is None:
        if record.negated:
            return f"{record.actor_ref} reported not {record.category_label}; duration is unknown."
        return f"{record.actor_ref} reported {record.category_label}; duration is unknown."
    if record.negated and record.status == "COMPLETED":
        return (
            f"{record.actor_ref} did not complete {record.category_label} "
            f"for {decimal} {record.unit_label}."
        )
    if record.negated and record.status == "PLANNED":
        return (
            f"{record.actor_ref} does not plan {record.category_label} "
            f"for {decimal} {record.unit_label}."
        )
    if record.negated:
        return f"{record.actor_ref} reported not {record.category_label} for {decimal} {record.unit_label}."
    if record.status == "COMPLETED":
        return f"{record.actor_ref} completed {record.category_label} for {decimal} {record.unit_label}."
    if record.status == "PLANNED":
        return f"{record.actor_ref} plans {record.category_label} for {decimal} {record.unit_label}."
    return f"{record.actor_ref} reported {record.category_label} for {decimal} {record.unit_label}."


def _template_lineage(record: EvidenceRecord) -> str:
    if record.negated:
        if record.reported_value.decimal is None:
            return "T3N"
        if record.status == "COMPLETED":
            return "T1N"
        if record.status == "PLANNED":
            return "T2N"
        return "T0N"
    if record.reported_value.decimal is None:
        return "T3"
    if record.status == "COMPLETED":
        return "T1"
    if record.status == "PLANNED":
        return "T2"
    return "T0"


def _frame(snapshot: BamfEvidenceSnapshot, record: EvidenceRecord) -> EvidenceFrame:
    return EvidenceFrame(
        record_id=record.record_id,
        actor_ref=record.actor_ref,
        actor_role_ref=record.agent_role_ref,
        category_ref=record.category_ref,
        status=record.status,
        reported_decimal=record.reported_value.decimal,
        reported_unit_ref=record.reported_value.unit_ref,
        event_time=record.event_time,
        alternatives=record.alternatives,
        negated=record.negated,
        verification_state=verification_state(record),
        source_digest=snapshot.source_byte_digest,
        interpretation_revision=snapshot.interpretation_revision,
        semantic_release=snapshot.semantic_release,
        source_family_id=source_family_id(snapshot, record),
    )


def _lessons(
    snapshot: BamfEvidenceSnapshot,
    record: EvidenceRecord,
    authority: EvidenceSemanticAuthority,
) -> tuple[EvidenceLesson, ...]:
    frame = _frame(snapshot, record)
    rendered = _render(record)
    family = frame.source_family_id
    common = dict(
        record_id=record.record_id,
        source_family_id=family,
        source_span=record.source_span,
        frame=frame,
        rendered=rendered,
        task_modality="typed-evidence-reconstruction/v1",
        positive_family="source-adjudicated-positive/v1",
        negative_family="source-authorized-contrast/v1",
        template_lineage=_template_lineage(record),
        checker_id="bilqis.evidence-exact-checker/v1",
        prerequisite_capabilities=("semantic.role.AGENT", "semantic.status", "semantic.duration"),
        rights=snapshot.rights,
    )
    rows = [
        ("category", "What category?", record.category_ref, None),
        ("status", "Planned or completed?", record.status, None),
        ("reported-duration", "What reported duration?",
         "UNKNOWN" if record.reported_value.decimal is None else record.reported_value.decimal, None),
    ]
    if record.reported_value.decimal is None:
        rows.append(("minutes", "Convert the reported duration to minutes.", "UNKNOWN", None))
    else:
        value, derivation = _minutes(
            record.reported_value.decimal, record, authority)
        rows.append(("minutes", "Convert the reported duration to minutes.", value, derivation))
    return tuple(EvidenceLesson(
        lesson_id=f"{record.record_id}:{snapshot.interpretation_revision}:{suffix}", question=question, gold=gold,
        derivation=derivation, **common) for suffix, question, gold, derivation in rows)


def compile_evidence_lessons(
    adjudicated_snapshot: BamfEvidenceSnapshot,
    source_rights: EvidenceRights,
    semantic_release: str,
) -> LessonCandidateSet:
    """Compile only currently qualified source evidence into deterministic lessons."""
    authority = source_manifest_semantic_authority(adjudicated_snapshot)
    if (type(adjudicated_snapshot) is not BamfEvidenceSnapshot
            or type(source_rights) is not EvidenceRights
            or source_rights != adjudicated_snapshot.rights
            or type(semantic_release) is not str
            or semantic_release != authority.semantic_release
            or semantic_release != adjudicated_snapshot.semantic_release):
        _fail("BAMF_EVIDENCE_COMPILER_AUTHORITY_MISMATCH")
    if (not source_rights.allowed_training
            or source_rights.regime == UNCLASSIFIED
            or (source_rights.regime == PUBLIC_FIXTURE
                and not source_rights.public_export_allowed)):
        holds = tuple(EvidenceHold(
            EvidenceLessonStatus.SOURCE_HELD,
            "RIGHTS_NOT_PUBLIC_TRAINING_QUALIFIED", record.record_id)
            for record in adjudicated_snapshot.records)
        return LessonCandidateSet(
            adjudicated_snapshot.snapshot_id,
            adjudicated_snapshot.source_byte_digest,
            adjudicated_snapshot.interpretation_revision,
            semantic_release, source_rights, (), holds)
    for record in adjudicated_snapshot.records:
        if (record.category_ref != authority.category_ref
                or record.agent_role_ref != authority.agent_role_ref):
            _fail("BAMF_EVIDENCE_COMPILER_AUTHORITY_MISMATCH")
        try:
            TypedValue(
                "UnitName", record.reported_value.unit_ref, semantic_release)
        except BilqisError:
            _fail("BAMF_EVIDENCE_COMPILER_AUTHORITY_MISMATCH")
        if (record.reported_value.unit_ref != authority.hour_unit_ref
                or record.unit_label != authority.hour_unit_ref):
            _fail("BAMF_EVIDENCE_DURATION_UNIT_UNQUALIFIED")
    qualified = tuple(record for record in adjudicated_snapshot.records
                      if record.adjudication_ref is not None)
    record_holds = tuple(EvidenceHold(
        EvidenceLessonStatus.SOURCE_HELD, "SOURCE_UNADJUDICATED", record.record_id)
        for record in adjudicated_snapshot.records if record.adjudication_ref is None)
    lessons = tuple(
        lesson for record in qualified
        for lesson in _lessons(adjudicated_snapshot, record, authority))
    return LessonCandidateSet(
        adjudicated_snapshot.snapshot_id,
        adjudicated_snapshot.source_byte_digest,
        adjudicated_snapshot.interpretation_revision,
        semantic_release, source_rights, lessons, record_holds)


# Preserve the public facade identity after the implementation was compartmentalized.
for _public_api in (
        EvidenceChallengePlan, EvidenceHold, EvidenceLesson, EvidenceLessonStatus,
        EvidenceSplitReceipt, LessonCandidateSet, TypedEvidenceReconstruction,
        compile_typed_reconstructions, plan_fresh_challenge,
        split_evidence_families):
    _public_api.__module__ = __name__
del _public_api
