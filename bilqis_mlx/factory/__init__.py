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
from .execution import (
    CapabilityExecution,
    CapabilityProfile,
    CurriculumDelta,
    CurriculumProfile,
    ExecutionPlan,
    GradeExecution,
    GradeProfile,
    ProjectionDigests,
    compile_execution_plan,
    diff_execution_plans,
)
from .release import (
    admit_factory_release,
    compile_factory_release,
)

__all__ = (
    "AdmissionReceipt",
    "AssessmentClass",
    "AssessmentPlan",
    "CapabilityDefinition",
    "CapabilityExecution",
    "CapabilityProfile",
    "ConstructionProgram",
    "CoveragePlan",
    "CurriculumDelta",
    "CurriculumProfile",
    "ExecutionPlan",
    "FactoryRelease",
    "GradeDefinition",
    "GradeExecution",
    "GradeProfile",
    "LearningEvidence",
    "ProjectionDigests",
    "SemanticRelease",
    "SourceAdapter",
    "TeachingOption",
    "admit_factory_release",
    "compile_execution_plan",
    "compile_factory_release",
    "diff_execution_plans",
    "qualification_complete",
)
