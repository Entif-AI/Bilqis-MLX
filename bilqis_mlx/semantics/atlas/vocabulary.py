"""A02 source-bound staging for prospective semantic identity factors."""
from .vocabulary_contracts import (
    STAGED_ONLY, CandidateState, VocabularyAllocation, VocabularyBankParent,
    VocabularyExtension, VocabularyPrior,
)
from .vocabulary_factors import prepare_identity_factors
from .vocabulary_planning import plan_vocabulary_extension
from .vocabulary_staging import apply_vocabulary_extension, staged_tied_logits

__all__ = (
    "CandidateState",
    "STAGED_ONLY",
    "VocabularyAllocation",
    "VocabularyBankParent",
    "VocabularyExtension",
    "VocabularyPrior",
    "apply_vocabulary_extension",
    "plan_vocabulary_extension",
    "prepare_identity_factors",
    "staged_tied_logits",
)
