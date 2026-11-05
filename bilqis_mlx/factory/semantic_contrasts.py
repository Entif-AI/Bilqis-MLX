"""Public BAMF A11.1 semantic-contrast API.

Implementation is split by contract, immutable model, transformation, and checker
responsibility so the public surface stays stable while each module remains small.
"""
from bilqis_mlx.factory.semantic_contrast.checker import check_contrast, generate_contrasts
from bilqis_mlx.factory.semantic_contrast.ambiguity import (
    MAX_AMBIGUITY_INTERPRETATIONS,
    AmbiguityExploration,
    AmbiguityTarget,
    NoiseSignature,
    NoisyLessonPresentation,
    apply_presentation_noise,
    explore_ambiguity,
)
from bilqis_mlx.factory.semantic_contrast.models import ContrastLineage, ContrastVariant, LessonSpec
from bilqis_mlx.factory.semantic_contrast.types import (
    AllowedVariation,
    ContrastFamily,
    ContrastSourceFrame,
    ObservationState,
    TemporalStatus,
)

__all__ = (
    "AllowedVariation",
    "AmbiguityExploration",
    "AmbiguityTarget",
    "ContrastFamily",
    "ContrastLineage",
    "ContrastSourceFrame",
    "ContrastVariant",
    "LessonSpec",
    "MAX_AMBIGUITY_INTERPRETATIONS",
    "NoiseSignature",
    "NoisyLessonPresentation",
    "ObservationState",
    "TemporalStatus",
    "apply_presentation_noise",
    "check_contrast",
    "explore_ambiguity",
    "generate_contrasts",
)
