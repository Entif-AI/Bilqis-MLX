"""Atlas projection concepts ownership; canonical algorithms preserved."""
from __future__ import annotations
from dataclasses import dataclass
from .common import HEX64, _fail


@dataclass(frozen=True, order=True)
class SourceRecordRef:
    domain: str
    table: str
    key: str

@dataclass(frozen=True, order=True)
class AtlasLabel:
    role: str
    value: str
    language: str | None = None

@dataclass(frozen=True, order=True)
class AtlasRealization:
    value: str
    datatype: str | None = None
    language: str | None = None

@dataclass(frozen=True, order=True)
class AtlasRelation:
    predicate: str
    target: str

@dataclass(frozen=True, order=True)
class SourceLocus:
    """Canonical source-locus description with blank-node labels removed."""

    canonical: str

@dataclass(frozen=True)
class AtlasConcept:
    semantic_id: str
    kind: str
    types: tuple[str, ...]
    labels: tuple[AtlasLabel, ...]
    realizations: tuple[AtlasRealization, ...]
    source_loci: tuple[SourceLocus, ...]
    relations: tuple[AtlasRelation, ...]
    source_rows: tuple[SourceRecordRef, ...]

@dataclass(frozen=True, order=True)
class HeldMapping:
    domain: str
    table: str
    key: str
    status: str
    reason_code: str
    owner: str
    semantic_id: str | None = None

@dataclass(frozen=True, order=True)
class FormalDomainBinding:
    family: str
    source_owner: str
    source_sha256: str
    semantic_ids: tuple[str, ...]
    capability_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (not self.family or not self.source_owner or not HEX64.fullmatch(self.source_sha256)
                or not self.semantic_ids or len(self.semantic_ids) != len(set(self.semantic_ids))
                or any(not isinstance(item, str) or not item for item in self.semantic_ids)
                or not isinstance(self.capability_ids, tuple)
                or len(self.capability_ids) != len(set(self.capability_ids))
                or any(not isinstance(item, str) or not item for item in self.capability_ids)):
            _fail("ATLAS_FORMAL_DOMAIN_BINDING_INVALID")

@dataclass(frozen=True, order=True)
class AbiEntry:
    index: int
    bank: int
    row: int
    semantic_id: str
    symbol: str | None
    source: str
    active: bool
    teaching_candidate: bool
    reason: str

@dataclass(frozen=True, order=True)
class CorpusCoverageRow:
    domain: str
    table: str
    key: str
    semantic_id: str | None
    source_disposition: str
    implementation_status: str
    teaching_candidate: bool
    reason_code: str
    teaching_reason: str
    owner: str
