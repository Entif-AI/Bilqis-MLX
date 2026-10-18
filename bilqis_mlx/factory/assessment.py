"""Qualification law shared by runtime and historical regression evidence."""
from __future__ import annotations

from .model import AssessmentClass, LearningEvidence


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
