"""Verified, database-free readback for immutable semantic Atlas artifacts."""
from __future__ import annotations

import json
import hashlib
import hmac
from dataclasses import dataclass
from pathlib import Path

from .atlas_projection import (
    ATLAS_ARTIFACT_SCHEMA,
    ATLAS_CONCEPT_RECORD_SCHEMA,
    ATLAS_MANIFEST_SCHEMA,
    ATLAS_RELATION_RECORD_SCHEMA,
    ATLAS_RELEASE_SCHEMA,
    ATLAS_SNAPSHOT_SCHEMA,
    ATLAS_WITHHELD_RECORD_SCHEMA,
    BANK_SIZE,
    HEX64,
    SHAPE_POLICY,
    AbiEntry,
    AtlasConcept,
    AtlasCounts,
    AtlasLabel,
    AtlasRealization,
    AtlasRelation,
    CorpusCoverageRow,
    FormalDomainBinding,
    FrozenAtlasConcept,
    FrozenAtlasRelation,
    FrozenAtlasSnapshot,
    SourceLocus,
    SourceRecordRef,
    _canonical_bytes,
    _digest,
    _fail,
    _validate_abi_entries,
)


ATLAS_SELECTION_SCHEMA = "bilqis.atlas-artifact-selection/v1"
ATLAS_SOURCE_PIN_REGISTRY_SCHEMA = "bilqis.atlas-source-pin-registry/v1"
ATLAS_SOURCE_PIN_REGISTRY_SHA256 = (
    "842b66ad7b19ddb333610668410820b3f5d703fa1e452d014755c2c5cc308cee")


@dataclass(frozen=True)
class AtlasArtifactSelection:
    """An A01 artifact locator checked against the repo-owned source pin."""

    path: str
    bundle_id: str
    release_sha256: str
    source_bundle_id: str
    schema: str = ATLAS_SELECTION_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.schema) is not str
                or self.schema != ATLAS_SELECTION_SCHEMA
                or type(self.path) is not str or not self.path
                or any(type(value) is not str or not HEX64.fullmatch(value)
                       for value in (
                           self.bundle_id, self.release_sha256,
                           self.source_bundle_id))):
            _fail("ATLAS_SOURCE_SELECTION_INVALID")


def _validate_selection_exact(selection: AtlasArtifactSelection) -> None:
    """A frozen dataclass is not a trust boundary: recheck its live fields."""
    if type(selection) is not AtlasArtifactSelection:
        _fail("ATLAS_SOURCE_SELECTION_INVALID")
    AtlasArtifactSelection.__post_init__(selection)


def _require_registered_source_pin(selection: AtlasArtifactSelection) -> None:
    """Source admission is repository-owned, never a caller-minted bundle ID."""
    _validate_selection_exact(selection)
    path = Path(__file__).with_name("atlas_source_pins_v1.json")
    if path.is_symlink() or not path.is_file():
        _fail("ATLAS_SOURCE_PIN_REGISTRY_MISSING")
    try:
        payload = path.read_bytes()
        registry = json.loads(payload)
    except (OSError, ValueError, UnicodeError) as error:
        _fail("ATLAS_SOURCE_PIN_REGISTRY_INVALID:" + type(error).__name__)
    if (hashlib.sha256(payload).hexdigest()
            != ATLAS_SOURCE_PIN_REGISTRY_SHA256
            or not isinstance(registry, dict)
            or set(registry) != {"schema", "entries"}
            or registry["schema"] != ATLAS_SOURCE_PIN_REGISTRY_SCHEMA
            or payload != _canonical_bytes(registry)
            or not isinstance(registry["entries"], list)):
        _fail("ATLAS_SOURCE_PIN_REGISTRY_INVALID")
    expected_keys = {
        "bundle_id", "release_sha256", "source_bundle_id",
        "source_receipt", "status"}
    entries = registry["entries"]
    if (not entries or any(
            not isinstance(entry, dict)
            or set(entry) != expected_keys
            or any(not isinstance(entry[name], str)
                   or not HEX64.fullmatch(entry[name])
                   for name in ("bundle_id", "release_sha256", "source_bundle_id"))
            or entry["status"] != "A01_SOURCE_ATTESTED_NOT_NEURAL_ADMITTED"
            or not isinstance(entry["source_receipt"], str)
            or not entry["source_receipt"].startswith("docs/evidence/bamf/A01.")
            for entry in entries)
            or len({entry["bundle_id"] for entry in entries}) != len(entries)):
        _fail("ATLAS_SOURCE_PIN_REGISTRY_INVALID")
    if not any(all(hmac.compare_digest(
            getattr(selection, name), entry[name])
            for name in ("bundle_id", "release_sha256", "source_bundle_id"))
            for entry in entries):
        _fail("ATLAS_SOURCE_PIN_NOT_REGISTERED")


def load_pinned_atlas_snapshot(selection: AtlasArtifactSelection) -> FrozenAtlasSnapshot:
    """Reload a source artifact only under an independently governed A01 pin."""
    _require_registered_source_pin(selection)
    return load_atlas_snapshot(
        selection.path,
        expected_bundle_id=selection.bundle_id,
        expected_release_sha256=selection.release_sha256,
        expected_source_bundle_id=selection.source_bundle_id,
    )


def _read_persisted_artifact(bundle_dir: str | Path) -> tuple[str, dict, dict[str, bytes]]:
    root = Path(bundle_dir)
    expected_files = frozenset({
        "atlas.json", "concepts.jsonl", "relations.jsonl", "held.jsonl", "manifest.json"})
    if (root.is_symlink() or not root.is_dir() or not HEX64.fullmatch(root.name)):
        _fail("ATLAS_SNAPSHOT_BUNDLE_PATH_INVALID")
    try:
        members = tuple(root.iterdir())
    except OSError as error:
        _fail("ATLAS_SNAPSHOT_BUNDLE_PATH_INVALID:" + type(error).__name__)
    if ({path.name for path in members} != expected_files
            or any(path.is_symlink() or not path.is_file() for path in members)):
        _fail("ATLAS_SNAPSHOT_FILESET_INVALID")
    manifest_path = root / "manifest.json"
    try:
        manifest_payload = manifest_path.read_bytes()
        manifest = json.loads(manifest_payload)
    except (OSError, ValueError, UnicodeError) as error:
        _fail("ATLAS_SNAPSHOT_MANIFEST_INVALID:" + type(error).__name__)
    if (not isinstance(manifest, dict)
            or set(manifest) != {
                "schema", "release_sha256", "shape_policy_sha256",
                "active_set_sha256", "files"}
            or manifest.get("schema") != ATLAS_MANIFEST_SCHEMA
            or manifest_payload != _canonical_bytes(manifest)
            or not all(HEX64.fullmatch(manifest.get(name, ""))
                       for name in ("release_sha256", "shape_policy_sha256",
                                    "active_set_sha256"))
            or not isinstance(manifest.get("files"), dict)
            or set(manifest["files"]) != expected_files - {"manifest.json"}):
        _fail("ATLAS_SNAPSHOT_MANIFEST_INVALID")
    bundle_id = _digest(manifest_payload)
    if root.name != bundle_id:
        _fail("ATLAS_SNAPSHOT_BUNDLE_ID_MISMATCH")
    payloads = {}
    for name, descriptor in sorted(manifest["files"].items()):
        if (not isinstance(descriptor, dict) or set(descriptor) != {"sha256", "bytes"}
                or not HEX64.fullmatch(descriptor.get("sha256", ""))
                or type(descriptor.get("bytes")) is not int or descriptor["bytes"] < 0):
            _fail("ATLAS_SNAPSHOT_FILE_DESCRIPTOR_INVALID:" + name)
        payload = (root / name).read_bytes()
        if len(payload) != descriptor["bytes"] or _digest(payload) != descriptor["sha256"]:
            _fail("ATLAS_SNAPSHOT_FILE_DIGEST_MISMATCH:" + name)
        payloads[name] = payload
    return bundle_id, manifest, payloads


def _snapshot_concept(value: object) -> AtlasConcept:
    if not isinstance(value, dict) or set(value) != {
            "semantic_id", "kind", "types", "labels", "realizations",
            "source_loci", "relations", "source_rows"}:
        _fail("ATLAS_SNAPSHOT_CONCEPT_INVALID")
    try:
        return AtlasConcept(
            semantic_id=value["semantic_id"],
            kind=value["kind"],
            types=tuple(value["types"]),
            labels=tuple(AtlasLabel(**item) for item in value["labels"]),
            realizations=tuple(AtlasRealization(**item) for item in value["realizations"]),
            source_loci=tuple(SourceLocus(**item) for item in value["source_loci"]),
            relations=tuple(AtlasRelation(**item) for item in value["relations"]),
            source_rows=tuple(SourceRecordRef(**item) for item in value["source_rows"]),
        )
    except (KeyError, TypeError) as error:
        _fail("ATLAS_SNAPSHOT_CONCEPT_INVALID:" + type(error).__name__)


def _jsonl_records(payload: bytes, *, reason: str) -> tuple[dict, ...]:
    try:
        lines = payload.splitlines()
        if any(not line for line in lines):
            _fail(reason + ":BLANK_LINE")
        records = tuple(json.loads(line) for line in lines)
    except (ValueError, TypeError, UnicodeError) as error:
        _fail(reason + ":" + type(error).__name__)
    if any(not isinstance(record, dict) for record in records):
        _fail(reason)
    return records


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
