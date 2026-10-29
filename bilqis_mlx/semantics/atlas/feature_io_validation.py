"""Pure validation and parsing for AtlasFeatures/v2 artifacts."""
from __future__ import annotations

from dataclasses import asdict
import json
import math

from ..atlas_features import (
    FACTOR_ROWS, GRAPH_DIM, AtlasFeatures, ConceptFeature,
    FEATURE_CONCEPT_SCHEMA, FEATURE_MANIFEST_SCHEMA,
)
from .feature_io_contracts import _canonical, _invalid, _reject_nonfinite, _SHA

def _validate_map(
    mapping: tuple[tuple[str, int], ...], *, initial: bool,
) -> None:
    if (not isinstance(mapping, tuple)
            or any(not isinstance(pair, tuple) or len(pair) != 2
                   or not isinstance(pair[0], str) or not pair[0]
                   or type(pair[1]) is not int
                   or not 0 <= pair[1] < FACTOR_ROWS
                   for pair in mapping)
            or tuple(sorted(mapping, key=lambda pair: pair[0].encode("utf-8")))
            != mapping):
        _invalid("BAMF_FEATURE_ARTIFACT_CATEGORY_MAP_INVALID")
    rows = dict(mapping)
    learned = [row for _, row in mapping if row >= 2]
    if (len(rows) != len(mapping)
            or rows.get("UNKNOWN") != 0 or rows.get("NONE") != 1
            or len(learned) != len(set(learned))
            or any(identifier != "NONE" and row == 1
                   for identifier, row in mapping)):
        _invalid("BAMF_FEATURE_ARTIFACT_CATEGORY_MAP_INVALID")
    if (sorted(learned) != list(range(2, 2 + len(learned)))
            or (len(learned) < FACTOR_ROWS - 2
                and any(identifier not in ("UNKNOWN", "NONE") and row == 0
                        for identifier, row in mapping))):
        _invalid("BAMF_FEATURE_ARTIFACT_CATEGORY_ALLOCATION_INVALID")
    if initial:
        ids = sorted(
            (identifier for identifier in rows
             if identifier not in ("UNKNOWN", "NONE")),
            key=str.encode)
        if any(rows[identifier] != (
                index + 2 if index + 2 < FACTOR_ROWS else 0)
                for index, identifier in enumerate(ids)):
            _invalid("BAMF_FEATURE_ARTIFACT_CATEGORY_ALLOCATION_INVALID")


def _validate_features(
    value: AtlasFeatures,
    predecessor: AtlasFeatures | None = None,
    *,
    require_lineage: bool = True,
) -> None:
    if not isinstance(value, AtlasFeatures):
        _invalid("BAMF_FEATURE_ARTIFACT_TYPE_INVALID")
    if (value.schema_version != FEATURE_MANIFEST_SCHEMA
            or not all(isinstance(item, str) and _SHA.fullmatch(item)
                       for item in (value.semantic_release,
                                    value.source_bundle_id,
                                    value.atlas_bundle_id))
            or (value.predecessor_digest is not None
                and (not isinstance(value.predecessor_digest, str)
                     or not _SHA.fullmatch(value.predecessor_digest)))):
        _invalid("BAMF_FEATURE_ARTIFACT_IDENTITY_INVALID")
    for mapping in (value.type_map, value.role_map, value.schema_map):
        _validate_map(
            mapping, initial=value.predecessor_digest is None)
    if (not isinstance(value.concepts, tuple)
            or any(not isinstance(item, ConceptFeature)
                   or not isinstance(item.semantic_id, str)
                   or not item.semantic_id
                   or type(item.abi_index) is not int or item.abi_index < 0
                   or not isinstance(item.type_ids, tuple)
                   or any(type(type_id) is not str for type_id in item.type_ids)
                   or tuple(sorted(set(item.type_ids), key=str.encode))
                   != item.type_ids
                   or any(type_id not in dict(value.type_map)
                          for type_id in item.type_ids)
                   or not isinstance(item.graph64, tuple)
                   or len(item.graph64) != GRAPH_DIM
                   or any(type(number) not in (int, float)
                          or not math.isfinite(number)
                          for number in item.graph64)
                   or item.source_status not in (
                       "ADMITTED_SOURCE", "ADMITTED_FORMAL_ABI_UNTYPED")
                   or item.schema_version != FEATURE_CONCEPT_SCHEMA
                   for item in value.concepts)
            or tuple(sorted(value.concepts,
                            key=lambda item: item.semantic_id.encode("utf-8")))
            != value.concepts
            or len({item.semantic_id for item in value.concepts})
            != len(value.concepts)
            or len({item.abi_index for item in value.concepts})
            != len(value.concepts)):
        _invalid("BAMF_FEATURE_ARTIFACT_CONCEPT_INVALID")
    if (not isinstance(value.held_reasons, tuple)
            or any(not isinstance(item, tuple) or len(item) != 2
                   or not all(isinstance(part, str) and part for part in item)
                   for item in value.held_reasons)
            or tuple(sorted(value.held_reasons,
                            key=lambda item: (
                                item[0].encode("utf-8"),
                                item[1].encode("utf-8"))))
            != value.held_reasons):
        _invalid("BAMF_FEATURE_ARTIFACT_HELD_INVALID")
    if require_lineage:
        _validate_lineage(value, predecessor)


def _validate_lineage(
    value: AtlasFeatures, predecessor: AtlasFeatures | None,
) -> None:
    if value.predecessor_digest is None:
        if predecessor is not None:
            _invalid("BAMF_FEATURE_ARTIFACT_UNEXPECTED_PREDECESSOR")
        return
    if predecessor is None:
        _invalid("BAMF_FEATURE_ARTIFACT_PREDECESSOR_REQUIRED")
    _validate_features(predecessor, require_lineage=False)
    if value.predecessor_digest != predecessor.digest:
        _invalid("BAMF_FEATURE_ARTIFACT_PREDECESSOR_MISMATCH")
    for old_map, new_map in (
        (predecessor.type_map, value.type_map),
        (predecessor.role_map, value.role_map),
        (predecessor.schema_map, value.schema_map),
    ):
        old_rows, new_rows = dict(old_map), dict(new_map)
        if any(new_rows.get(identifier) != row
               for identifier, row in old_rows.items()):
            _invalid("BAMF_FEATURE_ARTIFACT_PREDECESSOR_MAP_DRIFT")
        new_ids = sorted(
            (identifier for identifier in new_rows
             if identifier not in old_rows), key=str.encode)
        next_row = max(
            (row for row in old_rows.values() if row >= 2),
            default=1) + 1
        for identifier in new_ids:
            expected = next_row if next_row < FACTOR_ROWS else 0
            if new_rows[identifier] != expected:
                _invalid("BAMF_FEATURE_ARTIFACT_SUCCESSOR_ALLOCATION_DRIFT")
            if expected:
                next_row += 1


def _parse_features(
    payload: bytes, predecessor: AtlasFeatures | None,
) -> AtlasFeatures:
    try:
        data = json.loads(payload, parse_constant=_reject_nonfinite)
        if not isinstance(data, dict) or set(data) != {
                "semantic_release", "source_bundle_id", "atlas_bundle_id",
                "predecessor_digest", "type_map", "role_map", "schema_map",
                "concepts", "held_reasons", "schema_version"}:
            _invalid("BAMF_FEATURE_ARTIFACT_PAYLOAD_INVALID")
        value = AtlasFeatures(
            semantic_release=data["semantic_release"],
            source_bundle_id=data["source_bundle_id"],
            atlas_bundle_id=data["atlas_bundle_id"],
            predecessor_digest=data["predecessor_digest"],
            type_map=tuple(tuple(pair) for pair in data["type_map"]),
            role_map=tuple(tuple(pair) for pair in data["role_map"]),
            schema_map=tuple(tuple(pair) for pair in data["schema_map"]),
            concepts=tuple(ConceptFeature(
                semantic_id=item["semantic_id"],
                abi_index=item["abi_index"],
                type_ids=tuple(item["type_ids"]),
                graph64=tuple(item["graph64"]),
                source_status=item["source_status"],
                schema_version=item["schema_version"],
            ) for item in data["concepts"]),
            held_reasons=tuple(tuple(pair) for pair in data["held_reasons"]),
            schema_version=data["schema_version"],
        )
    except (ValueError, TypeError, KeyError, UnicodeError):
        _invalid("BAMF_FEATURE_ARTIFACT_PAYLOAD_INVALID")
    _validate_features(value, predecessor)
    if _canonical(asdict(value)) != payload:
        _invalid("BAMF_FEATURE_ARTIFACT_NONCANONICAL")
    return value
