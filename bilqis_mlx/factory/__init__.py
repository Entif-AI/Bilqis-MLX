"""Canonical curriculum-factory contracts and grade-neutral runtime adapters."""

from .model import (
    AdmissionReceipt,
    AssessmentClass,
    AssessmentPlan,
    CapabilityDefinition,
    ConstructionProgram,
    CoveragePlan,
    FactoryRelease,
    GradeDefinition,
    LearningEvidence,
    SemanticRelease,
    SourceAdapter,
    TeachingOption,
)
from .assessment import qualification_complete
from .release import (
    admit_factory_release,
    compile_factory_release,
)

__all__ = (
    "AdmissionReceipt",
    "AssessmentClass",
    "AssessmentPlan",
    "CapabilityDefinition",
    "ConstructionProgram",
    "CoveragePlan",
    "FactoryRelease",
    "GradeDefinition",
    "LearningEvidence",
    "SemanticRelease",
    "SourceAdapter",
    "TeachingOption",
    "admit_factory_release",
    "compile_factory_release",
    "qualification_complete",
)
