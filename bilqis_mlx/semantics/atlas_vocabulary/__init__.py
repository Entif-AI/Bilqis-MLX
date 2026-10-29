"""Source-bound semantic identity staging; no learner admission authority."""
from ..atlas_snapshot import load_pinned_atlas_snapshot
from .models import (VOCABULARY_PRIOR_SCHEMA, VOCABULARY_EXTENSION_SCHEMA,
    VOCABULARY_CANDIDATE_SCHEMA, STAGED_ONLY, UINT32_MAX, FP32_BYTES,
    ADAMW_ARRAYS_PER_ROW, VocabularyPrior, VocabularyAllocation,
    VocabularyExtension, VocabularyBankParent, CandidateState)
from .planning import (plan_vocabulary_extension, prepare_identity_factors)
from .staging import apply_vocabulary_extension
from .readout import staged_tied_logits

__all__ = [
    "VocabularyPrior", "VocabularyAllocation", "VocabularyExtension",
    "VocabularyBankParent", "CandidateState", "plan_vocabulary_extension",
    "prepare_identity_factors", "apply_vocabulary_extension",
    "staged_tied_logits", "STAGED_ONLY",
]
