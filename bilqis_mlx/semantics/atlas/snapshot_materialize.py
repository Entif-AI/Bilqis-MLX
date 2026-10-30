"""Materialize a fully verified immutable Atlas snapshot."""
from __future__ import annotations

import json
from pathlib import Path

from ..atlas_projection import (
    ATLAS_ARTIFACT_SCHEMA, ATLAS_CONCEPT_RECORD_SCHEMA,
    ATLAS_RELATION_RECORD_SCHEMA, ATLAS_RELEASE_SCHEMA,
    ATLAS_SNAPSHOT_SCHEMA, ATLAS_WITHHELD_RECORD_SCHEMA,
    BANK_SIZE, HEX64, SHAPE_POLICY,
    AbiEntry, AtlasCounts, CorpusCoverageRow, FormalDomainBinding,
    FrozenAtlasConcept, FrozenAtlasRelation, FrozenAtlasSnapshot,
    _canonical_bytes, _digest, _fail, _validate_abi_entries,
)
from .snapshot_io import _jsonl_records, _read_persisted_artifact, _snapshot_concept

def load_atlas_snapshot(
    bundle_dir: str | Path,
    *,
    expected_bundle_id: str | None = None,
    expected_release_sha256: str | None = None,
    expected_source_bundle_id: str | None = None,
) -> FrozenAtlasSnapshot:
    """Load a fully verified immutable Atlas snapshot without a database."""
    if any(value is not None and (
            type(value) is not str or not HEX64.fullmatch(value))
            for value in (
                expected_bundle_id, expected_release_sha256,
                expected_source_bundle_id)):
        _fail("ATLAS_SNAPSHOT_EXPECTED_PIN_INVALID")
    bundle_id, manifest, payloads = _read_persisted_artifact(bundle_dir)
    if expected_bundle_id is not None and expected_bundle_id != bundle_id:
        _fail("ATLAS_SNAPSHOT_EXPECTED_BUNDLE_MISMATCH")

    try:
        atlas = json.loads(payloads["atlas.json"])
    except (ValueError, TypeError, UnicodeError) as error:
        _fail("ATLAS_SNAPSHOT_ATLAS_INVALID:" + type(error).__name__)
    atlas_fields = {
        "schema", "release_schema", "release_sha256", "input_schemas",
        "source_bundle_id", "canonical_rdf_sha256", "coverage_sha256",
        "source_rows_sha256", "conformance_sha256", "prior_abi_sha256",
        "shape_policy", "shape_policy_sha256", "active_set_sha256", "counts",
        "formal_domain_bindings", "abi_entries",
    }
    digest_fields = (
        "release_sha256", "source_bundle_id", "canonical_rdf_sha256",
        "coverage_sha256", "source_rows_sha256", "conformance_sha256",
        "prior_abi_sha256", "shape_policy_sha256", "active_set_sha256",
    )
    if (not isinstance(atlas, dict) or set(atlas) != atlas_fields
            or payloads["atlas.json"] != _canonical_bytes(atlas)
            or atlas.get("schema") != ATLAS_ARTIFACT_SCHEMA
            or atlas.get("release_schema") != ATLAS_RELEASE_SCHEMA
            or any(not HEX64.fullmatch(atlas.get(name, "")) for name in digest_fields)
            or atlas["release_sha256"] != manifest["release_sha256"]
            or atlas["shape_policy_sha256"] != manifest["shape_policy_sha256"]
            or atlas["active_set_sha256"] != manifest["active_set_sha256"]
            or atlas.get("shape_policy") != SHAPE_POLICY
            or atlas["shape_policy_sha256"] != _digest(_canonical_bytes(SHAPE_POLICY))):
        _fail("ATLAS_SNAPSHOT_ATLAS_INVALID")
    if (expected_release_sha256 is not None
            and expected_release_sha256 != atlas["release_sha256"]):
        _fail("ATLAS_SNAPSHOT_EXPECTED_RELEASE_MISMATCH")
    if (expected_source_bundle_id is not None
            and expected_source_bundle_id != atlas["source_bundle_id"]):
        _fail("ATLAS_SNAPSHOT_EXPECTED_SOURCE_RELEASE_MISMATCH")

    try:
        if not isinstance(atlas["counts"], dict):
            _fail("ATLAS_SNAPSHOT_COUNTS_INVALID")
        counts = AtlasCounts(**atlas["counts"])
        bindings = tuple(FormalDomainBinding(
            family=item["family"],
            source_owner=item["source_owner"],
            source_sha256=item["source_sha256"],
            semantic_ids=tuple(item["semantic_ids"]),
            capability_ids=tuple(item["capability_ids"]),
        ) for item in atlas["formal_domain_bindings"])
        abi_entries = tuple(AbiEntry(**item) for item in atlas["abi_entries"])
    except (KeyError, TypeError) as error:
        _fail("ATLAS_SNAPSHOT_ATLAS_INVALID:" + type(error).__name__)
    if bindings != tuple(sorted(bindings)):
        _fail("ATLAS_SNAPSHOT_BINDING_ORDER_INVALID")
    _validate_abi_entries(abi_entries, require_concepts=())
    if (len(abi_entries) != counts.abi_entries
            or (len(abi_entries) + BANK_SIZE - 1) // BANK_SIZE != counts.abi_banks
            or sum(entry.active for entry in abi_entries) != counts.active_abi_indices
            or _digest(_canonical_bytes(
                [entry.index for entry in abi_entries if entry.active])) != atlas["active_set_sha256"]
            or len({capability for binding in bindings for capability in binding.capability_ids})
                != counts.trainable_capabilities):
        _fail("ATLAS_SNAPSHOT_COUNTS_INVALID")

    concepts = []
    for record in _jsonl_records(
            payloads["concepts.jsonl"], reason="ATLAS_SNAPSHOT_CONCEPTS_INVALID"):
        if set(record) != {
                "schema", "concept", "abi_index", "abi_bank", "abi_row", "active",
                "implementation_status", "teaching_candidate", "teaching_reason"} \
                or record.get("schema") != ATLAS_CONCEPT_RECORD_SCHEMA:
            _fail("ATLAS_SNAPSHOT_CONCEPT_RECORD_INVALID")
        concept = _snapshot_concept(record["concept"])
        index = record["abi_index"]
        if type(index) is not int or not 0 <= index < len(abi_entries):
            _fail("ATLAS_SNAPSHOT_CONCEPT_ABI_INVALID")
        abi_entry = abi_entries[index]
        if ((abi_entry.semantic_id, abi_entry.bank, abi_entry.row, abi_entry.active,
             abi_entry.teaching_candidate, abi_entry.reason)
                != (concept.semantic_id, record["abi_bank"], record["abi_row"],
                    record["active"], record["teaching_candidate"], record["teaching_reason"])
                or record["implementation_status"]
                != ("ADMITTED" if abi_entry.active else "IMPLEMENTATION_UNCOVERED")):
            _fail("ATLAS_SNAPSHOT_CONCEPT_ABI_MISMATCH")
        concepts.append(FrozenAtlasConcept(
            concept=concept,
            abi_index=index,
            abi_bank=record["abi_bank"],
            abi_row=record["abi_row"],
            active=record["active"],
            implementation_status=record["implementation_status"],
            teaching_candidate=record["teaching_candidate"],
            teaching_reason=record["teaching_reason"],
        ))
    frozen_concepts = tuple(concepts)
    concept_ids = tuple(item.concept.semantic_id for item in frozen_concepts)
    if (concept_ids != tuple(sorted(concept_ids))
            or len(concept_ids) != len(set(concept_ids))
            or len(frozen_concepts) != counts.semantic_concepts):
        _fail("ATLAS_SNAPSHOT_CONCEPT_ORDER_INVALID")

    relations = []
    for record in _jsonl_records(
            payloads["relations.jsonl"], reason="ATLAS_SNAPSHOT_RELATIONS_INVALID"):
        if (set(record) != {
                "schema", "source_semantic_id", "predicate", "target_semantic_id"}
                or record.get("schema") != ATLAS_RELATION_RECORD_SCHEMA):
            _fail("ATLAS_SNAPSHOT_RELATION_RECORD_INVALID")
        relations.append(FrozenAtlasRelation(
            record["source_semantic_id"], record["predicate"], record["target_semantic_id"]))
    frozen_relations = tuple(relations)
    expected_relations = tuple(
        FrozenAtlasRelation(item.concept.semantic_id, relation.predicate, relation.target)
        for item in frozen_concepts for relation in item.concept.relations)
    if frozen_relations != expected_relations:
        _fail("ATLAS_SNAPSHOT_RELATION_MISMATCH")

    withheld = []
    for record in _jsonl_records(
            payloads["held.jsonl"], reason="ATLAS_SNAPSHOT_WITHHELD_INVALID"):
        if record.get("schema") != ATLAS_WITHHELD_RECORD_SCHEMA:
            _fail("ATLAS_SNAPSHOT_WITHHELD_RECORD_INVALID")
        values = dict(record)
        values.pop("schema", None)
        try:
            row = CorpusCoverageRow(**values)
        except TypeError as error:
            _fail("ATLAS_SNAPSHOT_WITHHELD_RECORD_INVALID:" + type(error).__name__)
        if row.teaching_candidate or not row.teaching_reason:
            _fail("ATLAS_SNAPSHOT_WITHHELD_RECORD_INVALID")
        withheld.append(row)
    withheld_rows = tuple(withheld)
    if (sum(row.source_disposition == "SOURCE_HELD" for row in withheld_rows)
            != counts.source_held
            or sum(row.source_disposition == "SOURCE_IR_ONLY" for row in withheld_rows)
            != counts.source_ir_only
            or len({
                row.semantic_id for row in withheld_rows
                if row.implementation_status == "IMPLEMENTATION_UNCOVERED"
                and row.semantic_id
            }) != counts.implementation_uncovered):
        _fail("ATLAS_SNAPSHOT_WITHHELD_COUNTS_INVALID")
    held_ids = {
        row.semantic_id for row in withheld_rows
        if row.source_disposition == "SOURCE_HELD" and row.semantic_id}
    if held_ids & {entry.semantic_id for entry in abi_entries}:
        _fail("ATLAS_SNAPSHOT_HELD_IDENTITY_ADMITTED")

    semantic_lookup = tuple(sorted(
        (entry.semantic_id, entry.index) for entry in abi_entries))
    concept_lookup = tuple(
        (item.concept.semantic_id, index) for index, item in enumerate(frozen_concepts))
    return FrozenAtlasSnapshot(
        schema=ATLAS_SNAPSHOT_SCHEMA,
        bundle_id=bundle_id,
        release_sha256=atlas["release_sha256"],
        source_bundle_id=atlas["source_bundle_id"],
        canonical_rdf_sha256=atlas["canonical_rdf_sha256"],
        coverage_sha256=atlas["coverage_sha256"],
        source_rows_sha256=atlas["source_rows_sha256"],
        conformance_sha256=atlas["conformance_sha256"],
        prior_abi_sha256=atlas["prior_abi_sha256"],
        shape_policy_sha256=atlas["shape_policy_sha256"],
        active_set_sha256=atlas["active_set_sha256"],
        counts=counts,
        formal_domain_bindings=bindings,
        abi_entries=abi_entries,
        concepts=frozen_concepts,
        relations=frozen_relations,
        withheld_rows=withheld_rows,
        semantic_lookup=semantic_lookup,
        concept_lookup=concept_lookup,
    )
