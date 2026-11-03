"""Occurrence-aware frame-schema roles with source-owned authority."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade as _public_facade

def _public():
    return _public_facade("bilqis_mlx.semantics.frame_schema")

from dataclasses import dataclass
from enum import Enum

from .contracts import (
    _fail, _digest, CONCEPT_REF_RECORD, ROLE_OCCURRENCE_RECORD,
    CHILD_FRAME_REF_RECORD, FRAME_EDGE_RECORD, _SHA256,
)


class BindingState(str, Enum):
    VALUE = "VALUE"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"
    ALTERNATIVES = "ALTERNATIVES"



@dataclass(frozen=True, order=True)
class ConceptRef:
    semantic_id: str
    semantic_release: str
    abi_index: int
    type_ids: tuple[str, ...]
    source_reference: str
    schema_version: str = CONCEPT_REF_RECORD

    def __post_init__(self) -> None:
        if (not isinstance(self.semantic_id, str) or not self.semantic_id
                or not isinstance(self.semantic_release, str)
                or not _SHA256.fullmatch(self.semantic_release)
                or type(self.abi_index) is not int or self.abi_index < 0
                or self.type_ids != tuple(sorted(set(self.type_ids)))
                or any(not isinstance(item, str) or not item for item in self.type_ids)
                or not isinstance(self.source_reference, str) or not self.source_reference
                or self.schema_version != CONCEPT_REF_RECORD):
            _public()._fail("FRAME_CONCEPT_REF_INVALID")

    def content_identity(self) -> dict:
        return {
            "semantic_id": self.semantic_id,
            "semantic_release": self.semantic_release,
            "abi_index": self.abi_index,
            "type_ids": list(self.type_ids),
        }



@dataclass(frozen=True, order=True)
class ChildFrameRef:
    occurrence_id: str
    content_digest: str
    type_ids: tuple[str, ...] = ("Frame",)
    schema_version: str = CHILD_FRAME_REF_RECORD

    def __post_init__(self) -> None:
        if (not _SHA256.fullmatch(self.occurrence_id)
                or not _SHA256.fullmatch(self.content_digest)
                or not self.type_ids
                or self.type_ids != tuple(sorted(set(self.type_ids)))
                or self.schema_version != CHILD_FRAME_REF_RECORD):
            _public()._fail("FRAME_CHILD_REF_INVALID")



@dataclass(frozen=True)
class RoleOccurrence:
    role_id: str
    occurrence_index: int
    concept: ConceptRef | None = None
    child_frame: ChildFrameRef | None = None
    state: BindingState = BindingState.VALUE
    alternatives: tuple[ConceptRef, ...] = ()
    schema_version: str = ROLE_OCCURRENCE_RECORD

    def __post_init__(self) -> None:
        value_targets = int(self.concept is not None) + int(self.child_frame is not None)
        valid_state = (
            (self.state is BindingState.VALUE and value_targets == 1 and not self.alternatives)
            or (self.state in {BindingState.NONE, BindingState.UNKNOWN}
                and value_targets == 0 and not self.alternatives)
            or (self.state is BindingState.ALTERNATIVES
                and value_targets == 0 and bool(self.alternatives))
        )
        if (not isinstance(self.role_id, str) or not self.role_id
                or type(self.occurrence_index) is not int or self.occurrence_index < 0
                or not isinstance(self.state, BindingState)
                or not valid_state
                or self.schema_version != ROLE_OCCURRENCE_RECORD):
            _public()._fail("FRAME_ROLE_OCCURRENCE_INVALID")

    @property
    def key(self) -> tuple[str, int]:
        return self.role_id, self.occurrence_index

    def content_identity(self) -> dict:
        if self.state is BindingState.VALUE and self.concept is not None:
            target = {"kind": "concept", "value": self.concept.content_identity()}
        elif self.state is BindingState.VALUE and self.child_frame is not None:
            target = {
                "kind": "child-frame",
                "content_digest": self.child_frame.content_digest,
                "type_ids": list(self.child_frame.type_ids),
            }
        elif self.state is BindingState.ALTERNATIVES:
            target = {
                "kind": "alternatives",
                "values": [item.content_identity() for item in self.alternatives],
            }
        else:
            target = {"kind": self.state.value.lower()}
        return {
            "role_id": self.role_id,
            "occurrence_index": self.occurrence_index,
            "state": self.state.value,
            "target": target,
        }



@dataclass(frozen=True, order=True)
class FrameEdge:
    parent_occurrence_id: str
    role_id: str
    occurrence_index: int
    child_occurrence_id: str
    schema_version: str = FRAME_EDGE_RECORD



def _frame_content_digest(
    frame_schema_id: str,
    frame_schema_revision: int,
    schema_role_order: tuple[str, ...],
    bindings: tuple["RoleOccurrence", ...],
) -> str:
    rank = {role_id: index for index, role_id in enumerate(schema_role_order)}
    return _public()._digest({
        "frame_schema_id": frame_schema_id,
        "frame_schema_revision": frame_schema_revision,
        "schema_role_order": list(schema_role_order),
        "bindings": [
            binding.content_identity()
            for binding in sorted(
                bindings, key=lambda item: (rank[item.role_id], item.occurrence_index))
        ],
    })



def _binding_concepts(binding: RoleOccurrence) -> tuple[ConceptRef, ...]:
    if binding.state is BindingState.VALUE and binding.concept is not None:
        return (binding.concept,)
    if binding.state is BindingState.ALTERNATIVES:
        return binding.alternatives
    return ()
