"""B01 frame equations over a provisional, complete concept-member input view.

A05's concrete compiler is not integrated. FrameEncoderInput is a B03 adapter,
not CompiledFrameBatch or a source-admission credential. Atomic, partial, empty
and nested inputs require the sibling B03 outcomes and actual compiler receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.frame_embeddings import (
    FeatureRequest, FrameFactorTerms, frame_factor_terms, validate_frame_members,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes, validate_bamf_parameters,
)
from bilqis_mlx.semantics.atlas_features import AtlasFeatures


WIDTH = ModelTopologySpecV2.width
INNER = 192
INPUT_SCHEMA = "bilqis.mlx.frame-encoder-input/provisional-v1"
OUTPUT_SCHEMA = "bilqis.mlx.frame-encoding/v1"


def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


@dataclass(frozen=True)
class FrameEncoderInput:
    """Batch rows of complete frames, each with canonical source member requests.

    A05_COMPILER_SCHEMA_PENDING: arrays supplied to encode_frames follow this
    same row/frame/member order. Their B02 embedding provenance is the caller's
    responsibility until the actual compiler-to-embedding assembly is qualified.
    """

    requests: tuple[tuple[tuple[FeatureRequest, ...], ...], ...]
    features: AtlasFeatures
    extents: GenerationExtents
    schema_version: str = INPUT_SCHEMA

    def __post_init__(self):
        if (self.schema_version != INPUT_SCHEMA or type(self.features) is not AtlasFeatures or
                type(self.extents) is not GenerationExtents or
                self.extents.factor_map_digest != self.features.digest or
                type(self.requests) is not tuple or not self.requests or
                type(self.requests[0]) is not tuple or not self.requests[0]):
            _invalid()
        for row in self.requests:
            if type(row) is not tuple or len(row) != len(self.requests[0]):
                _invalid()
            for group in row:
                validate_frame_members(group)
            first = row[0][0]
            if (any(group[0].projection.digest != first.projection.digest for group in row) or
                    len({group[0].frame_handle for group in row}) != len(row)):
                _invalid()


@dataclass(frozen=True)
class FrameEncoding:
    global_seeds: mx.array
    members: tuple[tuple[mx.array, ...], ...]
    handles: tuple[tuple[tuple[FeatureRequest, ...], ...], ...]
    features: tuple[tuple[FrameFactorTerms, ...], ...]
    schema_version: str = OUTPUT_SCHEMA


def frame_encoder_parameter_view(parameters: Mapping[str, mx.array], *, spec: ModelTopologySpecV2,
                                 extents: GenerationExtents) -> dict[str, mx.array]:
    """Borrow the canonical frame/shared-feature tensors from a complete B01 tree."""
    validate_bamf_parameters(spec, extents, parameters)
    return {item.name: parameters[item.name] for item in expected_bamf_shapes(spec, extents)
            if item.name.startswith(("frame.", "features."))}


def _norm(value, gamma):
    return value * mx.rsqrt(mx.mean(value*value, axis=-1, keepdims=True) +
                           ModelTopologySpecV2.rms_norm_epsilon) * gamma


def _encode_one(members, factors, parameters):
    u = members @ parameters["frame.member_value"].T
    q = factors.schema128 @ parameters["frame.query_schema"].T
    k = members @ parameters["frame.member_key"].T
    attention = mx.softmax((q @ k.T) / INNER**.5, axis=-1)
    query = u @ parameters["frame.interact_query"].T
    key = u @ parameters["frame.interact_key"].T
    value = u @ parameters["frame.interact_value"].T
    interaction = mx.softmax((query @ key.T) / INNER**.5, axis=-1) @ value
    v = _norm(u + interaction @ parameters["frame.interact_output"].T,
              parameters["frame.interact_norm"])
    pooled = attention @ u + mx.sigmoid(parameters["frame.pool_gate"]) * (attention @ v)
    summary = (factors.schema128 + factors.mean_role128) / 2
    return _norm(pooled @ parameters["frame.project_output"].T +
                 summary @ parameters["frame.project_summary"].T, parameters["frame.norm"])


def encode_frames(compiled: FrameEncoderInput, atom_vectors: tuple[tuple[mx.array, ...], ...],
                  parameters: Mapping[str, mx.array]) -> FrameEncoding:
    """Encode complete unmasked groups without detaching or replacing members."""
    if type(compiled) is not FrameEncoderInput or not isinstance(parameters, Mapping):
        _invalid()
    compiled.__post_init__()
    if (type(atom_vectors) is not tuple or len(atom_vectors) != len(compiled.requests) or
            any(type(row) is not tuple or len(row) != len(request_row)
                for row, request_row in zip(atom_vectors, compiled.requests))):
        _invalid()
    declarations = tuple(item for item in expected_bamf_shapes(ModelTopologySpecV2(), compiled.extents)
                         if item.name.startswith(("frame.", "features.")))
    if ({name for name in parameters if name.startswith(("frame.", "features."))} !=
            {item.name for item in declarations}):
        _invalid()
    for item in declarations:
        tensor = parameters[item.name]
        if not isinstance(tensor, mx.array) or tensor.shape != item.shape or tensor.dtype != mx.float32:
            _invalid()
    for row, requests in zip(atom_vectors, compiled.requests):
        for members, group in zip(row, requests):
            if (not isinstance(members, mx.array) or members.shape != (len(group), WIDTH) or
                    members.dtype != mx.float32):
                _invalid()
    values = tuple(parameters[item.name] for item in declarations) + tuple(
        members for row in atom_vectors for members in row)
    if not all(bool(mx.all(mx.isfinite(value))) for value in values):
        _invalid()
    factors = tuple(tuple(frame_factor_terms(parameters, group, compiled.features, extents=compiled.extents)
                          for group in row) for row in compiled.requests)
    seeds = mx.stack([mx.stack([_encode_one(members, terms, parameters)
                               for members, terms in zip(row, feature_row)])
                      for row, feature_row in zip(atom_vectors, factors)])
    return FrameEncoding(seeds, atom_vectors, compiled.requests, factors)
