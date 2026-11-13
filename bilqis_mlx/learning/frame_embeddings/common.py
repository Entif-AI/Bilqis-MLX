"""BAMF embedding common owner."""
from __future__ import annotations
from enum import IntEnum
from typing import Mapping
import mlx.core as mx
import numpy as np
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes, validate_bamf_parameters


WIDTH = ModelTopologySpecV2.width

COMPOSITION_SCHEMA = "bilqis.mlx.factor-composition/v1"

FEATURE_REQUEST_SCHEMA = "bilqis.mlx.factor-request/v1"

CHILD_FRAME_REQUEST_SCHEMA = "bilqis.mlx.child-frame-constituent-request/v1"

ACTIVE_BANK_SCHEMA = "bilqis.mlx.semantic-bank-view/v1"

EMBEDDING_INPUT_SCHEMA = "bilqis.mlx.concept-batch/v1"

INDEXED_LOGITS_SCHEMA = "bilqis.mlx.indexed-logits/v1"

POSITION_BASE = 10000.0

_SINUSOID_PAIR_WIDTH = 2

class FactorGate(IntEnum):
    TYPE = 0
    ROLE = 1
    SCHEMA = 2
    GRAPH = 3

def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

BANK_ROWS = ModelTopologySpecV2.semantic_bank_rows

UINT32_MAX = int(np.iinfo(np.uint32).max)

ATOM_EMBEDDING_RANK = 3

CONSTITUENT_INDEX_RANK = 3

IDENTITY_FACTOR_POLICY = "bilqis.mlx.identity-factor/type-graph-v1"

IDENTITY_PROPOSAL_SCHEMA = "bilqis.mlx.identity-row-initialization/v1"

def embedding_parameter_view(parameters: Mapping[str, mx.array], *, spec: ModelTopologySpecV2,
                             extents: GenerationExtents) -> dict[str, mx.array]:
    """Borrow the exact identity/feature prefix after validating the whole B01 tree."""
    validate_bamf_parameters(spec, extents, parameters)
    names = tuple(item.name for item in expected_bamf_shapes(spec, extents)
                  if item.name.startswith(("identity.bank.", "features.")))
    return {name: parameters[name] for name in names}
