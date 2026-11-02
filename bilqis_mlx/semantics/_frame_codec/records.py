"""Frame codec records."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from ..frame_schema import BindingState, SourceSpan
from .primitives import (
    _fail, _digest, COMPACT_CODEC_ID, EXTENDED_SLOT_SCHEMA, FRAME_SIDECAR_SCHEMA,
    CONSTITUENT_METADATA_SCHEMA, EXTENDED_CODEC_ID, ATOMIC_CODEC_ID, UINT32_LIMIT,
    _SHA256,
)


@dataclass(frozen=True)
class ExtendedSlot:
    role_id: str
    occurrence_index: int
    state: str
    abi_indices: tuple[int, ...]
    semantic_ids: tuple[str, ...]
    child_occurrence_id: str | None
    child_content_digest: str | None
    child_type_ids: tuple[str, ...]
    schema_version: str = EXTENDED_SLOT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.role_id, str) or not self.role_id
                or type(self.occurrence_index) is not int or self.occurrence_index < 0
                or self.state not in {item.value for item in BindingState}
                or len(self.abi_indices) != len(self.semantic_ids)
                or any(type(index) is not int or not 0 <= index < UINT32_LIMIT
                       for index in self.abi_indices)
                or any(not isinstance(item, str) or not item for item in self.semantic_ids)
                or ((self.child_occurrence_id is None)
                    != (self.child_content_digest is None))
                or (self.child_occurrence_id is not None
                    and not _SHA256.fullmatch(self.child_occurrence_id))
                or (self.child_content_digest is not None
                    and not _SHA256.fullmatch(self.child_content_digest))
                or any(not isinstance(item, str) or not item for item in self.child_type_ids)
                or self.schema_version != EXTENDED_SLOT_SCHEMA):
            _fail("FRAME_EXTENDED_SLOT_INVALID")



@dataclass(frozen=True)
class ConstituentMetadata:
    order_index: int
    role_id: str
    occurrence_index: int
    state: str
    semantic_ids: tuple[str, ...]
    semantic_releases: tuple[str, ...]
    abi_indices: tuple[int, ...]
    type_ids: tuple[tuple[str, ...], ...]
    source_references: tuple[str, ...]
    child_occurrence_id: str | None
    child_content_digest: str | None
    child_type_ids: tuple[str, ...]
    schema_version: str = CONSTITUENT_METADATA_SCHEMA

    def __post_init__(self) -> None:
        widths = {
            len(self.semantic_ids),
            len(self.semantic_releases),
            len(self.abi_indices),
            len(self.type_ids),
            len(self.source_references),
        }
        if (type(self.order_index) is not int or self.order_index < 0
                or not isinstance(self.role_id, str) or not self.role_id
                or type(self.occurrence_index) is not int or self.occurrence_index < 0
                or self.state not in {item.value for item in BindingState}
                or len(widths) != 1
                or any(not isinstance(item, str) or not item
                       for item in self.semantic_ids)
                or any(not _SHA256.fullmatch(item)
                       for item in self.semantic_releases)
                or any(type(index) is not int or index < 0
                       for index in self.abi_indices)
                or any(not isinstance(item, tuple)
                       or any(not isinstance(value, str) or not value for value in item)
                       for item in self.type_ids)
                or any(not isinstance(item, str) or not item
                       for item in self.source_references)
                or ((self.child_occurrence_id is None)
                    != (self.child_content_digest is None))
                or (self.child_occurrence_id is not None
                    and not _SHA256.fullmatch(self.child_occurrence_id))
                or (self.child_content_digest is not None
                    and not _SHA256.fullmatch(self.child_content_digest))
                or any(not isinstance(item, str) or not item
                       for item in self.child_type_ids)
                or self.schema_version != CONSTITUENT_METADATA_SCHEMA):
            _fail("FRAME_CONSTITUENT_METADATA_INVALID")



@dataclass(frozen=True)
class FrameSidecar:
    codec_id: str
    semantic_release: str
    schema_map_sha256: str
    schema_id: str | None
    schema_revision: int | None
    schema_sha256: str | None
    ast_construct: str
    order_mode: str | None
    scope: str | None
    occurrence_id: str
    content_digest: str
    source_instance_id: str
    structural_path: tuple[int, ...]
    source_span: SourceSpan
    parent_occurrence_id: str | None
    causal_prefix_end: int
    constituents: tuple[ConstituentMetadata, ...]
    frame_payload_sha256: str
    schema_version: str = FRAME_SIDECAR_SCHEMA

    def __post_init__(self) -> None:
        if (self.codec_id not in {
                COMPACT_CODEC_ID, EXTENDED_CODEC_ID, ATOMIC_CODEC_ID}
                or not _SHA256.fullmatch(self.semantic_release)
                or not _SHA256.fullmatch(self.schema_map_sha256)
                or not _SHA256.fullmatch(self.occurrence_id)
                or not _SHA256.fullmatch(self.content_digest)
                or not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or any(type(item) is not int or item < 0 for item in self.structural_path)
                or (self.parent_occurrence_id is not None
                    and not _SHA256.fullmatch(self.parent_occurrence_id))
                or type(self.causal_prefix_end) is not int
                or self.causal_prefix_end < self.source_span.end
                or not _SHA256.fullmatch(self.frame_payload_sha256)
                or tuple(item.order_index for item in self.constituents)
                != tuple(range(len(self.constituents)))
                or self.schema_version != FRAME_SIDECAR_SCHEMA):
            _fail("FRAME_CODEC_SIDECAR_INVALID")
        schema_values = (
            self.schema_id,
            self.schema_revision,
            self.schema_sha256,
            self.order_mode,
            self.scope,
        )
        if self.codec_id == ATOMIC_CODEC_ID:
            if any(value is not None for value in schema_values):
                _fail("FRAME_ATOMIC_SIDECAR_SCHEMA_FORBIDDEN")
        elif (not isinstance(self.schema_id, str) or not self.schema_id
                or type(self.schema_revision) is not int
                or self.schema_revision < 1
                or not _SHA256.fullmatch(self.schema_sha256)
                or not isinstance(self.order_mode, str) or not self.order_mode
                or not isinstance(self.scope, str) or not self.scope):
            _fail("FRAME_SCHEMA_SIDECAR_INVALID")

    @property
    def digest(self) -> str:
        return _digest(asdict(self))
