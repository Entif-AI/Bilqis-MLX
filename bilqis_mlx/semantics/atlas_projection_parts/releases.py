"""Atlas projection releases ownership; canonical algorithms preserved."""
from __future__ import annotations
from dataclasses import asdict
from dataclasses import dataclass
from .common import _canonical_bytes, _digest
from .concepts import AbiEntry, AtlasConcept, CorpusCoverageRow, FormalDomainBinding, HeldMapping


@dataclass(frozen=True)
class AtlasCounts:
    source_rows: int
    rdf_terms: int
    semantic_concepts: int
    abi_entries: int
    abi_banks: int
    active_abi_indices: int
    trainable_capabilities: int
    source_held: int
    source_ir_only: int
    implementation_uncovered: int

@dataclass(frozen=True)
class AtlasRelease:
    schema: str
    input_schemas: tuple[tuple[str, str], ...]
    source_bundle_id: str
    canonical_rdf_sha256: str
    coverage_sha256: str
    source_rows_sha256: str
    conformance_sha256: str
    prior_abi_sha256: str
    source_row_count: int
    rdf_term_count: int
    concepts: tuple[AtlasConcept, ...]
    held_mappings: tuple[HeldMapping, ...]
    formal_domain_bindings: tuple[FormalDomainBinding, ...]
    coverage_rows: tuple[CorpusCoverageRow, ...]
    abi_entries: tuple[AbiEntry, ...]
    shape_policy_sha256: str
    active_set_sha256: str
    counts: AtlasCounts

    @property
    def digest(self) -> str:
        return _digest(_canonical_bytes(asdict(self)))

@dataclass(frozen=True)
class ReleaseValidation:
    schema: str
    status: str
    release_sha256: str
    source_row_count: int
    concept_count: int
    held_mapping_count: int
    formal_binding_count: int
    abi_entry_count: int
    abi_bank_count: int
    active_abi_count: int
    trainable_capability_count: int

@dataclass(frozen=True)
class AtlasArtifactReceipt:
    schema: str
    bundle_id: str
    path: str
    release_sha256: str
    file_sha256: tuple[tuple[str, str], ...]
