"""Atlas projection validation ownership; canonical algorithms preserved."""
from __future__ import annotations
from .abi import _validate_abi_entries
from .common import ATLAS_RELEASE_SCHEMA, ATLAS_VALIDATION_SCHEMA, BANK_SIZE, HEX64, SHAPE_POLICY, _canonical_bytes, _digest, _fail
from .releases import AtlasCounts, AtlasRelease, ReleaseValidation


def validate_atlas_release(release: AtlasRelease) -> ReleaseValidation:
    """Validate source/identity invariants without consulting a mutable database."""
    if not isinstance(release, AtlasRelease) or release.schema != ATLAS_RELEASE_SCHEMA:
        _fail("ATLAS_RELEASE_SCHEMA_INVALID")
    if (not HEX64.fullmatch(release.source_bundle_id)
            or not all(HEX64.fullmatch(value) for value in (
                release.canonical_rdf_sha256, release.coverage_sha256,
                release.source_rows_sha256, release.conformance_sha256,
                release.prior_abi_sha256, release.shape_policy_sha256,
                release.active_set_sha256))
            or type(release.source_row_count) is not int or release.source_row_count < 1
            or type(release.rdf_term_count) is not int or release.rdf_term_count < 1):
        _fail("ATLAS_RELEASE_IDENTITY_INVALID")
    if release.concepts != tuple(sorted(release.concepts, key=lambda item: item.semantic_id)):
        _fail("ATLAS_CONCEPT_ORDER_INVALID")
    ids = tuple(item.semantic_id for item in release.concepts)
    if len(ids) != len(set(ids)) or any(not item.source_rows for item in release.concepts):
        _fail("ATLAS_CONCEPT_IDENTITY_INVALID")
    if (release.coverage_rows != tuple(sorted(release.coverage_rows))
            or len(release.coverage_rows) != release.source_row_count
            or any(not row.teaching_candidate and not row.teaching_reason
                   for row in release.coverage_rows)):
        _fail("ATLAS_COVERAGE_ROW_INVALID")
    held_ids = {
        row.semantic_id for row in release.coverage_rows
        if row.source_disposition == "SOURCE_HELD" and row.semantic_id}
    held_ids.update(item.semantic_id for item in release.held_mappings if item.semantic_id)
    if held_ids & set(ids):
        _fail("ATLAS_HELD_IDENTITY_ADMITTED")
    if release.held_mappings != tuple(sorted(release.held_mappings)):
        _fail("ATLAS_HELD_MAPPING_ORDER_INVALID")
    if release.formal_domain_bindings != tuple(sorted(release.formal_domain_bindings)):
        _fail("ATLAS_FORMAL_DOMAIN_BINDING_ORDER_INVALID")
    if not {"boolean", "numeric"} <= {item.family for item in release.formal_domain_bindings}:
        _fail("ATLAS_FORMAL_DOMAIN_BINDING_REQUIRED")
    formal_ids = {
        semantic_id for binding in release.formal_domain_bindings
        for semantic_id in binding.semantic_ids}
    if held_ids & formal_ids:
        _fail("ATLAS_HELD_IDENTITY_ADMISSION_REQUESTED")
    _validate_abi_entries(release.abi_entries, require_concepts=set(ids) | formal_ids)
    abi_ids = {entry.semantic_id for entry in release.abi_entries}
    if held_ids & abi_ids:
        _fail("ATLAS_HELD_IDENTITY_ADMITTED")
    if release.shape_policy_sha256 != _digest(_canonical_bytes(SHAPE_POLICY)):
        _fail("ATLAS_ABI_SHAPE_POLICY_DRIFT")
    expected_active = _digest(_canonical_bytes(
        [entry.index for entry in release.abi_entries if entry.active]))
    if release.active_set_sha256 != expected_active:
        _fail("ATLAS_ABI_ACTIVE_SET_DRIFT")
    capabilities = {
        capability for binding in release.formal_domain_bindings
        for capability in binding.capability_ids}
    active_ids = {entry.semantic_id for entry in release.abi_entries if entry.active}
    expected_counts = AtlasCounts(
        source_rows=release.source_row_count,
        rdf_terms=release.rdf_term_count,
        semantic_concepts=len(release.concepts),
        abi_entries=len(release.abi_entries),
        abi_banks=(len(release.abi_entries) + BANK_SIZE - 1) // BANK_SIZE,
        active_abi_indices=sum(entry.active for entry in release.abi_entries),
        trainable_capabilities=len(capabilities),
        source_held=sum(row.source_disposition == "SOURCE_HELD" for row in release.coverage_rows),
        source_ir_only=sum(row.source_disposition == "SOURCE_IR_ONLY" for row in release.coverage_rows),
        implementation_uncovered=sum(
            concept.semantic_id not in active_ids for concept in release.concepts),
    )
    if release.counts != expected_counts:
        _fail("ATLAS_RELEASE_COUNTS_DRIFT")
    return ReleaseValidation(
        schema=ATLAS_VALIDATION_SCHEMA,
        status="valid",
        release_sha256=release.digest,
        source_row_count=release.source_row_count,
        concept_count=len(release.concepts),
        held_mapping_count=len(release.held_mappings),
        formal_binding_count=len(release.formal_domain_bindings),
        abi_entry_count=len(release.abi_entries),
        abi_bank_count=release.counts.abi_banks,
        active_abi_count=release.counts.active_abi_indices,
        trainable_capability_count=release.counts.trainable_capabilities,
    )
