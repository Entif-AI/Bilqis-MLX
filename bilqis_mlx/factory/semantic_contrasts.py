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
from bilqis_mlx.factory.semantic_contrast.teaching import (
    CHOICE_REGISTRY_KEY,
    OPTION_ID,
    ContrastTeachingChoice,
    check_contrast_row,
    contrast_semantic_footprint,
    enrich_contrasts,
)
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
    "ContrastTeachingChoice",
    "ContrastLineage",
    "ContrastSourceFrame",
    "ContrastVariant",
    "CHOICE_REGISTRY_KEY",
    "LessonSpec",
    "MAX_AMBIGUITY_INTERPRETATIONS",
    "NoiseSignature",
    "NoisyLessonPresentation",
    "ObservationState",
    "OPTION_ID",
    "TemporalStatus",
    "apply_presentation_noise",
    "check_contrast",
    "check_contrast_row",
    "contrast_semantic_footprint",
    "enrich_contrasts",
    "explore_ambiguity",
    "generate_contrasts",
)
