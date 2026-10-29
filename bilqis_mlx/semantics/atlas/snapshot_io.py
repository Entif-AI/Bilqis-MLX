"""Low-level verified Atlas artifact file parsing."""
from __future__ import annotations

import json
from pathlib import Path

from ..atlas_projection import (
    ATLAS_MANIFEST_SCHEMA, HEX64,
    AtlasConcept, AtlasLabel, AtlasRealization, AtlasRelation,
    SourceLocus, SourceRecordRef,
    _canonical_bytes, _digest, _fail,
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
