"""Contracts for the existing atlas engram contract."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SCHOOL
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from dataclasses import asdict
from dataclasses import dataclass
from typing import Protocol
import hashlib
import json
import re


KEY_SCHEMA = "bilqis.motif-key/v1"


MEMBER_SCHEMA = "bilqis.motif-member/v1"


MANIFEST_SCHEMA = "bilqis.motif-manifest/v1"


PLAN_SCHEMA = "bilqis.motif-allocation-plan/v1"


VIEW_SCHEMA = "bilqis.motif-candidate-view/v2"


PAGE_GROWTH_SCHEMA = "bilqis.motif-page-growth/v1"


FRAME_INPUT_SCHEMA = "bilqis.motif-frame-input/v1"


FRAME_INSTANCE_SCHEMA = "bilqis.semantic-frame-instance/v2"


FRAME_SCHEMA = "bilqis.semantic-frame-schema/v1"


CONCEPT_SCHEMA = "bilqis.semantic-concept-ref/v1"


CHILD_SCHEMA = "bilqis.semantic-child-frame-ref/v1"


MAX_CANDIDATE_ALLOCATIONS = 64


OBSERVED_USE_ARITY = 2


from bilqis_mlx.runtime.model_topology_v2 import MOTIF_PAGE_SHAPE
INITIAL_MOTIF_CAPACITY, MOTIF_VECTOR_WIDTH = MOTIF_PAGE_SHAPE


MAX_MOTIF_CAPACITY = INITIAL_MOTIF_CAPACITY * ModelTopologySpecV2.max_motif_pages


MOTIF_PAGE_STATE_BYTES = INITIAL_MOTIF_CAPACITY * MOTIF_VECTOR_WIDTH * 4 * 3


_SHA = re.compile(r"[0-9a-f]{64}\Z")


_STATES = frozenset({"VALUE", "NONE", "UNKNOWN", "ALTERNATIVES"})


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


class FrameInstanceV2(Protocol):
    frame_schema_id: str
    frame_schema_revision: int
    schema_role_order: tuple[str, ...]
    occurrence_id: str
    content_digest: str
    bindings: tuple
    schema_version: str


class FrameSchemaV1(Protocol):
    schema_id: str
    revision: int
    ast_construct: str
    ast_contract_sha256: str | None
    roles: tuple
    order_mode: str
    scope: str
    schema_version: str


@dataclass(frozen=True)
class MotifFrameInput:
    frame: FrameInstanceV2
    schema: FrameSchemaV1
    schema_version: str = FRAME_INPUT_SCHEMA


@dataclass(frozen=True)
class MotifMember:
    role_id: str
    occurrence_index: int
    state: str
    target_kind: str
    target_ids: tuple[str, ...]
    type_ids: tuple[str, ...]
    schema_version: str = MEMBER_SCHEMA

    def __post_init__(self) -> None:
        if (not self.role_id or type(self.occurrence_index) is not int
                or self.occurrence_index < 0 or self.state not in _STATES
                or not self.target_kind
                or not isinstance(self.target_ids, tuple)
                or not isinstance(self.type_ids, tuple)
                or self.type_ids != tuple(sorted(set(self.type_ids)))
                or any(not isinstance(value, str) or not value
                       for value in (*self.target_ids, *self.type_ids))
                or self.schema_version != MEMBER_SCHEMA):
            _invalid("BAMF_MOTIF_MEMBER_INVALID")


@dataclass(frozen=True)
class MotifKey:
    kind: str
    semantic_release: str
    frame_schema_id: str
    frame_schema_revision: int
    members: tuple[MotifMember, ...]
    relation_signature: str
    scope: str
    schema_version: str = KEY_SCHEMA

    def __post_init__(self) -> None:
        target_kinds = (
            {"CONCEPT", "CHILD_FRAME", "ALTERNATIVE_CONCEPTS", "NONE", "UNKNOWN"}
            if self.kind == "EXACT" else
            {"TYPE", "CHILD_TYPE", "ALTERNATIVE_TYPES", "NONE", "UNKNOWN"}
        )
        if (self.kind not in {"EXACT", "STRUCTURAL"}
                or not _SHA.fullmatch(self.semantic_release)
                or not self.frame_schema_id
                or type(self.frame_schema_revision) is not int
                or self.frame_schema_revision < 1
                or not isinstance(self.members, tuple)
                or any(type(member) is not MotifMember
                       or member.target_kind not in target_kinds
                       for member in self.members)
                or not _SHA.fullmatch(self.relation_signature)
                or not self.scope
                or self.schema_version != KEY_SCHEMA):
            _invalid("BAMF_MOTIF_KEY_INVALID")

    def canonical_bytes(self) -> bytes:
        return _bytes(asdict(self))

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class MotifSlot:
    slot_id: int
    key: MotifKey

    def __post_init__(self) -> None:
        if (type(self.slot_id) is not int or self.slot_id < 0
                or type(self.key) is not MotifKey):
            _invalid("BAMF_MOTIF_SLOT_INVALID")


def _bucket(key: MotifKey) -> str:
    """Only an index hint. Full canonical key equality is mandatory on hit."""
    return key.digest[:16]
