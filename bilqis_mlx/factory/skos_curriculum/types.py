"""Frozen source-family inventory and obligation records."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from bilqis_mlx.semantics.atlas_projection import CorpusCoverageRow
from .common import (LEARNING_UNVERIFIED, SOURCE_PROJECTION_ONLY,
    FAMILY_CONCEPT_SCHEMA, FAMILY_OBLIGATION_SCHEMA, FAMILY_INVENTORY_SCHEMA,
    _fail, _digest)

@dataclass(frozen=True)
class ConceptFamilyCoverage:
    semantic_id: str
    abi_index: int
    abi_active: bool
    source_disposition: str
    implementation_status: str
    required_family_ids: tuple[str, ...]
    source_refs: tuple[str, ...]
    learning_state: str = LEARNING_UNVERIFIED
    schema: str = FAMILY_CONCEPT_SCHEMA


@dataclass(frozen=True)
class FamilyObligation:
    semantic_id: str
    family_id: str
    source_evidence_sha256: str
    implementation_status: str
    reason: str
    learning_state: str = LEARNING_UNVERIFIED
    source_disposition: str = "SOURCE_ELIGIBLE"
    schema: str = FAMILY_OBLIGATION_SCHEMA


@dataclass(frozen=True)
class FamilyInventoryCounts:
    atlas_source_concepts: int
    formal_only_abi_identities: int
    source_eligible_concepts: int
    source_held_rows: int
    source_ir_only_rows: int
    source_emitted_nonconcept_rows: int
    required_families: int
    pending_source_families: int
    required_family_obligations: int
    implementation_uncovered_obligations: int


@dataclass(frozen=True)
class SemanticFamilyInventory:
    semantic_release: str
    atlas_bundle_id: str
    source_bundle_id: str
    source_coverage_sha256: str
    source_eligible_concept_ids: tuple[str, ...]
    required_source_family_ids: tuple[str, ...]
    pending_source_family_ids: tuple[str, ...]
    concepts: tuple[ConceptFamilyCoverage, ...]
    obligations: tuple[FamilyObligation, ...]
    source_held: tuple[CorpusCoverageRow, ...]
    source_ir_only: tuple[CorpusCoverageRow, ...]
    source_nonconcept: tuple[
        tuple[CorpusCoverageRow, tuple[str, ...]], ...]
    counts: FamilyInventoryCounts
    source_authority: str = SOURCE_PROJECTION_ONLY
    schema: str = FAMILY_INVENTORY_SCHEMA

    def __post_init__(self) -> None:
        if (self.source_authority != SOURCE_PROJECTION_ONLY
                or self.schema != FAMILY_INVENTORY_SCHEMA):
            _fail("BAMF_FAMILY_PROPOSAL_AUTHORITY_INVALID")

    @property
    def digest(self) -> str:
        return _digest(asdict(self))
