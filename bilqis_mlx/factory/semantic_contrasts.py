"""Public BAMF A11.1 semantic-contrast API.

Implementation is split by contract, immutable model, transformation, and checker
responsibility so the public surface stays stable while each module remains small.
"""
from bilqis_mlx.factory.semantic_contrast_checker import check_contrast, generate_contrasts
from bilqis_mlx.factory.semantic_contrast_models import ContrastLineage, ContrastVariant, LessonSpec
from bilqis_mlx.factory.semantic_contrast_types import (
    AllowedVariation,
    ContrastFamily,
    ContrastSourceFrame,
    ObservationState,
    TemporalStatus,
)

__all__ = (
    "AllowedVariation",
    "ContrastFamily",
    "ContrastLineage",
    "ContrastSourceFrame",
    "ContrastVariant",
    "LessonSpec",
    "ObservationState",
    "TemporalStatus",
    "check_contrast",
    "generate_contrasts",
)
