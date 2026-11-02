"""Frame codec packed."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .primitives import (
    _fail, _digest, PackDisposition, FallbackReason, COMPACT_CODEC_ID,
    PACKED_FRAME_SCHEMA, EXTENDED_CODEC_ID, ATOMIC_CODEC_ID, _SHA256,
)
from .records import ExtendedSlot, FrameSidecar


@dataclass(frozen=True)
class PackDecision:
    disposition: PackDisposition
    reason: FallbackReason
    schema_tag: int | None



@dataclass(frozen=True)
class PackedFrame:
    disposition: PackDisposition
    reason: FallbackReason
    codec_id: str
    semantic_release: str
    schema_map_sha256: str
    schema_id: str | None
    schema_revision: int | None
    schema_sha256: str | None
    schema_payload: bytes | None
    frame_payload: bytes
    compact_word: int | None
    extended_slots: tuple[ExtendedSlot, ...]
    sidecar: FrameSidecar
    schema_version: str = PACKED_FRAME_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.disposition, PackDisposition)
                or not isinstance(self.reason, FallbackReason)
                or not isinstance(self.codec_id, str) or not self.codec_id
                or not _SHA256.fullmatch(self.semantic_release)
                or not _SHA256.fullmatch(self.schema_map_sha256)
                or not isinstance(self.frame_payload, bytes)
                or not self.frame_payload
                or not isinstance(self.sidecar, FrameSidecar)
                or self.sidecar.codec_id != self.codec_id
                or self.sidecar.semantic_release != self.semantic_release
                or self.sidecar.schema_map_sha256 != self.schema_map_sha256
                or self.schema_version != PACKED_FRAME_SCHEMA):
            _fail("FRAME_PACKED_RECORD_INVALID")
        if self.disposition is PackDisposition.COMPACT:
            if (self.codec_id != COMPACT_CODEC_ID
                    or type(self.compact_word) is not int
                    or self.extended_slots
                    or self.schema_id is None
                    or self.schema_revision is None
                    or self.schema_sha256 is None
                    or self.schema_payload is None):
                _fail("FRAME_PACKED_COMPACT_INVALID")
        elif self.disposition is PackDisposition.EXTENDED:
            if (self.codec_id != EXTENDED_CODEC_ID
                    or self.compact_word is not None
                    or self.schema_id is None
                    or self.schema_revision is None
                    or self.schema_sha256 is None
                    or self.schema_payload is None):
                _fail("FRAME_PACKED_EXTENDED_INVALID")
        else:
            if (self.codec_id != ATOMIC_CODEC_ID
                    or self.compact_word is not None
                    or self.extended_slots
                    or any(value is not None for value in (
                        self.schema_id,
                        self.schema_revision,
                        self.schema_sha256,
                        self.schema_payload,
                    ))):
                _fail("FRAME_PACKED_ATOMIC_INVALID")

    @property
    def projection_sha256(self) -> str:
        return _digest({
            "codec_id": self.codec_id,
            "disposition": self.disposition.value,
            "reason": self.reason.value,
            "compact_word": self.compact_word,
            "extended_slots": [asdict(item) for item in self.extended_slots],
            "sidecar_sha256": self.sidecar.digest,
        })
