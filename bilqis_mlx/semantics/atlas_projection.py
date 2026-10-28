"""Deterministic projection from a pinned SKOS release into Bilqis semantic records.

This module does not allocate neural ABI rows.  It binds source-qualified semantic
identity to one immutable conformance bundle; append-only row allocation belongs to
the successor ABI leaf.
"""
from __future__ import annotations

from bisect import bisect_left
from collections.abc import Mapping
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import NoReturn

from rdflib import BNode, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS

from bilqis_mlx.errors import ErrorBus, SCHOOL, SEMANTIC_COVERAGE
from bilqis_mlx.vocabulary_growth import digest as semantic_digest
from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.coverage_schema import validate_coverage_receipt
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.publication import json_bytes
from lib.ithkuil.src.skos.rdf_read import read_canonical_graph


ATLAS_RELEASE_SCHEMA = "bilqis.semantic-atlas-release/v1"
ATLAS_VALIDATION_SCHEMA = "bilqis.semantic-atlas-validation/v1"
ATLAS_ARTIFACT_SCHEMA = "bilqis.semantic-atlas-artifact/v1"
ATLAS_MANIFEST_SCHEMA = "bilqis.semantic-atlas-manifest/v1"
ATLAS_CONCEPT_RECORD_SCHEMA = "bilqis.semantic-atlas-concept/v1"
ATLAS_RELATION_RECORD_SCHEMA = "bilqis.semantic-atlas-relation/v1"
ATLAS_WITHHELD_RECORD_SCHEMA = "bilqis.semantic-atlas-withheld/v1"
ATLAS_SNAPSHOT_SCHEMA = "bilqis.semantic-atlas-snapshot/v1"
CONFORMANCE_SCHEMA = "bilqis.skos.conformance/v1"
COVERAGE_SCHEMA = "bilqis.skos.semantic-coverage/v1"
BANK_SIZE = 8192
NATIVE_REGISTRY_MIN_ROWS = 2
NATIVE_REGISTRY_HEADER_COLUMNS = 3
NATIVE_REGISTRY_SYMBOL_COLUMN = 1
NATIVE_REGISTRY_IDENTITY_COLUMN = 2
SHAPE_POLICY = {
    "schema": "bilqis.semantic-abi-shape-policy/v1",
    "bank_size": BANK_SIZE,
    "index_formula": "8192*bank+row",
    "extended_index_bits": 32,
    "fast_codec_max_exclusive": BANK_SIZE,
    "allocation_order": "prior-accepted-then-canonical-new-id",
    "new_row_state": "MASKED_UNTIL_ADMISSION",
}
REQUIRED_GATES = frozenset({"coverage", "no-omission", "determinism", "shacl"})
GATE_VERSIONS = {name: "1.0.0" for name in REQUIRED_GATES}
REQUIRED_BUNDLE_FILES = frozenset({
    "canonical.nt",
    "comparison.nt",
    "coverage.json",
    "source-rows.json",
    "conformance.json",
    "admitted-mappings.nt",
    "gate-coverage.json",
    "gate-no-omission.json",
    "gate-determinism.json",
    "gate-shacl.json",
})
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _canonical_bytes(value: object) -> bytes:
    return json_bytes(value)


def _canonical_line(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _fail(reason: str) -> NoReturn:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


@dataclass(frozen=True, order=True)
class SourceRecordRef:
    domain: str
    table: str
    key: str


@dataclass(frozen=True, order=True)
class AtlasLabel:
    role: str
    value: str
    language: str | None = None


@dataclass(frozen=True, order=True)
class AtlasRealization:
    value: str
    datatype: str | None = None
    language: str | None = None


@dataclass(frozen=True, order=True)
class AtlasRelation:
    predicate: str
    target: str


@dataclass(frozen=True, order=True)
class SourceLocus:
    """Canonical source-locus description with blank-node labels removed."""

    canonical: str


@dataclass(frozen=True)
class AtlasConcept:
    semantic_id: str
    kind: str
    types: tuple[str, ...]
    labels: tuple[AtlasLabel, ...]
    realizations: tuple[AtlasRealization, ...]
    source_loci: tuple[SourceLocus, ...]
    relations: tuple[AtlasRelation, ...]
    source_rows: tuple[SourceRecordRef, ...]


@dataclass(frozen=True, order=True)
class HeldMapping:
    domain: str
    table: str
    key: str
    status: str
    reason_code: str
    owner: str
    semantic_id: str | None = None


@dataclass(frozen=True, order=True)
class FormalDomainBinding:
    family: str
    source_owner: str
    source_sha256: str
    semantic_ids: tuple[str, ...]
    capability_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (not self.family or not self.source_owner or not HEX64.fullmatch(self.source_sha256)
                or not self.semantic_ids or len(self.semantic_ids) != len(set(self.semantic_ids))
                or any(not isinstance(item, str) or not item for item in self.semantic_ids)
                or not isinstance(self.capability_ids, tuple)
                or len(self.capability_ids) != len(set(self.capability_ids))
                or any(not isinstance(item, str) or not item for item in self.capability_ids)):
            _fail("ATLAS_FORMAL_DOMAIN_BINDING_INVALID")


@dataclass(frozen=True, order=True)
class AbiEntry:
    index: int
    bank: int
    row: int
    semantic_id: str
    symbol: str | None
    source: str
    active: bool
    teaching_candidate: bool
    reason: str


@dataclass(frozen=True, order=True)
class CorpusCoverageRow:
    domain: str
    table: str
    key: str
    semantic_id: str | None
    source_disposition: str
    implementation_status: str
    teaching_candidate: bool
    reason_code: str
    teaching_reason: str
    owner: str


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


def _coverage_record(row: dict, domain: str, *, concept_ids: set[str],
                     active_ids: set[str]) -> CorpusCoverageRow:
    semantic_id = row.get("semantic_iri")
    semantic_id = semantic_id if isinstance(semantic_id, str) and semantic_id else None
    status = row["status"]
    if status in {"HELD", "REJECTED", "UNSUPPORTED"}:
        source_disposition = "SOURCE_HELD"
        implementation_status = "NOT_APPLICABLE"
        teaching_candidate = False
        teaching_reason = row["reason_code"]
    elif status == "IR_ONLY":
        source_disposition = "SOURCE_IR_ONLY"
        implementation_status = "NOT_APPLICABLE"
        teaching_candidate = False
        teaching_reason = row["reason_code"]
    elif semantic_id in concept_ids:
        source_disposition = "SOURCE_ELIGIBLE"
        if semantic_id in active_ids:
            implementation_status = "ADMITTED"
            teaching_candidate = True
            teaching_reason = "PRIOR_ACCEPTED_ABI"
        else:
            implementation_status = "IMPLEMENTATION_UNCOVERED"
            teaching_candidate = False
            teaching_reason = "IMPLEMENTATION_UNCOVERED"
    else:
        source_disposition = "SOURCE_EMITTED_NON_CONCEPT"
        implementation_status = "NOT_APPLICABLE"
        teaching_candidate = False
        teaching_reason = row["reason_code"]
    return CorpusCoverageRow(
        domain=domain,
        table=row["table"],
        key=row["key"],
        semantic_id=semantic_id,
        source_disposition=source_disposition,
        implementation_status=implementation_status,
        teaching_candidate=teaching_candidate,
        reason_code=row["reason_code"],
        teaching_reason=teaching_reason,
        owner=row.get("owner", ""),
    )


def _verify_bundle(root: Path) -> tuple[str, dict[str, bytes]]:
    if root.is_symlink() or not root.is_dir():
        _fail("ATLAS_SOURCE_BUNDLE_INVALID")
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        _fail("ATLAS_SOURCE_MANIFEST_INVALID")
    try:
        manifest_payload = manifest_path.read_bytes()
        manifest = json.loads(manifest_payload)
    except (OSError, ValueError, UnicodeError) as error:
        _fail("ATLAS_SOURCE_MANIFEST_INVALID:" + type(error).__name__)
    if (not isinstance(manifest, dict) or set(manifest) != REQUIRED_BUNDLE_FILES
            or any(not isinstance(name, str) or not isinstance(sha, str)
                   or not HEX64.fullmatch(sha) for name, sha in manifest.items())):
        _fail("ATLAS_SOURCE_MANIFEST_INVALID")
    if manifest_payload != _canonical_bytes(manifest):
        _fail("ATLAS_SOURCE_MANIFEST_NONCANONICAL")
    expected_members = REQUIRED_BUNDLE_FILES | {"manifest.json"}
    try:
        members = tuple(root.iterdir())
    except OSError as error:
        _fail("ATLAS_SOURCE_BUNDLE_INVALID:" + type(error).__name__)
    if ({path.name for path in members} != expected_members
            or any(path.is_symlink() or not path.is_file() for path in members)):
        _fail("ATLAS_SOURCE_BUNDLE_MEMBER_SET_INVALID")
    bundle_id = _digest(manifest_payload)
    if HEX64.fullmatch(root.name) and root.name != bundle_id:
        _fail("ATLAS_SOURCE_BUNDLE_ID_MISMATCH")
    payloads: dict[str, bytes] = {}
    for name, expected in sorted(manifest.items()):
        path = root / name
        if path.is_symlink() or not path.is_file():
            _fail("ATLAS_SOURCE_ARTIFACT_MISSING:" + name)
        payload = path.read_bytes()
        if _digest(payload) != expected:
            _fail("ATLAS_SOURCE_ARTIFACT_DIGEST_MISMATCH:" + name)
        payloads[name] = payload
    return bundle_id, payloads


def _validated_gates(conformance: dict, payloads: Mapping[str, bytes]) -> dict[str, dict]:
    gates = conformance.get("gates")
    if not isinstance(gates, list) or len(gates) != len(REQUIRED_GATES):
        _fail("ATLAS_CONFORMANCE_GATES_INVALID")
    result: dict[str, dict] = {}
    for gate in gates:
        if (not isinstance(gate, dict)
                or set(gate) != {"gate", "version", "status", "evidence"}
                or gate.get("gate") not in REQUIRED_GATES
                or gate.get("version") != GATE_VERSIONS[gate["gate"]]
                or gate.get("status") != "passed"
                or not isinstance(gate.get("evidence"), dict)
                or gate["gate"] in result):
            _fail("ATLAS_CONFORMANCE_GATES_INVALID")
        result[gate["gate"]] = gate
    if set(result) != REQUIRED_GATES:
        _fail("ATLAS_CONFORMANCE_GATES_INVALID")
    for gate_name, aggregate in result.items():
        file_name = "gate-" + gate_name + ".json"
        try:
            constituent = json.loads(payloads[file_name])
        except (ValueError, TypeError, UnicodeError) as error:
            _fail("ATLAS_CONFORMANCE_GATE_FILE_INVALID:" + gate_name + ":" + type(error).__name__)
        if (not isinstance(constituent, dict)
                or payloads[file_name] != _canonical_bytes(constituent)
                or constituent != aggregate):
            _fail("ATLAS_CONFORMANCE_GATE_MISMATCH:" + gate_name)
    return result


def _validate_source_census(coverage: dict, source_rows: object) -> tuple[tuple[str, str, str], ...]:
    if not isinstance(source_rows, list) or any(
            not isinstance(item, dict) or set(item) != {"domain", "table", "key"}
            or any(not isinstance(item[field], str) or not item[field]
                   for field in ("domain", "table", "key")) for item in source_rows):
        _fail("ATLAS_SOURCE_CENSUS_INVALID")
    independent = tuple(
        (item["domain"], item["table"], item["key"]) for item in source_rows)
    if len(independent) != len(set(independent)):
        _fail("ATLAS_SOURCE_CENSUS_DUPLICATE")

    covered = []
    try:
        for domain, receipt in coverage["domains"].items():
            for row in receipt["rows"]:
                covered.append((domain, row["table"], row["key"]))
    except (KeyError, TypeError, AttributeError) as error:
        _fail("ATLAS_COVERAGE_CENSUS_INVALID:" + type(error).__name__)
    covered_tuple = tuple(covered)
    if len(covered_tuple) != len(set(covered_tuple)):
        _fail("ATLAS_COVERAGE_CENSUS_DUPLICATE")
    if (len(independent) != coverage["totals"]["source_rows"]
            or len(covered_tuple) != coverage["totals"]["source_rows"]):
        _fail("ATLAS_SOURCE_CENSUS_COUNT_MISMATCH")
    if set(independent) != set(covered_tuple):
        _fail("ATLAS_SOURCE_CENSUS_IDENTITY_MISMATCH")
    return independent


def _stable_term(graph, term, seen: frozenset[str] = frozenset()) -> object:
    if isinstance(term, URIRef):
        return {"iri": str(term)}
    if isinstance(term, Literal):
        return {
            "literal": str(term),
            "datatype": str(term.datatype) if term.datatype else None,
            "language": term.language,
        }
    if isinstance(term, BNode):
        marker = str(term)
        if marker in seen:
            return {"cycle": True}
        child_seen = seen | {marker}
        values = [
            (str(predicate), _stable_term(graph, obj, child_seen))
            for predicate, obj in graph.predicate_objects(term)
        ]
        values.sort(key=lambda item: (item[0], json.dumps(item[1], sort_keys=True,
                                                          ensure_ascii=False)))
        return {"node": values}
    return {"term": str(term)}


def _locus(graph, term) -> SourceLocus:
    return SourceLocus(json.dumps(_stable_term(graph, term), ensure_ascii=False,
                                  sort_keys=True, separators=(",", ":"), allow_nan=False))


def _concept_kind(semantic_id: str) -> str:
    if "/id/root/" in semantic_id:
        return "root"
    if "/id/sense/" in semantic_id:
        return "sense"
    return "concept"


def _concept(graph, semantic_id: str, source_rows: tuple[SourceRecordRef, ...]) -> AtlasConcept:
    subject = URIRef(semantic_id)
    labels = []
    for role, predicate in (("pref", SKOS.prefLabel), ("alt", SKOS.altLabel),
                            ("hidden", SKOS.hiddenLabel)):
        for value in graph.objects(subject, predicate):
            if isinstance(value, Literal):
                labels.append(AtlasLabel(role, str(value), value.language))
    realizations = [
        AtlasRealization(str(value), str(value.datatype) if value.datatype else None, value.language)
        for value in graph.objects(subject, SKOS.notation) if isinstance(value, Literal)
    ]
    loci = [_locus(graph, value) for value in graph.objects(subject, DCTERMS.source)]
    ignored = {RDF.type, SKOS.prefLabel, SKOS.altLabel, SKOS.hiddenLabel, SKOS.notation,
               DCTERMS.source}
    relations = [
        AtlasRelation(str(predicate), str(obj))
        for predicate, obj in graph.predicate_objects(subject)
        if predicate not in ignored and isinstance(obj, URIRef)
    ]
    return AtlasConcept(
        semantic_id=semantic_id,
        kind=_concept_kind(semantic_id),
        types=tuple(sorted({str(value) for value in graph.objects(subject, RDF.type)
                            if isinstance(value, URIRef)})),
        labels=tuple(sorted(set(labels), key=lambda item: (
            item.role, item.value, item.language or ""))),
        realizations=tuple(sorted(set(realizations), key=lambda item: (
            item.value, item.datatype or "", item.language or ""))),
        source_loci=tuple(sorted(set(loci))),
        relations=tuple(sorted(set(relations))),
        source_rows=tuple(sorted(source_rows)),
    )


def _normalize_bindings(bindings) -> tuple[FormalDomainBinding, ...]:
    if isinstance(bindings, Mapping):
        values = []
        for family, item in bindings.items():
            if isinstance(item, FormalDomainBinding):
                if item.family != family:
                    _fail("ATLAS_FORMAL_DOMAIN_BINDING_FAMILY_MISMATCH")
                values.append(item)
            elif isinstance(item, Mapping):
                values.append(FormalDomainBinding(family=family, **dict(item)))
            else:
                _fail("ATLAS_FORMAL_DOMAIN_BINDING_INVALID")
    else:
        try:
            values = list(bindings)
        except TypeError:
            _fail("ATLAS_FORMAL_DOMAIN_BINDING_INVALID")
    if any(not isinstance(item, FormalDomainBinding) for item in values):
        _fail("ATLAS_FORMAL_DOMAIN_BINDING_INVALID")
    result = tuple(sorted(values))
    if len({item.family for item in result}) != len(result):
        _fail("ATLAS_FORMAL_DOMAIN_BINDING_DUPLICATE")
    if not {"boolean", "numeric"} <= {item.family for item in result}:
        _fail("ATLAS_FORMAL_DOMAIN_BINDING_REQUIRED")
    return result


def compile_atlas_release(
    corpus_dir: str | Path,
    coverage_receipt: Mapping | str | Path | bytes,
    prior_abi: Mapping | str | Path | bytes | FrozenAtlasSnapshot,
    formal_domain_bindings,
) -> AtlasRelease:
    """Compile a source-qualified immutable Atlas projection from one pinned bundle."""
    bundle_id, payloads = _verify_bundle(Path(corpus_dir))
    try:
        coverage = json.loads(payloads["coverage.json"])
        conformance = json.loads(payloads["conformance.json"])
        source_rows = json.loads(payloads["source-rows.json"])
    except (ValueError, TypeError, UnicodeError) as error:
        _fail("ATLAS_SOURCE_JSON_INVALID:" + type(error).__name__)

    supplied_coverage, supplied_bytes = _json_input(
        coverage_receipt, reason="ATLAS_COVERAGE_RECEIPT_INVALID")
    supplied_canonical = (_canonical_bytes(supplied_coverage)
                          if isinstance(coverage_receipt, Mapping) else supplied_bytes)
    if supplied_coverage != coverage or supplied_canonical != payloads["coverage.json"]:
        _fail("ATLAS_COVERAGE_RECEIPT_STALE")
    if coverage.get("schema") != COVERAGE_SCHEMA:
        ErrorBus.raise_(SEMANTIC_COVERAGE.PLAN.VERSION_MISMATCH,
                        actual_schema=coverage.get("schema"), expected_schema=COVERAGE_SCHEMA)
    try:
        validate_coverage_receipt(coverage)
    except ProfileError as error:
        _fail("ATLAS_COVERAGE_INVALID:" + error.code)

    if (not isinstance(conformance, dict) or conformance.get("schema") != CONFORMANCE_SCHEMA
            or conformance.get("status") != "complete" or conformance.get("failed_gates") != []):
        _fail("ATLAS_CONFORMANCE_NOT_COMPLETE")
    gates = _validated_gates(conformance, payloads)

    graph = read_canonical_graph(payloads["canonical.nt"])
    canonical = canonicalize(graph)
    if (canonical.payload != payloads["canonical.nt"]
            or coverage.get("canonical_rdf") != {
                "sha256": canonical.sha256, "triple_count": canonical.triple_count}
            or conformance.get("canonical_sha256") != canonical.sha256
            or payloads["comparison.nt"] != canonical.payload):
        _fail("ATLAS_CANONICAL_RDF_MISMATCH")

    _validate_source_census(coverage, source_rows)
    no_omission = gates["no-omission"]
    if (no_omission["evidence"].get("source_rows") != len(source_rows)
            or no_omission["evidence"].get("accounted_rows") != len(source_rows)):
        _fail("ATLAS_SOURCE_CENSUS_GATE_MISMATCH")

    source_by_semantic: dict[str, list[SourceRecordRef]] = {}
    held = []
    held_semantic_ids = set()
    for domain, domain_receipt in sorted(coverage["domains"].items()):
        for row in domain_receipt["rows"]:
            semantic_id = row.get("semantic_iri")
            ref = SourceRecordRef(domain, row["table"], row["key"])
            if row["status"] == "EMITTED" and isinstance(semantic_id, str) and semantic_id:
                source_by_semantic.setdefault(semantic_id, []).append(ref)
            elif row["status"] in {"HELD", "REJECTED", "UNSUPPORTED"}:
                if isinstance(semantic_id, str) and semantic_id:
                    held_semantic_ids.add(semantic_id)
                if domain == "mapping":
                    held.append(HeldMapping(
                        domain=domain,
                        table=row["table"],
                        key=row["key"],
                        status=row["status"],
                        reason_code=row["reason_code"],
                        owner=row.get("owner", ""),
                        semantic_id=semantic_id if isinstance(semantic_id, str) and semantic_id else None,
                    ))

    concepts = []
    for semantic_id, refs in sorted(source_by_semantic.items()):
        subject = URIRef(semantic_id)
        kind = _concept_kind(semantic_id)
        if kind in {"root", "sense"} or (subject, RDF.type, SKOS.Concept) in graph:
            concepts.append(_concept(graph, semantic_id, tuple(refs)))

    concepts = tuple(concepts)
    bindings = _normalize_bindings(formal_domain_bindings)
    prior_schema, prior_digest, prior_entries = _prior_abi(prior_abi)
    abi_entries = _build_abi_entries(
        prior_entries, concepts, bindings, frozenset(held_semantic_ids))
    active_ids = {entry.semantic_id for entry in abi_entries if entry.active}
    concept_ids = {item.semantic_id for item in concepts}
    coverage_rows = tuple(sorted(
        _coverage_record(row, domain, concept_ids=concept_ids, active_ids=active_ids)
        for domain, receipt in coverage["domains"].items() for row in receipt["rows"]
    ))
    rdf_term_count = len({term for triple in graph for term in triple})
    shape_policy_sha256 = _digest(_canonical_bytes(SHAPE_POLICY))
    active_set_sha256 = _digest(_canonical_bytes(
        [entry.index for entry in abi_entries if entry.active]))
    capabilities = {
        capability for binding in bindings for capability in binding.capability_ids}
    counts = AtlasCounts(
        source_rows=len(source_rows),
        rdf_terms=rdf_term_count,
        semantic_concepts=len(concepts),
        abi_entries=len(abi_entries),
        abi_banks=(len(abi_entries) + BANK_SIZE - 1) // BANK_SIZE,
        active_abi_indices=sum(entry.active for entry in abi_entries),
        trainable_capabilities=len(capabilities),
        source_held=sum(row.source_disposition == "SOURCE_HELD" for row in coverage_rows),
        source_ir_only=sum(row.source_disposition == "SOURCE_IR_ONLY" for row in coverage_rows),
        implementation_uncovered=sum(concept.semantic_id not in active_ids for concept in concepts),
    )
    release = AtlasRelease(
        schema=ATLAS_RELEASE_SCHEMA,
        input_schemas=tuple(sorted((
            ("conformance", conformance["schema"]),
            ("coverage", coverage["schema"]),
            ("prior_abi", prior_schema),
        ))),
        source_bundle_id=bundle_id,
        canonical_rdf_sha256=canonical.sha256,
        coverage_sha256=_digest(payloads["coverage.json"]),
        source_rows_sha256=_digest(payloads["source-rows.json"]),
        conformance_sha256=_digest(payloads["conformance.json"]),
        prior_abi_sha256=prior_digest,
        source_row_count=len(source_rows),
        rdf_term_count=rdf_term_count,
        concepts=concepts,
        held_mappings=tuple(sorted(held)),
        formal_domain_bindings=bindings,
        coverage_rows=coverage_rows,
        abi_entries=abi_entries,
        shape_policy_sha256=shape_policy_sha256,
        active_set_sha256=active_set_sha256,
        counts=counts,
    )
    validate_atlas_release(release)
    return release


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
        "shape_policy": SHAPE_POLICY,
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


def _verify_persisted(target: Path, payloads: dict[str, bytes], manifest_payload: bytes) -> None:
    expected = set(payloads) | {"manifest.json"}
    if target.is_symlink() or not target.is_dir():
        _fail("ATLAS_ARTIFACT_TARGET_INVALID")
    if {path.name for path in target.iterdir()} != expected:
        _fail("ATLAS_ARTIFACT_FILESET_DRIFT")
    for name, payload in {**payloads, "manifest.json": manifest_payload}.items():
        path = target / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
            _fail("ATLAS_ARTIFACT_CONTENT_DRIFT:" + name)


def persist_atlas_release(release: AtlasRelease, output_root: str | Path) -> AtlasArtifactReceipt:
    """Persist one immutable content-addressed semantic release without a database."""
    payloads, manifest_payload, bundle_id = _artifact_payloads(release)
    root = Path(output_root)
    if root.exists() and root.is_symlink():
        _fail("ATLAS_ARTIFACT_ROOT_SYMLINK")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    target = root / bundle_id
    if target.exists():
        _verify_persisted(target, payloads, manifest_payload)
    else:
        temp = Path(tempfile.mkdtemp(prefix=".atlas-", dir=root))
        try:
            for name, payload in {**payloads, "manifest.json": manifest_payload}.items():
                path = temp / name
                with path.open("xb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            directory_fd = os.open(temp, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            try:
                os.rename(temp, target)
                root_fd = os.open(root, os.O_RDONLY)
                try:
                    os.fsync(root_fd)
                finally:
                    os.close(root_fd)
            except OSError:
                if not target.exists():
                    raise
                _verify_persisted(target, payloads, manifest_payload)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    _verify_persisted(target, payloads, manifest_payload)
    manifest = json.loads(manifest_payload)
    return AtlasArtifactReceipt(
        schema=ATLAS_MANIFEST_SCHEMA,
        bundle_id=bundle_id,
        path=str(target),
        release_sha256=release.digest,
        file_sha256=tuple(sorted(
            (name, item["sha256"]) for name, item in manifest["files"].items())),
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
