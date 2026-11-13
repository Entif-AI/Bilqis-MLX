"""Contracts for the existing frame encoder contract."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SCHOOL
from bilqis_mlx.learning.frame_embeddings import EmptyFrameFactorTerms
from bilqis_mlx.learning.frame_embeddings import FeatureRequest
from bilqis_mlx.learning.frame_embeddings import FrameConstituentRequest
from bilqis_mlx.learning.frame_embeddings import FrameFactorTerms
from bilqis_mlx.learning.frame_embeddings import validate_frame_members
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.atlas_features import AtlasFeatures
from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection
from bilqis_mlx.semantics.frame_compiler import CompiledFrameRows
from bilqis_mlx.semantics.frame_compiler import CompiledPosition
from bilqis_mlx.semantics.frame_schema import AtomicFrame
from dataclasses import dataclass
import mlx.core as mx


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

    The raw numerical entrypoint is concept-only. Nested child closures are
    admitted exclusively through CompiledEncoderInput and A05.4 source proof;
    callers cannot provide an arbitrary child embedding in this path.
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
                if any(type(item) is not FeatureRequest for item in group):
                    _invalid()
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
    handles: (tuple[tuple[tuple[FrameConstituentRequest, ...], ...], ...] |
              tuple[tuple[AtomicSourceHandle, ...], ...] | tuple[tuple[CompiledPosition | None, ...], ...])
    features: tuple[tuple[FrameFactorTerms | EmptyFrameFactorTerms | None, ...], ...]
    schema_version: str = OUTPUT_SCHEMA
    compiled: CompiledFrameRows | None = None
