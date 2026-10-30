"""Typed contracts for staged A02 semantic vocabulary growth."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ...errors import ErrorBus, SEMANTIC_FRAME
from ...runtime.model_topology_v2 import GenerationExtents
from ..atlas_features import AtlasFeatures, FeatureSchema
from .snapshot import AtlasArtifactSelection

VOCABULARY_PRIOR_SCHEMA = "bilqis.atlas-vocabulary-prior/v1"
VOCABULARY_EXTENSION_SCHEMA = "bilqis.atlas-vocabulary-extension/v1"
VOCABULARY_CANDIDATE_SCHEMA = "bilqis.atlas-vocabulary-candidate/v1"
STAGED_ONLY = "STAGED_NOT_ADMITTED"
UINT32_MAX = (1 << 32) - 1
FP32_BYTES = 4
ADAMW_ARRAYS_PER_ROW = 3


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<atlas-vocabulary>",
        span_start=0, span_end=0,
    )


@dataclass(frozen=True)
class VocabularyPrior:
    """A source selection and a predecessor generation, not an admission grant."""

    source_selection: AtlasArtifactSelection
    extents: GenerationExtents
    features: AtlasFeatures
    feature_schema: FeatureSchema
    active_semantic_ids: tuple[str, ...]
    generation_id: str
    schema_version: str = VOCABULARY_PRIOR_SCHEMA


@dataclass(frozen=True, order=True)
class VocabularyAllocation:
    semantic_id: str
    abi_index: int
    bank: int
    row: int
    source_status: str


@dataclass(frozen=True)
class VocabularyExtension:
    """Replayable allocation proposal. Its contents confer no source rights."""

    parent_generation_id: str
    parent_extents_digest: str
    source_bundle_id: str
    semantic_release: str
    source_allocation_digest: str
    prospective_feature_digest: str
    shape_policy_digest: str
    allocations: tuple[VocabularyAllocation, ...]
    active_indices: tuple[int, ...]
    active_semantic_digest: str
    bank_count: int
    status: str = STAGED_ONLY
    schema_version: str = VOCABULARY_EXTENSION_SCHEMA


@dataclass(frozen=True)
class VocabularyBankParent:
    """Only the B01 identity-bank slice; full Factory custody remains downstream."""

    prior: VocabularyPrior
    weights: tuple[object, ...]
    moments_m: tuple[object, ...]
    moments_v: tuple[object, ...]
    row_counts: tuple[tuple[int, int], ...]
    feature_parameters: Mapping[str, object]
    run_seed: int
    resource_budget_bytes: int


@dataclass(frozen=True)
class CandidateState:
    """Detached, in-memory bank candidate; not a committed student generation."""

    parent_generation_id: str
    source_allocation_digest: str
    extents: GenerationExtents
    weights: tuple[object, ...]
    moments_m: tuple[object, ...]
    moments_v: tuple[object, ...]
    row_counts: tuple[tuple[int, int], ...]
    active_indices: tuple[int, ...]
    active_mask: bytes
    output_domain: tuple[tuple[int, str], ...]
    registry_mirror_delta: tuple[VocabularyAllocation, ...]
    estimated_new_bank_bytes: int
    status: str = STAGED_ONLY
    schema_version: str = VOCABULARY_CANDIDATE_SCHEMA
