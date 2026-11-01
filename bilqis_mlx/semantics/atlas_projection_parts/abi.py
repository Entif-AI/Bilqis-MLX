"""Atlas projection abi ownership; canonical algorithms preserved."""
from __future__ import annotations
from bilqis_mlx.vocabulary_growth import digest as semantic_digest
from collections.abc import Mapping
from pathlib import Path
import json
from .common import ATLAS_ARTIFACT_SCHEMA, ATLAS_SNAPSHOT_SCHEMA, BANK_SIZE, HEX64, NATIVE_REGISTRY_HEADER_COLUMNS, NATIVE_REGISTRY_IDENTITY_COLUMN, NATIVE_REGISTRY_MIN_ROWS, NATIVE_REGISTRY_SYMBOL_COLUMN, _canonical_bytes, _digest, _fail
from .concepts import AbiEntry, AtlasConcept, FormalDomainBinding
from .snapshots import FrozenAtlasSnapshot


def _json_input(value: Mapping | str | Path | bytes, *, reason: str) -> tuple[dict, bytes]:
    try:
        if isinstance(value, Mapping):
            data = dict(value)
            payload = _canonical_bytes(data)
        elif isinstance(value, bytes):
            payload = value
            data = json.loads(payload)
        else:
            payload = Path(value).read_bytes()
            data = json.loads(payload)
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        _fail(reason + ":" + type(error).__name__)
    if not isinstance(data, dict):
        _fail(reason + ":TOP_LEVEL_OBJECT_REQUIRED")
    return data, payload

def _prior_abi(
    value: Mapping | str | Path | bytes | FrozenAtlasSnapshot,
) -> tuple[str, str, tuple[AbiEntry, ...]]:
    if isinstance(value, FrozenAtlasSnapshot):
        if (value.schema != ATLAS_SNAPSHOT_SCHEMA
                or not HEX64.fullmatch(value.bundle_id)
                or not value.abi_entries):
            _fail("ATLAS_PRIOR_ABI_SNAPSHOT_INVALID")
        entries = value.abi_entries
        _validate_abi_entries(entries, require_concepts=())
        return ATLAS_ARTIFACT_SCHEMA, value.bundle_id, entries

    data, payload = _json_input(value, reason="ATLAS_PRIOR_ABI_INVALID")
    schema = data.get("schema")
    if schema == ATLAS_ARTIFACT_SCHEMA:
        _fail("ATLAS_PRIOR_ABI_PROVENANCE_REQUIRED")
    rows = data.get("rows")
    if (not isinstance(rows, list)
            or len(rows) < NATIVE_REGISTRY_MIN_ROWS
            or not isinstance(rows[0], list)
            or tuple(str(value) for value in rows[0][:NATIVE_REGISTRY_HEADER_COLUMNS]) != (
                "0-based Token ID", "Bilqis token symbol", "Pasigraphy identity")):
        _fail("ATLAS_PRIOR_ABI_ROWS_REQUIRED")
    native_digest = data.get("native_rows_sha256")
    if native_digest is not None and native_digest != semantic_digest(rows):
        _fail("ATLAS_PRIOR_ABI_NATIVE_ROWS_DIGEST_MISMATCH")
    entries_list = []
    for expected, row in enumerate(rows[1:]):
        if (not isinstance(row, list) or len(row) < NATIVE_REGISTRY_HEADER_COLUMNS
                or str(row[0]) != str(expected)
                or not isinstance(row[NATIVE_REGISTRY_SYMBOL_COLUMN], str)
                or not row[NATIVE_REGISTRY_SYMBOL_COLUMN]
                or not isinstance(row[NATIVE_REGISTRY_IDENTITY_COLUMN], str)
                or not row[NATIVE_REGISTRY_IDENTITY_COLUMN]):
            _fail("ATLAS_PRIOR_ABI_ROW_ORDER_INVALID")
        entries_list.append(AbiEntry(
            index=expected,
            bank=expected // BANK_SIZE,
            row=expected % BANK_SIZE,
            semantic_id=row[NATIVE_REGISTRY_IDENTITY_COLUMN],
            symbol=row[NATIVE_REGISTRY_SYMBOL_COLUMN],
            source="PRIOR_ACCEPTED_NATIVE_REGISTRY",
            active=True,
            teaching_candidate=True,
            reason="PRIOR_ACCEPTED_ABI",
        ))
    entries = tuple(entries_list)
    schema = schema if isinstance(schema, str) and schema else "UNVERSIONED"
    prior_digest = _digest(payload if not isinstance(value, Mapping) else _canonical_bytes(data))
    _validate_abi_entries(entries, require_concepts=())
    return schema, prior_digest, entries

def _validate_abi_entries(entries: tuple[AbiEntry, ...], *, require_concepts) -> None:
    if not entries:
        _fail("ATLAS_ABI_EMPTY")
    for expected, entry in enumerate(entries):
        if (not isinstance(entry, AbiEntry) or entry.index != expected
                or entry.bank != expected // BANK_SIZE or entry.row != expected % BANK_SIZE
                or not isinstance(entry.semantic_id, str) or not entry.semantic_id
                or not isinstance(entry.reason, str) or not entry.reason
                or entry.source not in {
                    "PRIOR_ACCEPTED_NATIVE_REGISTRY", "PRIOR_ATLAS_ABI",
                    "CANONICAL_SKOS", "FORMAL_DOMAIN"}):
            _fail("ATLAS_ABI_ENTRY_INVALID")
    ids = [entry.semantic_id for entry in entries]
    if len(ids) != len(set(ids)):
        _fail("ATLAS_ABI_SEMANTIC_ID_DUPLICATE")
    symbols = [entry.symbol for entry in entries if entry.symbol is not None]
    if len(symbols) != len(set(symbols)):
        _fail("ATLAS_ABI_SYMBOL_DUPLICATE")
    if not set(require_concepts) <= set(ids):
        _fail("ATLAS_ABI_MISSING_SOURCE_CONCEPT")

def _build_abi_entries(
    prior: tuple[AbiEntry, ...],
    concepts: tuple[AtlasConcept, ...],
    bindings: tuple[FormalDomainBinding, ...],
    held_semantic_ids: frozenset[str],
) -> tuple[AbiEntry, ...]:
    prior_ids = {entry.semantic_id for entry in prior}
    concept_ids = {item.semantic_id for item in concepts}
    formal_ids = {semantic_id for binding in bindings for semantic_id in binding.semantic_ids}
    if held_semantic_ids & formal_ids:
        _fail("ATLAS_HELD_IDENTITY_ADMISSION_REQUESTED")
    new_ids = sorted((concept_ids | formal_ids) - prior_ids)
    entries = list(prior)
    for semantic_id in new_ids:
        index = len(entries)
        entries.append(AbiEntry(
            index=index,
            bank=index // BANK_SIZE,
            row=index % BANK_SIZE,
            semantic_id=semantic_id,
            symbol=None,
            source="CANONICAL_SKOS" if semantic_id in concept_ids else "FORMAL_DOMAIN",
            active=False,
            teaching_candidate=False,
            reason="IMPLEMENTATION_UNCOVERED",
        ))
    result = tuple(entries)
    _validate_abi_entries(result, require_concepts=concept_ids | formal_ids)
    return result
