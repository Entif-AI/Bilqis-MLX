"""Closed CP02 record registry; later versions add new schema identities."""
from __future__ import annotations

from .envelopes import (
    ErrorEnvelope, EventEnvelope, PartialEnvelope, StaleEnvelope,
    UnavailableEnvelope,
)
from .events import (
    CandidateDecision, CorrectionEvent, FrameCompileReceipt, LearningEpisode,
    SalienceEvent, LearningHistorySummary,
)
from .observability import (
    GenerationManifest, GenerationManifestV2, MemorySnapshot, MemorySnapshotV2, NeuralRuntimeSample, ResourceSample,
    SemanticAtlasSnapshot, SemanticProjectionSnapshot, SemanticReleaseSnapshot,
    TeacherSnapshot,
)
from .notifications import Notification
from .operator import (
    OperatorActionReceipt, OperatorActionReceiptV2,
    OperatorActionRequest, OperatorActionRequestV2,
)
from ..semantic import (
    SemanticBankSnapshot, SemanticConceptSnapshot, SemanticGenerationState,
    SemanticHeldMappingSnapshot, SemanticSimilaritySnapshot,
)
from .snapshots import (
    CapabilitySnapshot, CurriculumFrontier, OperatorView, RunContext,
    SchoolSnapshot,
)


from .trainer import (
    TrainerObservation, TrainerObservationV2, TrainerObservationV3,
    TrainerObservationV4, TrainerObservationV5, TrainerObservationV6, TrainerObservationV7,
)
from .dossier import CapabilityDossier
from .factory import FactoryCockpitSnapshot


ALL_RECORD_TYPES = (
    TrainerObservation,
    TrainerObservationV2,
    TrainerObservationV3,
    TrainerObservationV4,
    TrainerObservationV5,
    TrainerObservationV6,
    TrainerObservationV7,
    CapabilityDossier,
    FactoryCockpitSnapshot,
    RunContext,
    OperatorView,
    SchoolSnapshot,
    CapabilitySnapshot,
    CurriculumFrontier,
    LearningEpisode,
    CandidateDecision,
    LearningHistorySummary,
    SemanticAtlasSnapshot,
    SemanticReleaseSnapshot,
    SemanticProjectionSnapshot,
    SemanticConceptSnapshot,
    SemanticGenerationState,
    SemanticBankSnapshot,
    SemanticHeldMappingSnapshot,
    SemanticSimilaritySnapshot,
    FrameCompileReceipt,
    NeuralRuntimeSample,
    MemorySnapshot,
    MemorySnapshotV2,
    TeacherSnapshot,
    SalienceEvent,
    CorrectionEvent,
    GenerationManifest,
    GenerationManifestV2,
    ResourceSample,
    Notification,
    OperatorActionRequest,
    OperatorActionReceipt,
    OperatorActionRequestV2,
    OperatorActionReceiptV2,
    ErrorEnvelope,
    UnavailableEnvelope,
    StaleEnvelope,
    PartialEnvelope,
    EventEnvelope,
)

RECORD_BY_SCHEMA = {record_type.SCHEMA: record_type for record_type in ALL_RECORD_TYPES}

if len(RECORD_BY_SCHEMA) != len(ALL_RECORD_TYPES):
    raise RuntimeError
