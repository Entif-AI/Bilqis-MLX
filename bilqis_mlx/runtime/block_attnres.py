"""Shared depth selection with recomputed source-member factor features.

The public feature interface reads approved A13 coordinates and actual A06/B01
factors. Producer-side depth capture seals ordered backbone states for later assembly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import numpy as np
from weakref import WeakValueDictionary
import re
from types import MappingProxyType
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.frame_embeddings import FeatureRequest, compose_factor_features
from bilqis_mlx.semantics.atlas_features import AtlasFeatures
from .model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
    validate_bamf_parameters,
)


WIDTH = ModelTopologySpecV2.width
INNER = 128
MIN_COMPLETED_GROUPS = 1
MAX_COMPLETED_GROUPS = ModelTopologySpecV2.depth_groups
FRAME_RANK = 3
BATCH_POSITION_AXES = 2
_SHA = re.compile(r"[0-9a-f]{64}\Z")
PARAMETER_SHAPES = MappingProxyType({
    "norm": (WIDTH,),
    "query": (INNER, WIDTH),
    "key": (INNER, WIDTH),
    "value": (INNER, WIDTH),
    "output": (WIDTH, INNER),
    "gate_vector": (WIDTH,),
    "gate_bias": (1,),
})
FEATURES_SCHEMA = "bilqis.mlx.depth-frame-features/v1"
RELEASED_FEATURES_SCHEMA = "bilqis.mlx.depth-frame-features/v2"
SUMMARY_SCHEMA = "bilqis.mlx.depth-summary/v1"
PARAMETER_VIEW_SCHEMA = "bilqis.mlx.depth-parameter-view/v1"
_VIEW_SEAL = object()
_CAPTURE_SEAL = object()
_CAPTURE_ISSUED: WeakValueDictionary[int, CapturedDepth] = WeakValueDictionary()
SOURCE_ORDER = ("h0", "g1", "g2", "g3")
COMPLETED_LAYERS = (0, 4, 8, 12)


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _depth_names(boundary_group):
    return {"norm": "depth.norm", "query": "depth.query", "key": "depth.key",
            "value": "depth.value", "output": "depth.output",
            "gate_vector": f"depth.gate.{boundary_group - 1}.vector",
            "gate_bias": f"depth.gate.{boundary_group - 1}.bias"}


@dataclass(frozen=True)
class DepthParameterView(Mapping[str, mx.array]):
    """Sealed, immutable B01-validated references, not anonymous local weights."""

    _tensors: Mapping[str, mx.array]
    boundary_group: int
    _seal: object
    _full_parameters: Mapping[str, mx.array] | None = None
    _extents: GenerationExtents | None = None
    _feature_parameters: Mapping[str, mx.array] = field(init=False, repr=False, compare=False)
    implementation_digest: str | None = None
    input_boundary_digest: str | None = None
    schema_version: str = PARAMETER_VIEW_SCHEMA

    def __post_init__(self) -> None:
        if (self._seal is not _VIEW_SEAL
                or self.schema_version != PARAMETER_VIEW_SCHEMA
                or type(self.boundary_group) is not int
                or not MIN_COMPLETED_GROUPS <= self.boundary_group <= MAX_COMPLETED_GROUPS
                or not isinstance(self._tensors, Mapping)
                or set(self._tensors) != set(PARAMETER_SHAPES)
                or not isinstance(self._full_parameters, Mapping)
                or type(self._extents) is not GenerationExtents
                or any(value is not None and (type(value) is not str or not _SHA.fullmatch(value))
                       for value in (self.implementation_digest, self.input_boundary_digest))):
            _invalid()
        validate_bamf_parameters(ModelTopologySpecV2(), self._extents, self._full_parameters)
        if any(self._tensors[local] is not self._full_parameters[path]
               for local, path in _depth_names(self.boundary_group).items()):
            _invalid()
        object.__setattr__(self, "_tensors", MappingProxyType(dict(self._tensors)))
        object.__setattr__(self, "_full_parameters", MappingProxyType(dict(self._full_parameters)))
        object.__setattr__(self, "_feature_parameters", MappingProxyType({
            name: value for name, value in self._full_parameters.items() if name.startswith("features.")}))

    def __getitem__(self, name: str) -> mx.array:
        return self._tensors[name]

    def __iter__(self):
        return iter(self._tensors)

    def __len__(self) -> int:
        return len(self._tensors)


def depth_parameter_view(
    parameters: Mapping[str, mx.array], *, spec: ModelTopologySpecV2,
    extents: GenerationExtents, boundary_group: int,
    implementation_digest: str | None = None, input_boundary_digest: str | None = None,
) -> DepthParameterView:
    """Borrow only shared depth tensors and the selected B01 boundary gate."""
    if (type(spec) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents
            or type(boundary_group) is not int
            or not MIN_COMPLETED_GROUPS <= boundary_group <= MAX_COMPLETED_GROUPS):
        _invalid()
    validate_bamf_parameters(spec, extents, parameters)
    declared = {item.name: item for item in expected_bamf_shapes(spec, extents)}
    names = _depth_names(boundary_group)
    if (set(names) != set(PARAMETER_SHAPES)
            or any(name not in declared
                   or declared[name].shape != PARAMETER_SHAPES[local]
                   for local, name in names.items())):
        _invalid()
    return DepthParameterView(
        {local: parameters[name] for local, name in names.items()},
        boundary_group, _VIEW_SEAL, parameters, extents, implementation_digest=implementation_digest,
        input_boundary_digest=input_boundary_digest)


@dataclass(frozen=True)
class _DepthFeatureValues:
    """Private numerical test seam; these arrays are not source authority."""

    frame_seed: mx.array
    type_role: mx.array
    semantic_release: str
    source_evidence_digest: str
    boundary_group: int
    schema_version: str = FEATURES_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or not isinstance(self.source_evidence_digest, str)
                or not _SHA.fullmatch(self.source_evidence_digest)
                or type(self.boundary_group) is not int
                or not MIN_COMPLETED_GROUPS <= self.boundary_group <= MAX_COMPLETED_GROUPS
                or self.schema_version != FEATURES_SCHEMA):
            _invalid()


@dataclass(frozen=True)
class DepthFrameFeatures:
    """Complete source-member groups, never caller-supplied feature vectors."""

    requests: tuple[tuple[tuple[FeatureRequest, ...], ...], ...]
    features: AtlasFeatures
    boundary_group: int
    schema_version: str = RELEASED_FEATURES_SCHEMA

    def __post_init__(self):
        if (self.schema_version != RELEASED_FEATURES_SCHEMA or type(self.features) is not AtlasFeatures
                or type(self.boundary_group) is not int
                or not MIN_COMPLETED_GROUPS <= self.boundary_group <= MAX_COMPLETED_GROUPS
                or type(self.requests) is not tuple or not self.requests
                or type(self.requests[0]) is not tuple or not self.requests[0]):
            _invalid()
        for row in self.requests:
            if type(row) is not tuple or len(row) != len(self.requests[0]):
                _invalid()
            for members in row:
                if type(members) is not tuple or not members or any(type(item) is not FeatureRequest for item in members):
                    _invalid()
                first = members[0]
                frame = first.projection.frame(first.frame_handle)
                if (tuple(item.local_slot for item in members) != tuple(range(len(frame.bindings)))
                        or any((item.projection.digest, item.frame_handle) !=
                               (first.projection.digest, first.frame_handle) for item in members)):
                    _invalid()


@dataclass(frozen=True)
class DepthSummary:
    source_id: str
    completed_layer: int
    hidden: mx.array
    schema_version: str = SUMMARY_SCHEMA

    def __post_init__(self) -> None:
        if (self.source_id not in SOURCE_ORDER
                or type(self.completed_layer) is not int
                or self.completed_layer != COMPLETED_LAYERS[
                    SOURCE_ORDER.index(self.source_id)]
                or self.schema_version != SUMMARY_SCHEMA):
            _invalid()



def _tensor_digest(hidden: mx.array) -> str:
    """Fingerprint values without detaching the tensor used by the selector."""
    return hashlib.sha256(np.asarray(mx.stop_gradient(hidden)).tobytes()).hexdigest()


@dataclass(frozen=True)
class CapturedDepth:
    """One producer-bound prefix of h0,g1,g2,g3; no public mintable seal."""

    summaries: tuple[DepthSummary, ...]
    topology_digest: str
    implementation_digest: str
    generation_digest: str
    input_boundary_digest: str
    source_tensor_digests: tuple[str, ...]
    source_tensor_identities: tuple[int, ...]
    _seal: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (self._seal is not _CAPTURE_SEAL
                or any(not isinstance(value, str) or not _SHA.fullmatch(value)
                       for value in (self.topology_digest, self.implementation_digest,
                                     self.generation_digest, self.input_boundary_digest))
                or not 1 <= len(self.summaries) <= 4
                or len(self.summaries) != len(self.source_tensor_digests)
                or len(self.summaries) != len(self.source_tensor_identities)
                or tuple(item.source_id for item in self.summaries) != SOURCE_ORDER[:len(self.summaries)]
                or any(type(item) is not DepthSummary or
                       item.completed_layer != COMPLETED_LAYERS[index] or
                       not isinstance(item.hidden, mx.array) or
                       item.hidden.ndim != FRAME_RANK or item.hidden.shape[-1] != WIDTH or
                       item.hidden.dtype != mx.float32 or
                       id(item.hidden) != self.source_tensor_identities[index] or
                       _tensor_digest(item.hidden) != self.source_tensor_digests[index]
                       for index, item in enumerate(self.summaries))):
            _invalid()


def _issue_capture(value: CapturedDepth) -> CapturedDepth:
    _CAPTURE_ISSUED[id(value)] = value
    return value


def _validate_capture(value: CapturedDepth) -> None:
    if type(value) is not CapturedDepth or _CAPTURE_ISSUED.get(id(value)) is not value:
        _invalid()
    value.__post_init__()


def start_depth_capture(
    h0: mx.array, *, topology: ModelTopologySpecV2,
    implementation_digest: str, generation_digest: str,
    input_boundary_digest: str,
) -> CapturedDepth:
    """Start the source producer's immutable capture before the first group."""
    if type(topology) is not ModelTopologySpecV2 or not isinstance(h0, mx.array):
        _invalid()
    return _issue_capture(CapturedDepth((DepthSummary("h0", 0, h0),), topology.digest,
                         implementation_digest, generation_digest,
                         input_boundary_digest, (_tensor_digest(h0),),
                         (id(h0),), _CAPTURE_SEAL))


def append_depth_capture(prior: CapturedDepth, group_hidden: mx.array) -> CapturedDepth:
    """Capture the next completed four-layer group exactly once, in order."""
    if type(prior) is not CapturedDepth or not isinstance(group_hidden, mx.array):
        _invalid()
    _validate_capture(prior)
    index = len(prior.summaries)
    if index > MAX_COMPLETED_GROUPS or any(group_hidden is item.hidden for item in prior.summaries):
        _invalid()
    return _issue_capture(CapturedDepth(
        prior.summaries + (DepthSummary(SOURCE_ORDER[index], COMPLETED_LAYERS[index], group_hidden),),
        prior.topology_digest, prior.implementation_digest, prior.generation_digest,
        prior.input_boundary_digest, prior.source_tensor_digests + (_tensor_digest(group_hidden),),
        prior.source_tensor_identities + (id(group_hidden),), _CAPTURE_SEAL))


def _validate(current, available_summaries, frame_features, params) -> None:
    if (not isinstance(current, mx.array) or current.ndim != FRAME_RANK
            or current.shape[-1] != WIDTH or current.dtype != mx.float32
            or min(current.shape[:BATCH_POSITION_AXES]) < 1
            or not isinstance(available_summaries, tuple)
            or not MIN_COMPLETED_GROUPS + 1 <= len(available_summaries) <= MAX_COMPLETED_GROUPS + 1
            or any(type(value) is not DepthSummary
                   or not isinstance(value.hidden, mx.array)
                   or value.hidden.shape != current.shape
                   or value.hidden.dtype != mx.float32
                   for value in available_summaries)
            or type(frame_features) is not _DepthFeatureValues
            or len(available_summaries) != frame_features.boundary_group + 1
            or tuple(value.source_id for value in available_summaries)
            != SOURCE_ORDER[:len(available_summaries)]
            or not isinstance(frame_features.frame_seed, mx.array)
            or frame_features.frame_seed.shape != current.shape
            or frame_features.frame_seed.dtype != mx.float32
            or not isinstance(frame_features.type_role, mx.array)
            or frame_features.type_role.shape != current.shape
            or frame_features.type_role.dtype != mx.float32
            or not isinstance(params, Mapping)
            or set(params) != set(PARAMETER_SHAPES)):
        _invalid()
    for name, shape in PARAMETER_SHAPES.items():
        value = params[name]
        if (not isinstance(value, mx.array) or value.shape != shape
                or value.dtype != mx.float32):
            _invalid()
    finite_flags = tuple(mx.all(mx.isfinite(value)) for value in (
        current, frame_features.frame_seed, frame_features.type_role,
        *(item.hidden for item in available_summaries), *params.values(),
    ))
    mx.eval(*finite_flags)
    if not all(bool(flag) for flag in finite_flags):
        _invalid()


def _rms_norm(values: mx.array, gamma: mx.array) -> mx.array:
    epsilon = ModelTopologySpecV2.rms_norm_epsilon
    return values * mx.rsqrt(
        mx.mean(values * values, axis=-1, keepdims=True) + epsilon) * gamma


def _depth_components(current, available_summaries, frame_features, params):
    """Return output and proof-only alpha/gate values, without mutable caches."""
    _validate(current, available_summaries, frame_features, params)
    q = _rms_norm(current + frame_features.frame_seed, params["norm"]) @ params["query"].T
    keys = mx.stack([
        _rms_norm(summary.hidden + frame_features.type_role, params["norm"]) @ params["key"].T
        for summary in available_summaries
    ], axis=-2)
    values = mx.stack([
        summary.hidden @ params["value"].T for summary in available_summaries
    ], axis=-2)
    scores = mx.sum(q[:, :, None, :] * keys, axis=-1) * (INNER ** -0.5)
    alpha = mx.softmax(scores, axis=-1)
    mix = mx.sum(alpha[:, :, :, None] * values, axis=-2)
    gate_logits = (
        mx.sum(params["gate_vector"] * _rms_norm(current, params["norm"]),
               axis=-1, keepdims=True) + params["gate_bias"])
    gate = 0.1 * mx.sigmoid(gate_logits)
    output = current + gate * (mix @ params["output"].T)
    return output, alpha, gate


def depth_select(
    current: mx.array, available_summaries: CapturedDepth,
    frame_features: DepthFrameFeatures, params: DepthParameterView,
) -> mx.array:
    """Merge h0 and completed group summaries in their fixed source order.

    The producer captures h0,g1,...,gk in order; B11 supplies the real
    backbone group outputs at the declared completion boundaries.
    """
    if (type(available_summaries) is not CapturedDepth
            or available_summaries.topology_digest != ModelTopologySpecV2().digest
            or available_summaries.generation_digest != params._extents.digest
            or available_summaries.implementation_digest != params.implementation_digest
            or available_summaries.input_boundary_digest != params.input_boundary_digest
            or type(params) is not DepthParameterView
            or type(frame_features) is not DepthFrameFeatures
            or params.boundary_group != frame_features.boundary_group):
        _invalid()
    _validate_capture(available_summaries)
    if (len(available_summaries.summaries) != frame_features.boundary_group + 1
            or not isinstance(current, mx.array) or current.ndim != FRAME_RANK
            or current.shape[:BATCH_POSITION_AXES] != (len(frame_features.requests), len(frame_features.requests[0]))):
        _invalid()
    type_role = mx.stack([mx.stack([
        mx.mean(compose_factor_features(params._feature_parameters, (members,), frame_features.features,
                                        extents=params._extents).type_role[0], axis=0)
        for members in row]) for row in frame_features.requests])
    numerical = _DepthFeatureValues(available_summaries.summaries[0].hidden, type_role,
                                     frame_features.features.semantic_release,
                                     frame_features.features.digest, frame_features.boundary_group)
    output, _, _ = _depth_components(
        current, available_summaries.summaries, numerical, params)
    return output
