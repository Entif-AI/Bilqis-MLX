"""Atlas projection snapshots ownership; canonical algorithms preserved."""
from __future__ import annotations
from bisect import bisect_left
from dataclasses import dataclass
from .common import _fail
from .concepts import AbiEntry, AtlasConcept, CorpusCoverageRow, FormalDomainBinding
from .releases import AtlasCounts


@dataclass(frozen=True)
class FrozenAtlasConcept:
    concept: AtlasConcept
    abi_index: int
    abi_bank: int
    abi_row: int
    active: bool
    implementation_status: str
    teaching_candidate: bool
    teaching_reason: str

@dataclass(frozen=True, order=True)
class FrozenAtlasRelation:
    source_semantic_id: str
    predicate: str
    target_semantic_id: str

@dataclass(frozen=True)
class FrozenAtlasSnapshot:
    schema: str
    bundle_id: str
    release_sha256: str
    source_bundle_id: str
    canonical_rdf_sha256: str
    coverage_sha256: str
    source_rows_sha256: str
    conformance_sha256: str
    prior_abi_sha256: str
    shape_policy_sha256: str
    active_set_sha256: str
    counts: AtlasCounts
    formal_domain_bindings: tuple[FormalDomainBinding, ...]
    abi_entries: tuple[AbiEntry, ...]
    concepts: tuple[FrozenAtlasConcept, ...]
    relations: tuple[FrozenAtlasRelation, ...]
    withheld_rows: tuple[CorpusCoverageRow, ...]
    semantic_lookup: tuple[tuple[str, int], ...]
    concept_lookup: tuple[tuple[str, int], ...]

    def abi(self, index: int) -> AbiEntry:
        if type(index) is not int or not 0 <= index < len(self.abi_entries):
            _fail("ATLAS_SNAPSHOT_ABI_INDEX_UNKNOWN")
        return self.abi_entries[index]

    def abi_for_semantic(self, semantic_id: str) -> AbiEntry:
        if not isinstance(semantic_id, str) or not semantic_id:
            _fail("ATLAS_SNAPSHOT_SEMANTIC_ID_INVALID")
        position = bisect_left(self.semantic_lookup, (semantic_id, -1))
        if (position == len(self.semantic_lookup)
                or self.semantic_lookup[position][0] != semantic_id):
            _fail("ATLAS_SNAPSHOT_SEMANTIC_ID_UNKNOWN")
        return self.abi_entries[self.semantic_lookup[position][1]]

    def concept(self, semantic_id: str) -> FrozenAtlasConcept:
        if not isinstance(semantic_id, str) or not semantic_id:
            _fail("ATLAS_SNAPSHOT_SEMANTIC_ID_INVALID")
        position = bisect_left(self.concept_lookup, (semantic_id, -1))
        if (position == len(self.concept_lookup)
                or self.concept_lookup[position][0] != semantic_id):
            _fail("ATLAS_SNAPSHOT_CONCEPT_UNKNOWN")
        return self.concepts[self.concept_lookup[position][1]]

    def source_hold_census(self) -> tuple[CorpusCoverageRow, ...]:
        return tuple(
            row for row in self.withheld_rows
            if row.source_disposition == "SOURCE_HELD")

    def implementation_uncovered_census(self) -> tuple[CorpusCoverageRow, ...]:
        return tuple(
            row for row in self.withheld_rows
            if row.implementation_status == "IMPLEMENTATION_UNCOVERED")
