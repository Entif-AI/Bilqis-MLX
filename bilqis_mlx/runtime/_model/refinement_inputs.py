"""B06.3 binds exact B03 frame/member outputs to local refinement."""
from __future__ import annotations

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.frame_embeddings import EmptyFrameFactorTerms, FrameFactorTerms
from bilqis_mlx.learning.frame_encoder import (
    CompiledEmbeddingVectors, CompiledEncoderInput, FrameEncoding, encode_frames,
)
from bilqis_mlx.semantics.frame_compiler import PositionKind
from .model_topology_v2 import ModelTopologySpecV2
from .refinement_policy import RefinementChoice


WIDTH = ModelTopologySpecV2.width


def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _atomic_member_handles(compiled, row_index, frame_handle):
    matches = tuple(item for item in compiled.atomic_handles[row_index]
                    if item.frame_handle == frame_handle)
    if len(matches) != 1:
        _invalid()
    matches[0].__post_init__()
    return (matches[0].member_handle,)


def _cache_coordinates(choice):
    if type(choice.cache_identity) is not tuple:
        _invalid()
    try:
        generation, boundary, query_id, occurrence = choice.cache_identity
    except ValueError:
        _invalid()
    if (not isinstance(generation, str) or not generation
            or type(boundary) is not int or isinstance(boundary, bool)
            or boundary < 0 or not isinstance(query_id, str) or not query_id
            or occurrence != choice.occurrence_id):
        _invalid()
    return boundary


def selected_frame_inputs(compiled: CompiledEncoderInput,
                          vectors: CompiledEmbeddingVectors,
                          frame_parameters, row_index: int,
                          choice: RefinementChoice):
    if (type(compiled) is not CompiledEncoderInput
            or type(vectors) is not CompiledEmbeddingVectors
            or type(row_index) is not int or isinstance(row_index, bool)
            or not 0 <= row_index < len(compiled.compiled.rows)
            or type(choice) is not RefinementChoice):
        _invalid()
    encoding = encode_frames(compiled, vectors, frame_parameters)
    if type(encoding) is not FrameEncoding or encoding.compiled is not compiled.compiled:
        _invalid()
    boundary = _cache_coordinates(choice)
    positions = encoding.handles[row_index]
    if compiled.compiled.rows[row_index].visible_end != boundary:
        _invalid()
    matches = tuple(
        (index, position) for index, position in enumerate(positions)
        if position is not None and position.kind is PositionKind.CLOSURE
        and position.frame_handle == choice.frame_handle)
    if len(matches) != 1:
        _invalid()
    index, position = matches[0]
    position.__post_init__()
    if (position.packed is None
            or position.packed.sidecar.occurrence_id != choice.occurrence_id
            or index >= len(encoding.features[row_index])
            or index >= len(encoding.members[row_index])):
        _invalid()
    factor = encoding.features[row_index][index]
    if type(factor) is FrameFactorTerms:
        for request in factor.requests:
            request.__post_init__()
            if request.frame_handle != choice.frame_handle:
                _invalid()
        member_handles = tuple(request.member_handle for request in factor.requests)
        projection = factor.requests[0].projection
        if any(request.projection != projection for request in factor.requests):
            _invalid()
    elif type(factor) is EmptyFrameFactorTerms:
        if factor.frame_handle != choice.frame_handle or factor.requests:
            _invalid()
        projection = factor.projection
        member_handles = ()
    elif factor is None:
        member_handles = _atomic_member_handles(compiled, row_index, choice.frame_handle)
        projection = next((item.projection for item in compiled.atomic_handles[row_index]
                           if item.frame_handle == choice.frame_handle), None)
        if projection is None:
            _invalid()
    else:
        _invalid()
    approved = next((item for item in projection.eligible.frames
                     if item.frame_handle == choice.frame_handle), None)
    if (approved is None or approved.occurrence_id != choice.occurrence_id
            or approved.content_digest != position.packed.sidecar.content_digest
            or approved.member_handles != member_handles):
        _invalid()
    seed = encoding.global_seeds[row_index, index]
    members = encoding.members[row_index][index]
    if (seed.shape != (WIDTH,) or seed.dtype != mx.float32
            or members.shape != (len(member_handles), WIDTH)
            or members.dtype != mx.float32
            or not bool(mx.all(mx.isfinite(seed)))
            or not bool(mx.all(mx.isfinite(members)))):
        _invalid()
    return (encoding, index, seed, members, member_handles,
            compiled.compiled.rows[row_index].cache_key)
