"""Literal public BRAVO fixture receipt and replay verifier for BAMF A10.3."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from bilqis_mlx.errors import BilqisError, ErrorBus, SCHOOL
from bilqis_mlx.factory.evidence_curriculum import (
    EvidenceLesson, EvidenceSplitReceipt, LessonCandidateSet,
    compile_evidence_lessons, split_evidence_families,
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
    SourceSpan,
    build_public_fixture_snapshot,
    parse_public_fixture_source,
    source_manifest_semantic_authority,
)
from bilqis_mlx.source_adapters.bravo.receipt import (
    EXPECTED_ACTOR_REF, EXPECTED_QUESTIONS, EXPECTED_RECORD_ID,
    EXPECTED_RENDERED, EXPECTED_REPORTED_DECIMAL, EXPECTED_STATUS,
    ExternalGoldWitness, ExternalWitnessSplitReceipt, F10WitnessProof,
    FIXTURE_SCHEMA, PublicBravoFixtureReceipt,
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
) -> tuple[ExternalGoldWitness, ...]:
    lessons = candidates.lessons
    if (tuple(lesson.question for lesson in lessons) != EXPECTED_QUESTIONS
            or len(lessons) != len(EXPECTED_QUESTIONS)):
        _fail("BAMF_PUBLIC_BRAVO_QUESTION_SET_INVALID")
    rows = []
    for lesson in lessons:
        if not lesson.check():
            _fail("BAMF_PUBLIC_BRAVO_CHECKER_FAILED")
        rows.append(ExternalGoldWitness(
            lesson_id=lesson.lesson_id,
            source_manifest_cid=snapshot.source_manifest_cid,
            source_byte_digest=snapshot.source_byte_digest,
            source_span_start=record.source_span.start,
            source_span_end=record.source_span.end,
            source_family_id=lesson.source_family_id,
            interpretation_revision=lesson.frame.interpretation_revision,
            semantic_release=snapshot.semantic_release,
            rights=lesson.rights,
            checker_id=lesson.checker_id,
            question=lesson.question,
            gold=lesson.gold,
        ))
    return tuple(rows)


def _same_family_rejection(
    snapshot: BamfEvidenceSnapshot,
    rights: EvidenceRights,
    record: EvidenceRecord,
) -> str:
    renamed = replace(
        record,
        record_id="fixture-001-renamed",
        adjudication_ref="adjudication:renamed-does-not-create-evidence",
    )
    candidates = compile_evidence_lessons(
        replace(snapshot, records=(record, renamed)),
        rights,
        snapshot.semantic_release,
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


def _independent_snapshot(
    primary_snapshot: BamfEvidenceSnapshot,
) -> tuple[BamfEvidenceSnapshot, EvidenceRights]:
    authority = source_manifest_semantic_authority(primary_snapshot)
    start = len(PUBLIC_FIXTURE_SOURCE) + 1
    parsed = parse_public_fixture_source(
        PUBLIC_INDEPENDENT_SOURCE,
        category_ref=authority.category_ref,
        hour_unit_ref=authority.hour_unit_ref,
        agent_role_ref=authority.agent_role_ref,
    )
    record = replace(
        parsed,
        record_id="fixture-002",
        source_span=SourceSpan(start, start + len(PUBLIC_INDEPENDENT_SOURCE)),
        adjudication_ref="adjudication:independent-public-fixture-002",
    )
    rights = EvidenceRights(PUBLIC_FIXTURE, "TRAINING", True, True)
    snapshot = BamfEvidenceSnapshot(
        snapshot_id="bamf-public-fixture-002",
        source_manifest_cid=PUBLIC_INDEPENDENT_MANIFEST_CID,
        source_byte_digest=sha256(
            PUBLIC_INDEPENDENT_BUNDLE_SOURCE.encode("utf-8")).hexdigest(),
        interpretation_revision="bravo-public-fixture/v1",
        semantic_release=authority.semantic_release,
        rights=rights,
        records=(record,),
    )
    return snapshot, rights


def _independent_split(
    primary_witnesses: tuple[ExternalGoldWitness, ...],
    primary_snapshot: BamfEvidenceSnapshot,
) -> ExternalWitnessSplitReceipt:
    snapshot, rights = _independent_snapshot(primary_snapshot)
    record = snapshot.records[0]
    candidates = compile_evidence_lessons(
        snapshot, rights, snapshot.semantic_release)
    heldout = _witnesses(candidates, snapshot, record)
    train_family = primary_witnesses[0].source_family_id
    heldout_family = heldout[0].source_family_id
    if any(item.source_family_id != heldout_family for item in heldout):
        _fail("BAMF_PUBLIC_BRAVO_INDEPENDENT_FAMILY_INVALID")
    return ExternalWitnessSplitReceipt(
        train_family_id=train_family,
        heldout_family_id=heldout_family,
        train_source_digest=primary_snapshot.source_byte_digest,
        heldout_source_digest=snapshot.source_byte_digest,
        train_source_manifest_cid=primary_snapshot.source_manifest_cid,
        heldout_source_manifest_cid=snapshot.source_manifest_cid,
        heldout_rights=rights,
        heldout_witnesses=heldout,
    )


def compile_public_bravo_fixture_receipt(
    *, atlas_selection: AtlasArtifactSelection,
) -> PublicBravoFixtureReceipt:
    """Replay source owners and exact checkers into one public acceptance receipt."""
    snapshot, rights = build_public_fixture_snapshot(
        atlas_selection=atlas_selection)
    record = _record(snapshot)
    candidates = compile_evidence_lessons(
        snapshot, rights, snapshot.semantic_release)
    witnesses = _witnesses(candidates, snapshot, record)
    first: EvidenceLesson = candidates.lessons[0]
    expected_golds = (
        first.frame.category_ref, EXPECTED_STATUS,
        EXPECTED_REPORTED_DECIMAL, "15")
    if (tuple(item.gold for item in witnesses) != expected_golds
            or first.rendered != EXPECTED_RENDERED):
        _fail("BAMF_PUBLIC_BRAVO_GOLD_INVALID")
    split: EvidenceSplitReceipt = split_evidence_families(
        candidates,
        train_record_ids=(record.record_id,),
        heldout_record_ids=(),
    )
    f10_proof = F10WitnessProof(
        same_family_rejection_reason=_same_family_rejection(
            snapshot, rights, record),
        independent_split=_independent_split(witnesses, snapshot),
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
        semantic_release=snapshot.semantic_release,
        interpretation_revision=snapshot.interpretation_revision,
        rights=rights,
        source_family_id=first.source_family_id,
        rendered=first.rendered,
        witnesses=witnesses,
        split_receipt=split,
        f10_proof=f10_proof,
    )


def verify_public_bravo_fixture_receipt(
    receipt: PublicBravoFixtureReceipt,
    *,
    atlas_selection: AtlasArtifactSelection,
) -> PublicBravoFixtureReceipt:
    """Reconstruct public evidence and reject even self-consistently rehashed tampering."""
    if type(receipt) is not PublicBravoFixtureReceipt:
        _fail("BAMF_PUBLIC_BRAVO_RECEIPT_INVALID")
    expected = compile_public_bravo_fixture_receipt(
        atlas_selection=atlas_selection)
    if receipt != expected or receipt.receipt_sha256 != expected.receipt_sha256:
        _fail("BAMF_PUBLIC_BRAVO_REPLAY_MISMATCH")
    return receipt
