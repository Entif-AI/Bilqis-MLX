"""Source-bound feature composition, identity banks and tied readout."""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
import hashlib
import json
import math
from typing import Mapping
import mlx.core as mx
import numpy as np
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.model_topology_v2 import FEATURE_NONE_ROW, GenerationExtents, ModelTopologySpecV2, SHA256_HEX_LENGTH, expected_bamf_shapes, initialize_bamf_row, initializer_seed, validate_bamf_parameters
from bilqis_mlx.semantics.atlas_features import AtlasFeatures, _factor_overflow
from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection
from bilqis_mlx.semantics.frame_schema import ChildFrameRef, ConceptRef, FrameInstance
from .common import (
    WIDTH,
    COMPOSITION_SCHEMA,
    FEATURE_REQUEST_SCHEMA,
    CHILD_FRAME_REQUEST_SCHEMA,
    ACTIVE_BANK_SCHEMA,
    EMBEDDING_INPUT_SCHEMA,
    INDEXED_LOGITS_SCHEMA,
    POSITION_BASE,
    _SINUSOID_PAIR_WIDTH,
    FactorGate,
    _invalid,
    BANK_ROWS,
    UINT32_MAX,
    ATOM_EMBEDDING_RANK,
    CONSTITUENT_INDEX_RANK,
    IDENTITY_FACTOR_POLICY,
    IDENTITY_PROPOSAL_SCHEMA,
    embedding_parameter_view,
)
from .requests import (
    _source_coordinates,
    _child_source_coordinates,
    FeatureRequest,
    ChildFrameRequest,
    FrameConstituentRequest,
)
from .composition import (
    FactorComposition,
    _factor_vector,
    _local_position,
    _validate_feature_parameters,
    _validate_composer,
    _released_factor_terms,
    _compose_one,
    compose_factor_features,
)
from .frame_factors import (
    validate_frame_members,
    FrameFactorTerms,
    _child_factor_terms,
    child_frame_source_context,
    frame_factor_terms,
    EmptyFrameFactorTerms,
    empty_frame_factor_terms,
)
from .banks import (
    SemanticBankView,
    ConceptBatch,
    IndexedLogits,
    _validate_banks,
    embed_atoms,
    semantic_logits,
)
from .initialization import (
    SourceFactorWitness,
    IdentityRowInitialization,
    plan_identity_initialization,
)
from .gather import (
    gather_constituents,
    masked_semantic_loss,
)
