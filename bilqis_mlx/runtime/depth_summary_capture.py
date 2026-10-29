"""Producer-side, process-local custody for completed backbone summaries.

Only the future B11 backbone assembly may call the private capture constructor.
The public depth selector rejects raw tensors and copied/relabelled receipts.
This is not a persisted B13 generation or a substitute for its source proof.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
import uuid
import weakref
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from .model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, validate_bamf_parameters,
)

CAPTURE_SCHEMA = "bilqis.mlx.depth-capture/v1"
SUMMARY_SCHEMA = "bilqis.mlx.sealed-depth-summary/v1"
SOURCE_ORDER = ("h0", "g1", "g2", "g3")
COMPLETED_LAYERS = (0, 4, 8, 12)
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_CAPTURE_SEAL = object()
_SUMMARY_SEAL = object()
_LIVE_SUMMARIES: weakref.WeakValueDictionary[str, SealedDepthSummary] = (
    weakref.WeakValueDictionary())


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def _tensor_digest(hidden: mx.array) -> str:
    """Process-local object identity, preserving MLX gradient tracing."""
    if (not isinstance(hidden, mx.array) or hidden.dtype != mx.float32
            or hidden.ndim != 3 or hidden.shape[-1] != ModelTopologySpecV2.width
            or min(hidden.shape[:2]) < 1):
        _invalid()
    return _digest((id(hidden), tuple(hidden.shape), str(hidden.dtype)))


def _parameter_identity(parameters: Mapping[str, mx.array]) -> str:
    """Process-local exact tensor ownership; never a persisted content digest."""
    return _digest(tuple(sorted(
        (name, id(value)) for name, value in parameters.items())))


@dataclass(frozen=True)
class DepthCaptureProvenance:
    topology_digest: str
    extents_digest: str
    generation_digest: str
    implementation_digest: str
    prediction_digest: str
    feature_digest: str
    parameter_identity: str
    capture_id: str
    source_id: str
    completed_layer: int
    source_tensor_digest: str
    prior_summary_digest: str
    prefix_order: tuple[str, ...]

    @property
    def digest(self) -> str:
        return _digest(self.__dict__)


@dataclass(frozen=True)
class SealedDepthSummary:
    source_id: str
    completed_layer: int
    hidden: mx.array
    provenance: DepthCaptureProvenance
    _receipt_id: str = field(repr=False, compare=False)
    _seal: object = field(repr=False, compare=False)
    schema_version: str = SUMMARY_SCHEMA

    def __post_init__(self) -> None:
        if (self._seal is not _SUMMARY_SEAL
                or self.schema_version != SUMMARY_SCHEMA
                or type(self.provenance) is not DepthCaptureProvenance
                or self.source_id != self.provenance.source_id
                or self.completed_layer != self.provenance.completed_layer
                or self.source_id not in SOURCE_ORDER
                or self.completed_layer != COMPLETED_LAYERS[
                    SOURCE_ORDER.index(self.source_id)]):
            _invalid()


class _BackboneCapture:
    """One sequential h0,g1,g2,g3 capture epoch owned by the forward producer."""

    def __init__(
        self, parameters: Mapping[str, mx.array],
        spec: ModelTopologySpecV2, extents: GenerationExtents,
        generation_digest: str, implementation_digest: str,
        prediction_digest: str, feature_digest: str, seal: object,
    ) -> None:
        if (seal is not _CAPTURE_SEAL
                or type(spec) is not ModelTopologySpecV2
                or type(extents) is not GenerationExtents
                or any(not isinstance(value, str) or not _HEX64.fullmatch(value)
                       for value in (generation_digest, implementation_digest,
                                     prediction_digest, feature_digest))):
            _invalid()
        validate_bamf_parameters(spec, extents, parameters)
        self._parameter_identity = _parameter_identity(parameters)
        self._topology_digest = spec.digest
        self._extents_digest = extents.digest
        self._generation_digest = generation_digest
        self._implementation_digest = implementation_digest
        self._prediction_digest = prediction_digest
        self._feature_digest = feature_digest
        self._capture_id = uuid.uuid4().hex
        self._summaries: list[SealedDepthSummary] = []

    def capture(self, hidden: mx.array) -> SealedDepthSummary:
        index = len(self._summaries)
        if index >= len(SOURCE_ORDER):
            _invalid()
        if self._summaries and hidden.shape != self._summaries[0].hidden.shape:
            _invalid()
        source_digest = _tensor_digest(hidden)
        source_id = SOURCE_ORDER[index]
        provenance = DepthCaptureProvenance(
            self._topology_digest, self._extents_digest,
            self._generation_digest, self._implementation_digest,
            self._prediction_digest, self._feature_digest,
            self._parameter_identity, self._capture_id,
            source_id, COMPLETED_LAYERS[index], source_digest,
            self._summaries[-1].provenance.digest if self._summaries else "0" * 64,
            SOURCE_ORDER[:index + 1],
        )
        receipt = uuid.uuid4().hex
        summary = SealedDepthSummary(
            source_id, COMPLETED_LAYERS[index], hidden,
            provenance, receipt, _SUMMARY_SEAL)
        _LIVE_SUMMARIES[receipt] = summary
        self._summaries.append(summary)
        return summary

    def available(self, boundary_group: int) -> tuple[SealedDepthSummary, ...]:
        if (type(boundary_group) is not int or not 1 <= boundary_group <= 3
                or len(self._summaries) < boundary_group + 1):
            _invalid()
        return tuple(self._summaries[:boundary_group + 1])


def _begin_backbone_capture(
    parameters: Mapping[str, mx.array],
    *, spec: ModelTopologySpecV2, extents: GenerationExtents,
    generation_digest: str, implementation_digest: str,
    prediction_digest: str, feature_digest: str,
) -> _BackboneCapture:
    """Private B11 producer hook; not a public receipt-minting authority."""
    return _BackboneCapture(
        parameters, spec, extents, generation_digest, implementation_digest,
        prediction_digest, feature_digest, _CAPTURE_SEAL)


def verify_depth_summaries(
    summaries: tuple[SealedDepthSummary, ...],
    *, boundary_group: int, parameters: Mapping[str, mx.array],
    extents: GenerationExtents, feature_digest: str,
) -> None:
    """Reject relabelled/copied/future/cross-generation summary objects."""
    if (type(summaries) is not tuple or len(summaries) != boundary_group + 1
            or not 1 <= boundary_group <= 3
            or any(type(item) is not SealedDepthSummary
                   or _LIVE_SUMMARIES.get(item._receipt_id) is not item
                   for item in summaries)):
        _invalid()
    first = summaries[0].provenance
    expected_identity = _parameter_identity(parameters)
    if (first.parameter_identity != expected_identity
            or first.topology_digest != ModelTopologySpecV2().digest
            or first.extents_digest != extents.digest
            or first.feature_digest != feature_digest):
        _invalid()
    prior_digest = "0" * 64
    for index, summary in enumerate(summaries):
        p = summary.provenance
        if (summary.source_id != SOURCE_ORDER[index]
                or summary.completed_layer != COMPLETED_LAYERS[index]
                or p.prefix_order != SOURCE_ORDER[:index + 1]
                or p.prior_summary_digest != prior_digest
                or p.capture_id != first.capture_id
                or any(getattr(p, field) != getattr(first, field)
                       for field in ("topology_digest", "extents_digest",
                                     "generation_digest", "implementation_digest",
                                     "prediction_digest", "feature_digest",
                                     "parameter_identity"))
                or p.source_tensor_digest != _tensor_digest(summary.hidden)):
            _invalid()
        prior_digest = p.digest
