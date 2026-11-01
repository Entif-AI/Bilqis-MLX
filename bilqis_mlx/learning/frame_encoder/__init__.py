"""Stable frame encoder API with cohesive implementation owners."""
from __future__ import annotations
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from typing import Mapping
import mlx.core as mx
from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SCHOOL
from bilqis_mlx.learning.frame_embeddings import ChildFrameRequest
from bilqis_mlx.learning.frame_embeddings import FeatureRequest
from bilqis_mlx.learning.frame_embeddings import FrameConstituentRequest
from bilqis_mlx.learning.frame_embeddings import FrameFactorTerms
from bilqis_mlx.learning.frame_embeddings import EmptyFrameFactorTerms
from bilqis_mlx.learning.frame_embeddings import empty_frame_factor_terms
from bilqis_mlx.learning.frame_embeddings import child_frame_source_context
from bilqis_mlx.learning.frame_embeddings import frame_factor_terms
from bilqis_mlx.learning.frame_embeddings import validate_frame_members
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.model_topology_v2 import expected_bamf_shapes
from bilqis_mlx.runtime.model_topology_v2 import validate_bamf_parameters
from bilqis_mlx.semantics.atlas_features import AtlasFeatures
from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection
from bilqis_mlx.semantics.context_eligibility import project_context
from bilqis_mlx.semantics.frame_schema import AtomicFrame
from bilqis_mlx.semantics.frame_schema import FrameInstance
from bilqis_mlx.semantics.frame_compiler import CompiledFrameRows
from bilqis_mlx.semantics.frame_compiler import CompiledPosition
from bilqis_mlx.semantics.frame_compiler import FrameCompilerConfig
from bilqis_mlx.semantics.frame_compiler import PositionKind
from bilqis_mlx.semantics.frame_compiler import StreamingAST
from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.semantics.frame_compiler import reconstruct
from bilqis_mlx.semantics.partial_visible_forest import PartialVisibleForestReceipt
from bilqis_mlx.semantics.partial_visible_forest import validate_partial_visible_forest
from .contracts import (
    _invalid, WIDTH, INNER, INPUT_SCHEMA, OUTPUT_SCHEMA,
    COMPILED_VECTORS_SCHEMA, FrameEncoderInput, AtomicSourceHandle, AtomicEncoderInput, FrameEncoding,
)
from .compiled import (
    _compiled_groups, CompiledEncoderInput,
)
from .vectors import (
    MemberEmbedding, AtomicFrameEmbedding, CompiledEmbeddingVectors,
)
from .kernel import (
    _norm, _encode_one, _validate_vectors, _validate_encoder_parameters,
)
from .execution import (
    _encode_compiled,
)
from .dispatch import (
    frame_encoder_parameter_view, encode_frames,
)

for _export in (
    _invalid, FrameEncoderInput, AtomicSourceHandle, AtomicEncoderInput, FrameEncoding,
    _compiled_groups, CompiledEncoderInput, MemberEmbedding, AtomicFrameEmbedding, CompiledEmbeddingVectors,
    _encode_compiled, frame_encoder_parameter_view, _norm, _encode_one, _validate_vectors,
    _validate_encoder_parameters, encode_frames,
):
    _export.__module__ = __name__
del _export
