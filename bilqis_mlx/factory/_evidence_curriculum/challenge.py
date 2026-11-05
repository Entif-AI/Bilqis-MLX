"""Family-first reconstruction and challenge planning for A10 evidence."""
from __future__ import annotations

from hashlib import sha256

from bilqis_mlx.errors import ErrorBus, SCHOOL

from .types import (
    EvidenceChallengePlan, EvidenceLesson, EvidenceSplitReceipt,
    LessonCandidateSet, TypedEvidenceReconstruction,
)


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def compile_typed_reconstructions(
    candidates: LessonCandidateSet,
) -> tuple[TypedEvidenceReconstruction, ...]:
    """Project each source episode without collapsing reported and derived state."""
    by_record: dict[str, list[EvidenceLesson]] = {}
    for lesson in candidates.lessons:
        by_record.setdefault(lesson.record_id, []).append(lesson)
    rows = []
    for record_id in sorted(by_record):
        lessons = by_record[record_id]
        first = lessons[0]
        frame = first.frame
        derivations = tuple(
            lesson.derivation for lesson in lessons if lesson.derivation is not None)
        rows.append(TypedEvidenceReconstruction(
            record_id=record_id,
            source_family_id=first.source_family_id,
            interpretation_revision=candidates.interpretation_revision,
            rights=candidates.rights,
            template_lineage=first.template_lineage,
            actor_ref=frame.actor_ref,
            category_ref=frame.category_ref,
            status=frame.status,
            reported_value=frame.reported_decimal,
            reported_unit_ref=frame.reported_unit_ref,
            computed_values=derivations,
            negated=frame.negated,
            event_time=frame.event_time,
            alternatives=frame.alternatives,
            verification_state=frame.verification_state,
        ))
    return tuple(rows)


def _template_groups(
    candidates: LessonCandidateSet, record_ids: tuple[str, ...],
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    selected = set(record_ids)
    groups: dict[tuple[str, str], list[str]] = {}
    for lesson in candidates.lessons:
        if lesson.record_id in selected:
            groups.setdefault(
                (lesson.source_family_id, lesson.template_lineage), []
            ).append(lesson.lesson_id)
    return tuple(
        (family, lineage, tuple(sorted(ids)))
        for (family, lineage), ids in sorted(groups.items()))


def split_evidence_families(
    candidates: LessonCandidateSet, *,
    train_record_ids: tuple[str, ...],
    heldout_record_ids: tuple[str, ...],
) -> EvidenceSplitReceipt:
    """Prove one underlying source episode cannot straddle an independent split."""
    if set(train_record_ids) & set(heldout_record_ids):
        _fail("BAMF_EVIDENCE_SPLIT_RECORD_OVERLAP")
    by_record: dict[str, str] = {}
    for lesson in candidates.lessons:
        prior = by_record.setdefault(lesson.record_id, lesson.source_family_id)
        if prior != lesson.source_family_id:
            _fail("BAMF_EVIDENCE_SPLIT_FAMILY_DRIFT")
    if any(item not in by_record for item in (*train_record_ids, *heldout_record_ids)):
        _fail("BAMF_EVIDENCE_SPLIT_RECORD_UNKNOWN")
    train = tuple(sorted({by_record[item] for item in train_record_ids}))
    held = tuple(sorted({by_record[item] for item in heldout_record_ids}))
    if set(train) & set(held):
        _fail("BAMF_EVIDENCE_SPLIT_WITNESS_NOT_INDEPENDENT")
    payload = repr((
        train_record_ids,
        heldout_record_ids,
        train,
        held,
        candidates.interpretation_revision,
        candidates.rights,
    )).encode("utf-8")
    return EvidenceSplitReceipt(
        train_record_ids=tuple(train_record_ids),
        heldout_record_ids=tuple(heldout_record_ids),
        train_family_ids=train,
        heldout_family_ids=held,
        interpretation_revision=candidates.interpretation_revision,
        rights=candidates.rights,
        receipt_sha256=sha256(payload).hexdigest(),
    )


def plan_fresh_challenge(
    candidates: LessonCandidateSet, *,
    train_record_ids: tuple[str, ...],
    heldout_record_ids: tuple[str, ...],
) -> EvidenceChallengePlan:
    """Split immutable source families first, then group renderings on each side."""
    split = split_evidence_families(
        candidates,
        train_record_ids=train_record_ids,
        heldout_record_ids=heldout_record_ids,
    )
    heldout_lesson_ids = tuple(sorted(
        lesson.lesson_id for lesson in candidates.lessons
        if lesson.record_id in set(heldout_record_ids)))
    return EvidenceChallengePlan(
        split=split,
        interpretation_revision=candidates.interpretation_revision,
        rights=candidates.rights,
        train_template_groups=_template_groups(candidates, train_record_ids),
        heldout_template_groups=_template_groups(candidates, heldout_record_ids),
        post_exam_teachable_lesson_ids=heldout_lesson_ids,
    )
