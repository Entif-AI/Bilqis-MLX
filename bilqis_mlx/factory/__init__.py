"""Canonical curriculum-factory contracts and grade-neutral runtime adapters."""

from .autonomy import (
    CurriculumWorkItem,
    EvidenceKind,
    EvidenceLedger,
    EvidenceObligation,
    EvidenceReceipt,
    closed_obligations,
    initial_evidence_ledger,
    evidence_complete_capabilities,
    next_work,
    obligations_for_capability,
    record_evidence,
)
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
    "CurriculumWorkItem",
    "EvidenceKind",
    "EvidenceLedger",
    "EvidenceObligation",
    "EvidenceReceipt",
    "closed_obligations",
    "initial_evidence_ledger",
    "evidence_complete_capabilities",
    "next_work",
    "obligations_for_capability",
    "record_evidence",
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
