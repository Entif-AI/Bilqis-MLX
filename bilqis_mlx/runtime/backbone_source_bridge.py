"""B11.1a source-compiled h0 bridge; deliberately no producer admission.

Actual group-one capture still needs an executed B08 second motif disposition,
source-origin B02 vector custody, and a B04/B13 prediction boundary authority.
"""
from __future__ import annotations
from dataclasses import dataclass
import mlx.core as mx
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.frame_encoder import (
    CompiledEncoderInput, CompiledEmbeddingVectors, encode_frames,
)
from .model_topology_v2 import ModelTopologySpecV2, GenerationExtents
from .backbone_group_numerical import _content_digest, UNADMITTED_NUMERICAL


@dataclass(frozen=True)
class UnadmittedCompiledH0:
    hidden: mx.array
    compiled_prefix_digest: str
    admission_status: str = UNADMITTED_NUMERICAL


def compute_compiled_h0(
    compiled: CompiledEncoderInput, vectors: CompiledEmbeddingVectors,
    parameters: dict[str, mx.array], *, spec: ModelTopologySpecV2,
    extents: GenerationExtents,
) -> UnadmittedCompiledH0:
    """Calculate h0 from compiler-bound frame vectors, never caller hidden bytes."""
    if (type(compiled) is not CompiledEncoderInput or
            type(vectors) is not CompiledEmbeddingVectors or
            type(spec) is not ModelTopologySpecV2 or
            type(extents) is not GenerationExtents or compiled.extents != extents):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    encoding = encode_frames(compiled, vectors, parameters)
    if encoding.compiled is not compiled.compiled:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    # The digest is observational, not a credential for source or neural admission.
    return UnadmittedCompiledH0(encoding.global_seeds,
        _content_digest(encoding.global_seeds))


def admit_compiled_backbone_producer(*_args, **_kwargs):
    """No production issuance before actual B08/group and source-owned custody."""
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID,
                    reason="BLOCKED_PRODUCER_DEPENDENCY")
