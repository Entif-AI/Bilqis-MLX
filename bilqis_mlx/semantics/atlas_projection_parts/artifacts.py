"""Atlas projection artifacts ownership; canonical algorithms preserved."""
from __future__ import annotations
from dataclasses import asdict
from .common import ATLAS_ARTIFACT_SCHEMA, ATLAS_CONCEPT_RECORD_SCHEMA, ATLAS_MANIFEST_SCHEMA, ATLAS_RELATION_RECORD_SCHEMA, ATLAS_WITHHELD_RECORD_SCHEMA, SHAPE_POLICY, _canonical_bytes, _canonical_line, _digest
from .releases import AtlasRelease
from .validation import validate_atlas_release


def _artifact_payloads(release: AtlasRelease) -> tuple[dict[str, bytes], bytes, str]:
    validate_atlas_release(release)
    by_id = {entry.semantic_id: entry for entry in release.abi_entries}
    atlas = {
        "schema": ATLAS_ARTIFACT_SCHEMA,
        "release_schema": release.schema,
        "release_sha256": release.digest,
        "input_schemas": [list(item) for item in release.input_schemas],
        "source_bundle_id": release.source_bundle_id,
        "canonical_rdf_sha256": release.canonical_rdf_sha256,
        "coverage_sha256": release.coverage_sha256,
        "source_rows_sha256": release.source_rows_sha256,
        "conformance_sha256": release.conformance_sha256,
        "prior_abi_sha256": release.prior_abi_sha256,
        "shape_policy": dict(SHAPE_POLICY),
        "shape_policy_sha256": release.shape_policy_sha256,
        "active_set_sha256": release.active_set_sha256,
        "counts": asdict(release.counts),
        "formal_domain_bindings": [asdict(item) for item in release.formal_domain_bindings],
        "abi_entries": [asdict(item) for item in release.abi_entries],
    }
    concept_records = []
    relation_records = []
    for concept in release.concepts:
        entry = by_id[concept.semantic_id]
        concept_records.append({
            "schema": ATLAS_CONCEPT_RECORD_SCHEMA,
            "concept": asdict(concept),
            "abi_index": entry.index,
            "abi_bank": entry.bank,
            "abi_row": entry.row,
            "active": entry.active,
            "implementation_status": "ADMITTED" if entry.active else "IMPLEMENTATION_UNCOVERED",
            "teaching_candidate": entry.teaching_candidate,
            "teaching_reason": entry.reason,
        })
        for relation in concept.relations:
            relation_records.append({
                "schema": ATLAS_RELATION_RECORD_SCHEMA,
                "source_semantic_id": concept.semantic_id,
                "predicate": relation.predicate,
                "target_semantic_id": relation.target,
            })
    withheld_records = [
        {"schema": ATLAS_WITHHELD_RECORD_SCHEMA, **asdict(row)}
        for row in release.coverage_rows if not row.teaching_candidate
    ]
    payloads = {
        "atlas.json": _canonical_bytes(atlas),
        "concepts.jsonl": b"".join(_canonical_line(item) for item in concept_records),
        "relations.jsonl": b"".join(_canonical_line(item) for item in relation_records),
        "held.jsonl": b"".join(_canonical_line(item) for item in withheld_records),
    }
    file_manifest = {
        name: {"sha256": _digest(payload), "bytes": len(payload)}
        for name, payload in sorted(payloads.items())
    }
    manifest = {
        "schema": ATLAS_MANIFEST_SCHEMA,
        "release_sha256": release.digest,
        "shape_policy_sha256": release.shape_policy_sha256,
        "active_set_sha256": release.active_set_sha256,
        "files": file_manifest,
    }
    manifest_payload = _canonical_bytes(manifest)
    bundle_id = _digest(manifest_payload)
    return payloads, manifest_payload, bundle_id
