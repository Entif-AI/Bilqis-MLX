"""Literal public BRAVO fixture acceptance receipt for BAMF A10.3.

This module commits the public-safe fixture witness, not a second evidence
compiler.  It binds the exact source bytes to the already-owned A10.1/A10.2
parser, frame, lesson, checker, family, rights, and interpretation contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.factory.evidence_curriculum import (
    EvidenceLesson,
    EvidenceSplitReceipt,
    LessonCandidateSet,
    compile_evidence_lessons,
    split_evidence_families,
)
from bilqis_mlx.source_adapters.evidence_frames import (
    PUBLIC_FIXTURE,
    PUBLIC_FIXTURE_SOURCE,
    BamfEvidenceSnapshot,
    EvidenceRecord,
    EvidenceRights,
    build_public_fixture_snapshot,
)


FIXTURE_SCHEMA = "bilqis.bamf.public-bravo-fixture-receipt/v1"
EXPECTED_RECORD_ID = "fixture-001"
EXPECTED_ACTOR_REF = "actor_01"
EXPECTED_STATUS = "COMPLETED"
EXPECTED_REPORTED_DECIMAL = "0.25"
EXPECTED_RENDERED = "actor_01 completed study for 0.25 h."
EXPECTED_QUESTIONS = (
    "What category?",
    "Planned or completed?",
    "What reported duration?",
    "Convert the reported duration to minutes.",
)
EXPECTED_GOLDS_SUFFIX = (EXPECTED_STATUS, EXPECTED_REPORTED_DECIMAL, "15")


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class PublicLessonWitness:
    lesson_id: str
    source_family_id: str
    interpretation_revision: str
    rights_regime: str
    checker_id: str
    checker_passed: bool
    question: str
    gold: str

    def __post_init__(self) -> None:
        if (self.rights_regime != PUBLIC_FIXTURE
                or self.checker_id != "bilqis.evidence-exact-checker/v1"
                or self.checker_passed is not True):
            _fail("BAMF_PUBLIC_BRAVO_LESSON_WITNESS_INVALID")


@dataclass(frozen=True)
class PublicBravoFixtureReceipt:
    schema: str
    source_text: str
    source_byte_digest: str
    snapshot_id: str
    source_manifest_cid: str
    record_id: str
    actor_ref: str
    category_ref: str
    agent_role_ref: str
    reported_unit_ref: str
    semantic_release: str
    interpretation_revision: str
    rights: EvidenceRights
    source_family_id: str
    rendered: str
    witnesses: tuple[PublicLessonWitness, ...]
    split_receipt: EvidenceSplitReceipt
    receipt_sha256: str

    def __post_init__(self) -> None:
        if (self.schema != FIXTURE_SCHEMA
                or self.source_text != PUBLIC_FIXTURE_SOURCE
                or self.record_id != EXPECTED_RECORD_ID
                or self.actor_ref != EXPECTED_ACTOR_REF
                or self.rendered != EXPECTED_RENDERED
                or self.rights.regime != PUBLIC_FIXTURE
                or not self.rights.allowed_training
                or not self.rights.public_export_allowed
                or not self.witnesses
                or any(w.source_family_id != self.source_family_id for w in self.witnesses)
                or any(w.interpretation_revision != self.interpretation_revision
                       for w in self.witnesses)
                or any(w.rights_regime != self.rights.regime for w in self.witnesses)):
            _fail("BAMF_PUBLIC_BRAVO_RECEIPT_INVALID")


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


def _witnesses(candidates: LessonCandidateSet) -> tuple[PublicLessonWitness, ...]:
    if tuple(lesson.question for lesson in candidates.lessons) != EXPECTED_QUESTIONS:
        _fail("BAMF_PUBLIC_BRAVO_QUESTION_SET_INVALID")
    if not candidates.lessons:
        _fail("BAMF_PUBLIC_BRAVO_LESSONS_MISSING")
    if candidates.lessons[1].gold != EXPECTED_GOLDS_SUFFIX[0]:
        _fail("BAMF_PUBLIC_BRAVO_STATUS_GOLD_INVALID")
    if candidates.lessons[2].gold != EXPECTED_GOLDS_SUFFIX[1]:
        _fail("BAMF_PUBLIC_BRAVO_REPORTED_GOLD_INVALID")
    if candidates.lessons[3].gold != EXPECTED_GOLDS_SUFFIX[2]:
        _fail("BAMF_PUBLIC_BRAVO_DERIVED_GOLD_INVALID")
    rows = tuple(PublicLessonWitness(
        lesson_id=lesson.lesson_id,
        source_family_id=lesson.source_family_id,
        interpretation_revision=lesson.frame.interpretation_revision,
        rights_regime=lesson.rights.regime,
        checker_id=lesson.checker_id,
        checker_passed=lesson.check(),
        question=lesson.question,
        gold=lesson.gold,
    ) for lesson in candidates.lessons)
    if not all(row.checker_passed for row in rows):
        _fail("BAMF_PUBLIC_BRAVO_CHECKER_FAILED")
    return rows


def compile_public_bravo_fixture_receipt(
    *,
    semantic_release: str,
    category_ref: str,
    hour_unit_ref: str,
    agent_role_ref: str,
) -> PublicBravoFixtureReceipt:
    """Compile the exact public fixture and bind every derivative to one family."""
    snapshot, rights = build_public_fixture_snapshot(
        semantic_release=semantic_release,
        category_ref=category_ref,
        hour_unit_ref=hour_unit_ref,
        agent_role_ref=agent_role_ref,
    )
    record = _record(snapshot)
    candidates = compile_evidence_lessons(snapshot, rights, semantic_release)
    witnesses = _witnesses(candidates)
    first: EvidenceLesson = candidates.lessons[0]
    if (first.frame.category_ref != category_ref
            or first.frame.actor_role_ref != agent_role_ref
            or first.frame.reported_unit_ref != hour_unit_ref
            or first.rendered != EXPECTED_RENDERED):
        _fail("BAMF_PUBLIC_BRAVO_FRAME_INVALID")
    split = split_evidence_families(
        candidates,
        train_record_ids=(record.record_id,),
        heldout_record_ids=(),
    )
    payload = {
        "schema": FIXTURE_SCHEMA,
        "source_byte_digest": snapshot.source_byte_digest,
        "snapshot_id": snapshot.snapshot_id,
        "source_manifest_cid": snapshot.source_manifest_cid,
        "record_id": record.record_id,
        "semantic_release": semantic_release,
        "interpretation_revision": snapshot.interpretation_revision,
        "source_family_id": first.source_family_id,
        "rights": {
            "regime": rights.regime,
            "purpose": rights.purpose,
            "allowed_training": rights.allowed_training,
            "public_export_allowed": rights.public_export_allowed,
        },
        "witnesses": [
            (item.lesson_id, item.checker_id, item.checker_passed, item.gold)
            for item in witnesses
        ],
        "split_receipt": split.receipt_sha256,
    }
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
        receipt_sha256=_digest(payload),
    )
