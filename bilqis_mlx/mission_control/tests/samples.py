"""Literal samples spanning every CP02 top-level record type."""
from .sample_parts.base import (
    BASE_SAMPLES, D1, D2, D3, D4, RUN, SEMANTIC_CONCEPT_ID, SEMANTIC_HELD_META,
    SEMANTIC_ID, SEMANTIC_SOURCE_META, meta, value,
)
from .sample_parts.trainer import TRAINER_SAMPLES

from ..contracts.events import LearningHistorySummary

SAMPLES = (*BASE_SAMPLES, *TRAINER_SAMPLES,
           LearningHistorySummary(meta("learning-summary"), D1, 0, 0, 0, 0, (), None))

__all__ = (
    "D1", "D2", "D3", "D4", "RUN", "SEMANTIC_ID", "SEMANTIC_CONCEPT_ID",
    "SEMANTIC_SOURCE_META", "SEMANTIC_HELD_META", "meta", "value", "SAMPLES",
)
