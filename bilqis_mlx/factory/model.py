"""Stable import surface for typed curriculum-factory contracts.

Implementation is split across focused owners to keep the public module small while
preserving existing ``bilqis_mlx.factory.model`` imports.
"""
from .model_contracts import (
    AdmissionReceipt, AssessmentClass, AssessmentPlan, CapabilityDefinition,
    ConstructionProgram, CoveragePlan, GradeDefinition, LearningEvidence,
    SemanticRelease, SourceAdapter, TeachingOption, assessment_plans,
)
from .model_release import FactoryRelease

__all__ = (
    "AdmissionReceipt", "AssessmentClass", "AssessmentPlan",
    "CapabilityDefinition", "ConstructionProgram", "CoveragePlan",
    "FactoryRelease", "GradeDefinition", "LearningEvidence",
    "SemanticRelease", "SourceAdapter", "TeachingOption", "assessment_plans",
)
