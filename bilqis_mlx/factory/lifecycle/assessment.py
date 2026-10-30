"""Qualification law shared by runtime and historical regression evidence."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .executable_release import ExecutableFactoryRelease
from .model import AssessmentClass, LearningEvidence


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AssessmentScopeContract:
    """Exact measurement and source identity for one active capability scope."""

    capabilities: tuple[str, ...]
    rubric_sha256: str
    source_sha256: str
    factory_release_sha256: str
    semantic_catalog_sha256: str
    generator_version: str


def assessment_scope_contract(
        release: ExecutableFactoryRelease,
        capabilities) -> AssessmentScopeContract:
    """Derive exact scope identities from v2 projections, never grade identity."""
    if not isinstance(release, ExecutableFactoryRelease):
        raise TypeError("FACTORY_ASSESSMENT_EXECUTABLE_RELEASE_REQUIRED")
    release.verify()
    requested = tuple(capabilities)
    if not requested:
        raise ValueError("FACTORY_ASSESSMENT_SCOPE_EMPTY")
    if len(set(requested)) != len(requested):
        raise ValueError("FACTORY_ASSESSMENT_SCOPE_DUPLICATE_CAPABILITY")

    known = tuple(
        item.capability_id for item in release.execution_plan.capabilities)
    unknown = set(requested) - set(known)
    if unknown:
        raise ValueError(
            "FACTORY_ASSESSMENT_SCOPE_UNKNOWN_CAPABILITY:"
            + ",".join(sorted(unknown)))
    selected = set(requested)
    scope = tuple(capability for capability in known if capability in selected)

    projections = {
        item.capability_id: item
        for item in release.execution_plan.capability_projection_digests}
    receipts = {
        item.capability_id: item
        for item in release.verification.capabilities}
    rubric_sha256 = _digest({
        "schema": "bilqis.mlx.assessment-scope-rubric/v2",
        "capabilities": scope,
        "assessment_projections": tuple(
            (capability, projections[capability].assessment)
            for capability in scope),
    })
    source_sha256 = _digest({
        "schema": "bilqis.mlx.assessment-scope-source/v2",
        "capabilities": scope,
        "source_projections": tuple(
            (capability, projections[capability].source)
            for capability in scope),
        "verified_receipts": tuple(
            (capability, receipts[capability].digest())
            for capability in scope),
    })
    return AssessmentScopeContract(
        capabilities=scope,
        rubric_sha256=rubric_sha256,
        source_sha256=source_sha256,
        factory_release_sha256=release.release_sha256,
        semantic_catalog_sha256=release.semantic_catalog_sha256,
        generator_version=source_sha256,
    )


def qualification_complete(promotion: LearningEvidence,
                           generalization: LearningEvidence) -> bool:
    """Require classroom mastery plus one distinct fresh qualification proof."""
    if not isinstance(promotion, LearningEvidence) or not isinstance(generalization, LearningEvidence):
        raise TypeError("FACTORY_QUALIFICATION_EVIDENCE_REQUIRED")
    if (promotion.assessment_class is not AssessmentClass.PROMOTION or
            generalization.assessment_class is not AssessmentClass.GENERALIZATION):
        raise ValueError("FACTORY_QUALIFICATION_EVIDENCE_CLASS_INVALID")
    if (promotion.checkpoint_sha256 != generalization.checkpoint_sha256 or
            promotion.optimizer_step != generalization.optimizer_step):
        raise ValueError("FACTORY_QUALIFICATION_CHECKPOINT_MISMATCH")
    if promotion.cohort_sha256 == generalization.cohort_sha256:
        raise ValueError("FACTORY_GENERALIZATION_MUST_USE_DISTINCT_COHORT")
    if generalization.contaminated_for_qualification:
        return False
    return promotion.passed and generalization.passed
