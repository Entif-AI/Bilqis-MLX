"""B01 frame equations and source-revalidated A05 atom/closure encoding.

Actual A05 rows consume current compiler authority. Numerical group inputs
remain bounded fixtures. Nested closures require their sibling outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.frame_embeddings import (
    FeatureRequest, FrameFactorTerms, EmptyFrameFactorTerms, empty_frame_factor_terms,
    frame_factor_terms, validate_frame_members,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes, validate_bamf_parameters,
)
from bilqis_mlx.semantics.atlas_features import AtlasFeatures
from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection, project_context
from bilqis_mlx.semantics.frame_schema import AtomicFrame, FrameInstance
from bilqis_mlx.semantics.frame_compiler import (
    CompiledFrameRows, CompiledPosition, FrameCompilerConfig, PositionKind, StreamingAST, compile_prefix, reconstruct,
)


WIDTH = ModelTopologySpecV2.width
INNER = 192
INPUT_SCHEMA = "bilqis.mlx.frame-encoder-input/provisional-v1"
OUTPUT_SCHEMA = "bilqis.mlx.frame-encoding/v4"
COMPILED_VECTORS_SCHEMA = "bilqis.mlx.compiled-embedding-vectors/v2"


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
class AtomicSourceHandle:
    """One existing A13 atomic frame/member pair, without invented factors."""

    projection: ApprovedContextProjection
    frame_handle: str
    member_handle: str

    def __post_init__(self):
        if type(self.projection) is not ApprovedContextProjection:
            _invalid()
        source = next((item for item in self.projection.envelopes
                       if item.frame_handle == self.frame_handle), None)
        if (source is None or type(source.frame) is not AtomicFrame or len(source.members) != 1 or
                source.members[0].source_handle != self.member_handle or
                source.members[0].key != ("<atomic>", 0)):
            _invalid()


@dataclass(frozen=True)
class AtomicEncoderInput:
    """Provisional rows of A13 atomic positions; no partial-prefix claim."""

    handles: tuple[tuple[AtomicSourceHandle, ...], ...]
    schema_version: str = "bilqis.mlx.atomic-encoder-input/provisional-v1"

    def __post_init__(self):
        if (self.schema_version != "bilqis.mlx.atomic-encoder-input/provisional-v1" or
                type(self.handles) is not tuple or not self.handles or
                type(self.handles[0]) is not tuple or not self.handles[0]):
            _invalid()
        for row in self.handles:
            if (type(row) is not tuple or len(row) != len(self.handles[0]) or
                    any(type(item) is not AtomicSourceHandle for item in row)):
                _invalid()
            for item in row:
                item.__post_init__()
            if (any(item.projection.digest != row[0].projection.digest for item in row) or
                    len({item.frame_handle for item in row}) != len(row)):
                _invalid()


@dataclass(frozen=True)
class FrameEncoding:
    global_seeds: mx.array
    members: tuple[tuple[mx.array, ...], ...]
    handles: (tuple[tuple[tuple[FeatureRequest, ...], ...], ...] |
              tuple[tuple[AtomicSourceHandle, ...], ...] | tuple[tuple[CompiledPosition | None, ...], ...])
    features: tuple[tuple[FrameFactorTerms | EmptyFrameFactorTerms | None, ...], ...]
    schema_version: str = OUTPUT_SCHEMA
    compiled: CompiledFrameRows | None = None


def _compiled_groups(row, config):
    visible = reconstruct(row)
    rebuilt = compile_prefix(StreamingAST(visible.source_instance_id, visible.atoms, visible.frames),
                             row.visible_end, row.semantic_release, config)
    if rebuilt != row:
        _invalid()
    closures = tuple(position for position in row.positions if position.kind is PositionKind.CLOSURE)
    projection = None
    if closures:
        if config.approved is None:
            _invalid()
        handles = {position.frame_handle for position in closures}
        projection = project_context(tuple(item for item in config.approved.envelopes if item.frame_handle in handles),
                                     replace(config.task, causal_prefix_end=row.visible_end), config.frontier, config.policy)
        if type(projection) is not ApprovedContextProjection or projection.digest != row.context_digest:
            _invalid()
    groups = []
    for position in row.positions:
        if position.kind is PositionKind.ATOM:
            groups.append(())
            continue
        frame = projection.frame(position.frame_handle)
        if type(frame) is AtomicFrame:
            groups.append(())
            continue
        if (type(frame) is not FrameInstance or
                any(binding.concept is None for binding in frame.bindings)):
            _invalid()
        envelope = next(item for item in projection.envelopes if item.frame_handle == position.frame_handle)
        group = tuple(FeatureRequest.from_context(projection, position.frame_handle, member.source_handle)
                      for member in envelope.members)
        if group:
            validate_frame_members(group)
        groups.append(group)
    return tuple(groups), projection


@dataclass(frozen=True)
class CompiledEncoderInput:
    """Actual A05 rows, current compiler authority and released B02 features."""

    compiled: CompiledFrameRows
    compiler_configs: tuple[FrameCompilerConfig, ...]
    features: AtlasFeatures
    extents: GenerationExtents
    member_requests: tuple[tuple[FeatureRequest, ...], ...] = field(init=False)
    atomic_handles: tuple[tuple[AtomicSourceHandle, ...], ...] = field(init=False)
    _groups: tuple[tuple[tuple[FeatureRequest, ...], ...], ...] = field(init=False, repr=False)
    _projections: tuple[ApprovedContextProjection | None, ...] = field(init=False, repr=False)
    schema_version: str = "bilqis.mlx.compiled-encoder-input/v1"

    def __post_init__(self):
        if (self.schema_version != "bilqis.mlx.compiled-encoder-input/v1" or
                type(self.compiled) is not CompiledFrameRows or not self.compiled.rows or
                type(self.compiler_configs) is not tuple or len(self.compiler_configs) != len(self.compiled.rows) or
                any(type(config) is not FrameCompilerConfig for config in self.compiler_configs) or
                type(self.features) is not AtlasFeatures or type(self.extents) is not GenerationExtents or
                self.extents.factor_map_digest != self.features.digest or
                any(row.semantic_release != self.features.semantic_release for row in self.compiled.rows)):
            _invalid()
        self.compiled.__post_init__()
        checked = tuple(_compiled_groups(row, config)
                        for row, config in zip(self.compiled.rows, self.compiler_configs))
        groups = tuple(item[0] for item in checked)
        object.__setattr__(self, "_groups", groups)
        object.__setattr__(self, "_projections", tuple(item[1] for item in checked))
        object.__setattr__(self, "member_requests", tuple(tuple(item for group in row for item in group)
                                                         for row in groups))
        atomic_handles = []
        for row, (_, projection) in zip(self.compiled.rows, checked):
            handles = []
            for position in row.positions:
                if (position.kind is PositionKind.CLOSURE and
                        type(projection.frame(position.frame_handle)) is AtomicFrame):
                    source = next(item for item in projection.envelopes if item.frame_handle == position.frame_handle)
                    handles.append(AtomicSourceHandle(projection, position.frame_handle, source.members[0].source_handle))
            atomic_handles.append(tuple(handles))
        object.__setattr__(self, "atomic_handles", tuple(atomic_handles))


@dataclass(frozen=True)
class MemberEmbedding:
    """One supplied B02 vector bound to its exact source occurrence request."""

    request: FeatureRequest
    vector: mx.array

    def __post_init__(self):
        if (type(self.request) is not FeatureRequest or not isinstance(self.vector, mx.array) or
                self.vector.shape != (WIDTH,) or self.vector.dtype != mx.float32 or
                not bool(mx.all(mx.isfinite(self.vector)))):
            _invalid()


@dataclass(frozen=True)
class AtomicFrameEmbedding:
    """One supplied atomic closure vector bound to its exact approved handle."""

    handle: AtomicSourceHandle
    vector: mx.array

    def __post_init__(self):
        if (type(self.handle) is not AtomicSourceHandle or not isinstance(self.vector, mx.array) or
                self.vector.shape != (WIDTH,) or self.vector.dtype != mx.float32 or
                not bool(mx.all(mx.isfinite(self.vector)))):
            _invalid()
        self.handle.__post_init__()


@dataclass(frozen=True)
class CompiledEmbeddingVectors:
    """Unpadded raw atom rows and exact ordered closure-member vectors."""

    atoms: tuple[mx.array, ...]
    members: tuple[tuple[MemberEmbedding, ...], ...]
    atomic_frames: tuple[tuple[AtomicFrameEmbedding, ...], ...] = ()
    schema_version: str = COMPILED_VECTORS_SCHEMA


def _encode_compiled(compiled, vectors, parameters):
    compiled.__post_init__()
    if (type(vectors) is not CompiledEmbeddingVectors or
            vectors.schema_version != COMPILED_VECTORS_SCHEMA or
            type(vectors.atoms) is not tuple or type(vectors.members) is not tuple or
            type(vectors.atomic_frames) is not tuple or
            len(vectors.atoms) != len(compiled.compiled.rows) or len(vectors.members) != len(vectors.atoms)):
        _invalid()
    atomic_rows = vectors.atomic_frames or tuple(() for _ in compiled.compiled.rows)
    if len(atomic_rows) != len(vectors.atoms):
        _invalid()
    seeds, members, factors = [], [], []
    width = len(compiled.compiled.padded_positions[0])
    for row, groups, projection, atoms, supplied, expected, atomic_frames, atomic_handles in zip(
            compiled.compiled.rows, compiled._groups, compiled._projections,
            vectors.atoms, vectors.members, compiled.member_requests, atomic_rows, compiled.atomic_handles):
        if (not isinstance(atoms, mx.array) or atoms.shape != (row.visible_end, WIDTH) or atoms.dtype != mx.float32 or
                not bool(mx.all(mx.isfinite(atoms))) or type(supplied) is not tuple or
                any(type(item) is not MemberEmbedding for item in supplied) or
                tuple(item.request for item in supplied) != expected or type(atomic_frames) is not tuple or
                any(type(item) is not AtomicFrameEmbedding for item in atomic_frames) or
                tuple(item.handle for item in atomic_frames) != atomic_handles):
            _invalid()
        for item in supplied:
            item.__post_init__()
        for item in atomic_frames:
            item.__post_init__()
        cursor = 0
        atomic_cursor = 0
        row_seeds, row_members, row_factors = [], [], []
        for position, group in zip(row.positions, groups):
            if position.kind is PositionKind.ATOM:
                matrix = atoms[position.source_index:position.source_index+1]
                row_seeds.append(matrix[0])
                row_factors.append(None)
            elif group:
                matrix = mx.stack([item.vector for item in supplied[cursor:cursor+len(group)]])
                cursor += len(group)
                numerical = encode_frames(FrameEncoderInput(((group,),), compiled.features, compiled.extents),
                                           ((matrix,),), parameters)
                row_seeds.append(numerical.global_seeds[0, 0])
                row_factors.append(numerical.features[0][0])
            elif type(projection.frame(position.frame_handle)) is AtomicFrame:
                vector = atomic_frames[atomic_cursor].vector
                atomic_cursor += 1
                row_seeds.append(vector)
                row_factors.append(None)
                matrix = vector[None, :]
            else:
                _validate_encoder_parameters(parameters, compiled.extents)
                terms = empty_frame_factor_terms(parameters, projection, position.frame_handle,
                                                 compiled.features, extents=compiled.extents)
                summary = (terms.schema128 + terms.mean_role128) / 2
                row_seeds.append(_norm(parameters["frame.empty_seed"] +
                                       summary @ parameters["frame.project_summary"].T,
                                       parameters["frame.norm"]))
                row_factors.append(terms)
                matrix = mx.zeros((0, WIDTH), dtype=mx.float32)
            row_members.append(matrix)
        row_seeds.extend(mx.zeros((WIDTH,), dtype=mx.float32) for _ in range(width-len(row_seeds)))
        seeds.append(mx.stack(row_seeds) if row_seeds else mx.zeros((0, WIDTH), dtype=mx.float32))
        members.append(tuple(row_members))
        factors.append(tuple(row_factors))
    return FrameEncoding(mx.stack(seeds), tuple(members), compiled.compiled.padded_positions,
                         tuple(factors), compiled=compiled.compiled)


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


def _validate_vectors(atom_vectors, counts):
    if (type(atom_vectors) is not tuple or len(atom_vectors) != len(counts) or
            any(type(row) is not tuple or len(row) != len(count_row)
                for row, count_row in zip(atom_vectors, counts))):
        _invalid()
    for row, count_row in zip(atom_vectors, counts):
        for members, count in zip(row, count_row):
            if (not isinstance(members, mx.array) or members.shape != (count, WIDTH) or
                    members.dtype != mx.float32 or not bool(mx.all(mx.isfinite(members)))):
                _invalid()


def _validate_encoder_parameters(parameters, extents):
    declarations = tuple(item for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)
                         if item.name.startswith(("frame.", "features.")))
    if ({name for name in parameters if name.startswith(("frame.", "features."))} !=
            {item.name for item in declarations}):
        _invalid()
    for item in declarations:
        tensor = parameters[item.name]
        if not isinstance(tensor, mx.array) or tensor.shape != item.shape or tensor.dtype != mx.float32:
            _invalid()
    values = tuple(parameters[item.name] for item in declarations)
    if not all(bool(mx.all(mx.isfinite(value))) for value in values):
        _invalid()


def encode_frames(compiled: FrameEncoderInput | AtomicEncoderInput | CompiledEncoderInput,
                  atom_vectors: tuple[tuple[mx.array, ...], ...] | CompiledEmbeddingVectors,
                  parameters: Mapping[str, mx.array]) -> FrameEncoding:
    """Encode complete groups or preserve approved atomic vectors without detaching."""
    if not isinstance(parameters, Mapping):
        _invalid()
    if type(compiled) is CompiledEncoderInput:
        return _encode_compiled(compiled, atom_vectors, parameters)
    if type(compiled) not in (FrameEncoderInput, AtomicEncoderInput):
        _invalid()
    compiled.__post_init__()
    if type(compiled) is AtomicEncoderInput:
        _validate_vectors(atom_vectors, tuple(tuple(1 for _ in row) for row in compiled.handles))
        seeds = mx.stack([mx.stack([members[0] for members in row]) for row in atom_vectors])
        return FrameEncoding(seeds, atom_vectors, compiled.handles,
                             tuple(tuple(None for _ in row) for row in compiled.handles))
    _validate_vectors(atom_vectors, tuple(tuple(len(group) for group in row) for row in compiled.requests))
    _validate_encoder_parameters(parameters, compiled.extents)
    factors = tuple(tuple(frame_factor_terms(parameters, group, compiled.features, extents=compiled.extents)
                          for group in row) for row in compiled.requests)
    seeds = mx.stack([mx.stack([_encode_one(members, terms, parameters)
                               for members, terms in zip(row, feature_row)])
                      for row, feature_row in zip(atom_vectors, factors)])
    return FrameEncoding(seeds, atom_vectors, compiled.requests, factors)
