"""B01 generation owner."""
from __future__ import annotations
from dataclasses import asdict, dataclass, fields
from typing import Mapping
from bilqis_mlx.errors import ErrorBus, SCHOOL
from .config import EXTENTS_SCHEMA, PROVENANCE_SCHEMA, SHA256_HEX_LENGTH, _digest, ModelTopologySpecV2


@dataclass(frozen=True)
class GenerationExtents:
    """Generation-specific table counts and upstream content bindings."""

    semantic_bank_count: int
    motif_page_count: int
    active_semantic_digest: str
    motif_key_map_digest: str
    factor_map_digest: str

    def __post_init__(self) -> None:
        if (type(self.semantic_bank_count) is not int or self.semantic_bank_count < 1 or
                type(self.motif_page_count) is not int or
                not 1 <= self.motif_page_count <= ModelTopologySpecV2.max_motif_pages):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        for value in (self.active_semantic_digest, self.motif_key_map_digest, self.factor_map_digest):
            if (not isinstance(value, str) or len(value) != SHA256_HEX_LENGTH or
                    any(character not in "0123456789abcdef" for character in value)):
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    @property
    def digest(self) -> str:
        return _digest({"schema": EXTENTS_SCHEMA, **asdict(self)})

    def to_record(self) -> dict:
        return {"schema": EXTENTS_SCHEMA, **asdict(self), "digest": self.digest}

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> "GenerationExtents":
        return _generation_from_record(cls, record, EXTENTS_SCHEMA)


@dataclass(frozen=True)
class GenerationProvenance:
    """Source/release and teacher bindings; validation does not grant admission."""

    source_identity: str
    release_digest: str
    teacher_identity: str
    teacher_epoch: int

    def __post_init__(self) -> None:
        for identity in (self.source_identity, self.teacher_identity):
            if not isinstance(identity, str) or not identity.strip():
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        if (not isinstance(self.release_digest, str) or len(self.release_digest) != SHA256_HEX_LENGTH or
                any(character not in "0123456789abcdef" for character in self.release_digest) or
                type(self.teacher_epoch) is not int or self.teacher_epoch < 0):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    @property
    def digest(self) -> str:
        return _digest({"schema": PROVENANCE_SCHEMA, **asdict(self)})

    def to_record(self) -> dict:
        return {"schema": PROVENANCE_SCHEMA, **asdict(self), "digest": self.digest}

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> "GenerationProvenance":
        return _generation_from_record(cls, record, PROVENANCE_SCHEMA)


def _generation_from_record(cls, record: Mapping[str, object], schema: str):
    names = {field.name for field in fields(cls)}
    if (not isinstance(record, Mapping) or set(record) != names | {"schema", "digest"} or
            record.get("schema") != schema):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
    generation = cls(**{name: record[name] for name in names})
    if record.get("digest") != generation.digest:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.RECORD_INVALID)
    return generation
