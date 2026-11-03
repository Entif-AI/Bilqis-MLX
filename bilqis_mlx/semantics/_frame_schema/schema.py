"""Occurrence-aware frame-schema schema with source-owned authority."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade as _public_facade

def _public():
    return _public_facade("bilqis_mlx.semantics.frame_schema")

from dataclasses import asdict, dataclass

from .contracts import (
    _fail, _bytes, FRAME_SCHEMA_RECORD, ROLE_SPEC_RECORD, SOURCE_SPAN_RECORD,
    _SHA256, _ORDER_MODES,
)


@dataclass(frozen=True, order=True)
class SourceSpan:
    start: int
    end: int
    schema_version: str = SOURCE_SPAN_RECORD

    def __post_init__(self) -> None:
        if (type(self.start) is not int or type(self.end) is not int
                or self.start < 0 or self.end < self.start
                or self.schema_version != SOURCE_SPAN_RECORD):
            _public()._fail("FRAME_SOURCE_SPAN_INVALID")



@dataclass(frozen=True, order=True)
class RoleSpec:
    role_id: str
    allowed_type_ids: tuple[str, ...]
    min_cardinality: int
    max_cardinality: int
    schema_version: str = ROLE_SPEC_RECORD

    def __post_init__(self) -> None:
        if (not isinstance(self.role_id, str) or not self.role_id
                or not self.allowed_type_ids
                or self.allowed_type_ids != tuple(sorted(set(self.allowed_type_ids)))
                or any(not isinstance(item, str) or not item for item in self.allowed_type_ids)
                or type(self.min_cardinality) is not int
                or type(self.max_cardinality) is not int
                or self.min_cardinality < 0
                or self.max_cardinality < self.min_cardinality
                or self.schema_version != ROLE_SPEC_RECORD):
            _public()._fail("FRAME_ROLE_SPEC_INVALID")



@dataclass(frozen=True)
class FrameSchema:
    schema_id: str
    revision: int
    ast_construct: str
    roles: tuple[RoleSpec, ...]
    order_mode: str
    scope: str
    ast_contract_sha256: str | None = None
    schema_version: str = FRAME_SCHEMA_RECORD

    def __post_init__(self) -> None:
        role_ids = tuple(role.role_id for role in self.roles)
        if (not isinstance(self.schema_id, str) or not self.schema_id
                or type(self.revision) is not int or self.revision < 1
                or not isinstance(self.ast_construct, str) or not self.ast_construct
                or not self.roles or len(role_ids) != len(set(role_ids))
                or self.order_mode not in _ORDER_MODES
                or not isinstance(self.scope, str) or not self.scope
                or (self.ast_contract_sha256 is not None
                    and not _SHA256.fullmatch(self.ast_contract_sha256))
                or self.schema_version != FRAME_SCHEMA_RECORD):
            _public()._fail("FRAME_SCHEMA_INVALID")

    @property
    def identity(self) -> str:
        return f"{self.schema_id}@{self.revision}"

    def canonical_bytes(self) -> bytes:
        return _public()._bytes(_public().asdict(self))
