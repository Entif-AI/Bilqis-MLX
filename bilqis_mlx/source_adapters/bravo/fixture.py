"""Literal public BRAVO fixture acceptance receipt for BAMF A10.3.

This module commits the public-safe fixture witness, not a second evidence
compiler.  It binds the exact source bytes to the already-owned A10.1/A10.2
parser, frame, lesson, checker, family, rights, and interpretation contracts.
"""
from __future__ import annotations

from hashlib import sha256

from bilqis_mlx.errors import BilqisError, ErrorBus, SCHOOL
from bilqis_mlx.factory.evidence_curriculum import (
    EvidenceLesson,
    EvidenceSplitReceipt,
    LessonCandidateSet,
    compile_evidence_lessons,
    split_evidence_families,
)
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.source_adapters.evidence_frames import (
    PUBLIC_FIXTURE,
    PUBLIC_FIXTURE_SOURCE,
    PUBLIC_INDEPENDENT_BUNDLE_SOURCE,
    PUBLIC_INDEPENDENT_MANIFEST_CID,
    PUBLIC_INDEPENDENT_SOURCE,
    BamfEvidenceSnapshot,
    EvidenceRecord,
    EvidenceRights,
    build_public_fixture_snapshot,
    parse_public_fixture_source,
)
from bilqis_mlx.source_adapters.bravo.receipt import (
    EXPECTED_ACTOR_REF,
    EXPECTED_GOLDS,
    EXPECTED_QUESTIONS,
    EXPECTED_RECORD_ID,
    EXPECTED_RENDERED,
    EXPECTED_REPORTED_DECIMAL,
    EXPECTED_STATUS,
    ExternalWitnessSplitReceipt,
    F10WitnessProof,
    FIXTURE_SCHEMA,
    PublicBravoFixtureReceipt,
    PublicLessonWitness,
)


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _record(snapshot: BamfEvidenceSnapshot) -> EvidenceRecord:
    if len(snapshot.records) != 1:
        _fail("BAMF_PUBLIC_BRAVO_RECORD_COUNT_INVALID")
    record = snapshot.records[0]
    if (record.record_id != EXPECTED_RECORD_ID
            or record.actor_ref != EXPECTED_ACTOR_REF
            or record.status != EXPECTED_STATUS
            or record.reported_value.decimal != EXPECTED_REPORTED_DECIMAL):
        _fail("BAMF_PUBLIC_BRAVO_RECORD_INVALID")
    return record


def _witnesses(
    candidates: LessonCandidateSet,
    snapshot: BamfEvidenceSnapshot,
    record: EvidenceRecord,
) -> tuple[PublicLessonWitness, ...]:
    if tuple(lesson.question for lesson in candidates.lessons) != EXPECTED_QUESTIONS:
        _fail("BAMF_PUBLIC_BRAVO_QUESTION_SET_INVALID")
    if not candidates.lessons:
        _fail("BAMF_PUBLIC_BRAVO_LESSONS_MISSING")
    actual_golds = {lesson.question: lesson.gold for lesson in candidates.lessons}
    if any(actual_golds.get(question) != gold for question, gold in EXPECTED_GOLDS):
        _fail("BAMF_PUBLIC_BRAVO_GOLD_INVALID")
    rows = tuple(PublicLessonWitness(
        lesson_id=lesson.lesson_id,
        source_family_id=lesson.source_family_id,
        interpretation_revision=lesson.frame.interpretation_revision,
        rights_regime=lesson.rights.regime,
        checker_id=lesson.checker_id,
        checker_passed=lesson.check(),
        external_witness_ref=record.adjudication_ref or "",
        source_manifest_cid=snapshot.source_manifest_cid,
        source_byte_digest=snapshot.source_byte_digest,
        source_span_start=record.source_span.start,
        source_span_end=record.source_span.end,
        question=lesson.question,
        gold=lesson.gold,
    ) for lesson in candidates.lessons)
    if not all(row.checker_passed for row in rows):
        _fail("BAMF_PUBLIC_BRAVO_CHECKER_FAILED")
    return rows


def _same_family_rejection(
    snapshot: BamfEvidenceSnapshot,
    rights: EvidenceRights,
    semantic_release: str,
    record: EvidenceRecord,
) -> str:
    renamed = EvidenceRecord(
        record_id="fixture-001-renamed",
        actor_ref=record.actor_ref,
        source_span=record.source_span,
        category_ref=record.category_ref,
        category_label=record.category_label,
        status=record.status,
        reported_value=record.reported_value,
        unit_label=record.unit_label,
        event_time=record.event_time,
        observed_at=record.observed_at,
        alternatives=record.alternatives,
        adjudication_ref="adjudication:renamed-does-not-create-evidence",
        agent_role_ref=record.agent_role_ref,
        negated=record.negated,
    )
    candidates = compile_evidence_lessons(
        BamfEvidenceSnapshot(
            snapshot_id=snapshot.snapshot_id,
            source_manifest_cid=snapshot.source_manifest_cid,
            source_byte_digest=snapshot.source_byte_digest,
            interpretation_revision=snapshot.interpretation_revision,
            semantic_release=snapshot.semantic_release,
            rights=snapshot.rights,
            records=(record, renamed),
        ),
        rights,
        semantic_release,
    )
    try:
        split_evidence_families(
            candidates,
            train_record_ids=(record.record_id,),
            heldout_record_ids=(renamed.record_id,),
        )
    except BilqisError as exc:
        return str(exc.context.get("reason", ""))
    _fail("BAMF_PUBLIC_BRAVO_SAME_FAMILY_ADVERSARY_ACCEPTED")


def _independent_split(
    primary: PublicLessonWitness,
    primary_snapshot: BamfEvidenceSnapshot,
) -> ExternalWitnessSplitReceipt:
    semantic_release = primary_snapshot.semantic_release
    primary_record = _record(primary_snapshot)
    source_digest = sha256(PUBLIC_INDEPENDENT_BUNDLE_SOURCE.encode("utf-8")).hexdigest()
    record = parse_public_fixture_source(
        PUBLIC_INDEPENDENT_SOURCE,
        category_ref=primary_record.category_ref,
        hour_unit_ref=primary_record.reported_value.unit_ref,
        agent_role_ref=primary_record.agent_role_ref,
    )
    second_start = len(PUBLIC_FIXTURE_SOURCE) + 1
    record = EvidenceRecord(
        record_id="fixture-002",
        actor_ref=record.actor_ref,
        source_span=type(record.source_span)(
            second_start, second_start + len(PUBLIC_INDEPENDENT_SOURCE)),
        category_ref=record.category_ref,
        category_label=record.category_label,
        status=record.status,
        reported_value=record.reported_value,
        unit_label=record.unit_label,
        event_time=record.event_time,
        observed_at=record.observed_at,
        alternatives=record.alternatives,
        adjudication_ref="adjudication:independent-public-fixture-002",
        agent_role_ref=record.agent_role_ref,
    )
    rights = EvidenceRights(PUBLIC_FIXTURE, "TRAINING", True, True)
    snapshot = BamfEvidenceSnapshot(
        snapshot_id="bamf-public-fixture-002",
        source_manifest_cid=PUBLIC_INDEPENDENT_MANIFEST_CID,
        source_byte_digest=source_digest,
        interpretation_revision="bravo-public-fixture/v1",
        semantic_release=semantic_release,
        rights=rights,
        records=(primary_record, record),
    )
    candidates = compile_evidence_lessons(snapshot, rights, semantic_release)
    heldout = next(
        lesson for lesson in candidates.lessons if lesson.record_id == record.record_id)
    if not heldout.check():
        _fail("BAMF_PUBLIC_BRAVO_INDEPENDENT_CHECKER_FAILED")
    return ExternalWitnessSplitReceipt(
        train_family_id=primary.source_family_id,
        heldout_family_id=heldout.source_family_id,
        train_source_digest=primary_snapshot.source_byte_digest,
        heldout_source_digest=snapshot.source_byte_digest,
        train_source_manifest_cid=primary_snapshot.source_manifest_cid,
        heldout_source_manifest_cid=snapshot.source_manifest_cid,
        heldout_external_witness_ref=record.adjudication_ref or "",
    )


def compile_public_bravo_fixture_receipt(
    *,
    atlas_selection: AtlasArtifactSelection,
) -> PublicBravoFixtureReceipt:
    """Compile the exact public fixture and bind every derivative to one family."""
    snapshot, rights = build_public_fixture_snapshot(
        atlas_selection=atlas_selection,
    )
    record = _record(snapshot)
    semantic_release = snapshot.semantic_release
    candidates = compile_evidence_lessons(snapshot, rights, semantic_release)
    witnesses = _witnesses(candidates, snapshot, record)
    first: EvidenceLesson = next(iter(candidates.lessons))
    if (first.frame.category_ref != record.category_ref
            or first.frame.actor_role_ref != record.agent_role_ref
            or first.frame.reported_unit_ref != record.reported_value.unit_ref
            or first.rendered != EXPECTED_RENDERED):
        _fail("BAMF_PUBLIC_BRAVO_FRAME_INVALID")
    split = split_evidence_families(
        candidates,
        train_record_ids=(record.record_id,),
        heldout_record_ids=(),
    )
    f10_proof = F10WitnessProof(
        same_family_rejection_reason=_same_family_rejection(
            snapshot, rights, semantic_release, record),
        independent_split=_independent_split(
            witnesses[0],
            snapshot,
        ),
    )
    return PublicBravoFixtureReceipt(
        schema=FIXTURE_SCHEMA,
        source_text=PUBLIC_FIXTURE_SOURCE,
        source_byte_digest=snapshot.source_byte_digest,
        snapshot_id=snapshot.snapshot_id,
        source_manifest_cid=snapshot.source_manifest_cid,
        record_id=record.record_id,
        actor_ref=record.actor_ref,
        category_ref=record.category_ref,
        agent_role_ref=record.agent_role_ref,
        reported_unit_ref=record.reported_value.unit_ref,
        semantic_release=semantic_release,
        interpretation_revision=snapshot.interpretation_revision,
        rights=rights,
        source_family_id=first.source_family_id,
        rendered=first.rendered,
        witnesses=witnesses,
        split_receipt=split,
        f10_proof=f10_proof,
    )
