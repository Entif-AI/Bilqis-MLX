"""BAMF embedding requests owner."""
from __future__ import annotations
from dataclasses import dataclass
import math
from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection
from bilqis_mlx.semantics.frame_schema import ChildFrameRef, ConceptRef, FrameInstance
from .common import CHILD_FRAME_REQUEST_SCHEMA, FEATURE_REQUEST_SCHEMA, _invalid


def _source_coordinates(projection, frame_handle, member_handle):
    if type(projection) is not ApprovedContextProjection:
        _invalid()
    envelope = next((item for item in projection.envelopes if item.frame_handle == frame_handle), None)
    if envelope is None or type(envelope.frame) is not FrameInstance:
        _invalid()
    member = next((item for item in envelope.members if item.source_handle == member_handle), None)
    if member is None:
        _invalid()
    for slot, binding in enumerate(envelope.frame.bindings):
        if binding.key == member.key and binding.concept is not None:
            return (binding.concept, binding.role_id, envelope.frame.frame_schema_id, envelope.scope, slot)
    _invalid()

def _child_source_coordinates(projection, frame_handle, member_handle):
    if type(projection) is not ApprovedContextProjection:
        _invalid()
    envelope = next((
        item for item in projection.envelopes
        if item.frame_handle == frame_handle), None)
    if envelope is None or type(envelope.frame) is not FrameInstance:
        _invalid()
    member = next((
        item for item in envelope.members
        if item.source_handle == member_handle), None)
    if member is None:
        _invalid()
    for slot, binding in enumerate(envelope.frame.bindings):
        if binding.key != member.key or binding.child_frame is None:
            continue
        child = binding.child_frame
        child_envelopes = tuple(
            item for item in projection.envelopes
            if item.frame.occurrence_id == child.occurrence_id)
        if len(child_envelopes) != 1:
            _invalid()
        child_envelope = child_envelopes[0]
        actual = child_envelope.frame
        if (actual.content_digest != child.content_digest
                or actual.parent_occurrence_id
                != envelope.frame.occurrence_id
                or actual.source_instance_id
                != envelope.frame.source_instance_id
                or child_envelope.semantic_release
                != envelope.semantic_release
                or child_envelope.scope != envelope.scope):
            _invalid()
        return (child, binding.role_id, envelope.frame.frame_schema_id,
                envelope.scope, slot, child_envelope.frame_handle)
    _invalid()

@dataclass(frozen=True)
class FeatureRequest:
    """Target-free source coordinates for one visible atomic occurrence."""

    concept: ConceptRef
    role_id: str
    schema_id: str
    scope: str
    local_slot: int
    projection: ApprovedContextProjection
    frame_handle: str
    member_handle: str
    schema_version: str = FEATURE_REQUEST_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != FEATURE_REQUEST_SCHEMA or
                type(self.concept) is not ConceptRef or type(self.local_slot) is not int or
                self.local_slot < 0 or any(not isinstance(value, str) or not value
                                          for value in (self.role_id, self.schema_id, self.scope))):
            _invalid()
        try:
            if not math.isfinite(float(self.local_slot)):
                _invalid()
        except OverflowError:
            _invalid()
        if (self.concept, self.role_id, self.schema_id, self.scope, self.local_slot) != _source_coordinates(
                self.projection, self.frame_handle, self.member_handle):
            _invalid()

    @classmethod
    def from_context(cls, projection: ApprovedContextProjection, frame_handle: str,
                     member_handle: str) -> "FeatureRequest":
        coordinates = _source_coordinates(projection, frame_handle, member_handle)
        return cls(*coordinates, projection, frame_handle, member_handle)

@dataclass(frozen=True)
class ChildFrameRequest:
    """An approved child closure, not a ConceptRef or a semantic ABI row."""

    child: ChildFrameRef
    role_id: str
    schema_id: str
    scope: str
    local_slot: int
    projection: ApprovedContextProjection
    frame_handle: str
    member_handle: str
    child_frame_handle: str
    schema_version: str = CHILD_FRAME_REQUEST_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != CHILD_FRAME_REQUEST_SCHEMA
                or type(self.child) is not ChildFrameRef
                or type(self.local_slot) is not int
                or self.local_slot < 0
                or not all(isinstance(item, str) and item for item in (
                    self.role_id, self.schema_id, self.scope,
                    self.frame_handle, self.member_handle,
                    self.child_frame_handle))
                or (self.child, self.role_id, self.schema_id, self.scope,
                    self.local_slot, self.child_frame_handle)
                != _child_source_coordinates(
                    self.projection, self.frame_handle, self.member_handle)):
            _invalid()

    @classmethod
    def from_context(
        cls, projection: ApprovedContextProjection,
        frame_handle: str, member_handle: str,
    ) -> "ChildFrameRequest":
        child, role, schema, scope, slot, child_handle = (
            _child_source_coordinates(
                projection, frame_handle, member_handle))
        return cls(child, role, schema, scope, slot, projection,
                   frame_handle, member_handle, child_handle)

FrameConstituentRequest = FeatureRequest | ChildFrameRequest
