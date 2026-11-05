"""Integrity-bearing receipt types for the BAMF A10.3 public BRAVO fixture."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.factory.evidence_curriculum import EvidenceSplitReceipt
from bilqis_mlx.source_adapters.evidence_frames import (
    PUBLIC_FIXTURE,
    PUBLIC_FIXTURE_SOURCE,
    EvidenceRights,
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
EXPECTED_GOLDS = {
    "Planned or completed?": EXPECTED_STATUS,
    "What reported duration?": EXPECTED_REPORTED_DECIMAL,
    "Convert the reported duration to minutes.": "15",
}
EXPECTED_SAME_FAMILY_REJECTION = "BAMF_EVIDENCE_SPLIT_WITNESS_NOT_INDEPENDENT"


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _split_digest(split: EvidenceSplitReceipt) -> str:
    payload = repr((
        split.train_record_ids,
        split.heldout_record_ids,
        split.train_family_ids,
        split.heldout_family_ids,
    )).encode("utf-8")
    return sha256(payload).hexdigest()


@dataclass(frozen=True)
class PublicLessonWitness:
    lesson_id: str
    source_family_id: str
    interpretation_revision: str
    rights_regime: str
    checker_id: str
    checker_passed: bool
    external_witness_ref: str
    source_manifest_cid: str
    source_byte_digest: str
    source_span_start: int
    source_span_end: int
    question: str
    gold: str

    def __post_init__(self) -> None:
        if (self.rights_regime != PUBLIC_FIXTURE
                or self.checker_id != "bilqis.evidence-exact-checker/v1"
                or self.checker_passed is not True
                or not self.external_witness_ref
                or not self.source_manifest_cid
                or self.source_span_start < 0
                or self.source_span_end <= self.source_span_start):
            _fail("BAMF_PUBLIC_BRAVO_LESSON_WITNESS_INVALID")

    @property
    def source_binding_sha256(self) -> str:
        return canonical_digest({
            "source_manifest_cid": self.source_manifest_cid,
            "source_byte_digest": self.source_byte_digest,
            "source_span": (self.source_span_start, self.source_span_end),
            "external_witness_ref": self.external_witness_ref,
            "lesson_id": self.lesson_id,
            "question": self.question,
            "gold": self.gold,
        })


@dataclass(frozen=True)
class ExternalWitnessSplitReceipt:
    train_family_id: str
    heldout_family_id: str
    train_source_digest: str
    heldout_source_digest: str
    train_source_manifest_cid: str
    heldout_source_manifest_cid: str
    heldout_external_witness_ref: str

    def __post_init__(self) -> None:
        if (self.train_family_id == self.heldout_family_id
                or self.train_source_digest == self.heldout_source_digest
                or self.train_source_manifest_cid == self.heldout_source_manifest_cid
                or not self.heldout_external_witness_ref):
            _fail("BAMF_PUBLIC_BRAVO_EXTERNAL_SPLIT_INVALID")

    @property
    def receipt_sha256(self) -> str:
        return canonical_digest(asdict(self))


@dataclass(frozen=True)
class F10WitnessProof:
    same_family_rejection_reason: str
    independent_split: ExternalWitnessSplitReceipt

    def __post_init__(self) -> None:
        if self.same_family_rejection_reason != EXPECTED_SAME_FAMILY_REJECTION:
            _fail("BAMF_PUBLIC_BRAVO_F10_REJECTION_INVALID")


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
    f10_proof: F10WitnessProof

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
                or self.split_receipt.receipt_sha256 != _split_digest(self.split_receipt)
                or any(w.source_family_id != self.source_family_id for w in self.witnesses)
                or any(w.interpretation_revision != self.interpretation_revision
                       for w in self.witnesses)
                or any(w.rights_regime != self.rights.regime for w in self.witnesses)
                or any(w.source_manifest_cid != self.source_manifest_cid for w in self.witnesses)
                or any(w.source_byte_digest != self.source_byte_digest for w in self.witnesses)):
            _fail("BAMF_PUBLIC_BRAVO_RECEIPT_INVALID")

    @property
    def receipt_sha256(self) -> str:
        return canonical_digest(asdict(self))
