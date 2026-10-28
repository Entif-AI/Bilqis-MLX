"""Deterministic projection from a pinned SKOS release into Bilqis semantic records.

This module does not allocate neural ABI rows.  It binds source-qualified semantic
identity to one immutable conformance bundle; append-only row allocation belongs to
the successor ABI leaf.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re

from rdflib import BNode, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS

from bilqis_mlx.errors import ErrorBus, SCHOOL, SEMANTIC_COVERAGE
from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.coverage_schema import validate_coverage_receipt
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.rdf_read import read_canonical_graph


ATLAS_RELEASE_SCHEMA = "bilqis.semantic-atlas-release/v1"
ATLAS_VALIDATION_SCHEMA = "bilqis.semantic-atlas-validation/v1"
CONFORMANCE_SCHEMA = "bilqis.skos.conformance/v1"
COVERAGE_SCHEMA = "bilqis.skos.semantic-coverage/v1"
REQUIRED_GATES = frozenset({"coverage", "no-omission", "determinism", "shacl"})
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
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _fail(reason: str) -> None:
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

    def __post_init__(self) -> None:
        if (not self.family or not self.source_owner or not HEX64.fullmatch(self.source_sha256)
                or not self.semantic_ids or len(self.semantic_ids) != len(set(self.semantic_ids))
                or any(not isinstance(item, str) or not item for item in self.semantic_ids)):
            _fail("ATLAS_FORMAL_DOMAIN_BINDING_INVALID")


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
    concepts: tuple[AtlasConcept, ...]
    held_mappings: tuple[HeldMapping, ...]
    formal_domain_bindings: tuple[FormalDomainBinding, ...]

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
        if not isinstance(data, dict):
            raise TypeError("top level must be an object")
        return data, payload
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        _fail(reason + ":" + type(error).__name__)
        raise AssertionError("unreachable") from error


def _prior_abi(value: Mapping | str | Path | bytes) -> tuple[str, str]:
    data, payload = _json_input(value, reason="ATLAS_PRIOR_ABI_INVALID")
    schema = data.get("schema")
    if not isinstance(schema, str) or not schema:
        _fail("ATLAS_PRIOR_ABI_SCHEMA_MISSING")
    return schema, _digest(payload if not isinstance(value, Mapping) else _canonical_bytes(data))


def _verify_bundle(root: Path) -> tuple[str, dict[str, bytes]]:
    if root.is_symlink() or not root.is_dir():
        _fail("ATLAS_SOURCE_BUNDLE_INVALID")
    manifest_path = root / "manifest.json"
    try:
        manifest_payload = manifest_path.read_bytes()
        manifest = json.loads(manifest_payload)
    except (OSError, ValueError, UnicodeError) as error:
        _fail("ATLAS_SOURCE_MANIFEST_INVALID:" + type(error).__name__)
    if (not isinstance(manifest, dict) or not REQUIRED_BUNDLE_FILES <= set(manifest)
            or any(not isinstance(name, str) or not isinstance(sha, str)
                   or not HEX64.fullmatch(sha) for name, sha in manifest.items())):
        _fail("ATLAS_SOURCE_MANIFEST_INVALID")
    if manifest_payload != _canonical_bytes(manifest):
        _fail("ATLAS_SOURCE_MANIFEST_NONCANONICAL")
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
        labels=tuple(sorted(set(labels))),
        realizations=tuple(sorted(set(realizations))),
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
    prior_abi: Mapping | str | Path | bytes,
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
    gates = conformance.get("gates")
    if (not isinstance(gates, list) or {item.get("gate") for item in gates} != REQUIRED_GATES
            or any(item.get("status") != "passed" for item in gates)):
        _fail("ATLAS_CONFORMANCE_GATES_INVALID")

    graph = read_canonical_graph(payloads["canonical.nt"])
    canonical = canonicalize(graph)
    if (canonical.payload != payloads["canonical.nt"]
            or coverage.get("canonical_rdf") != {
                "sha256": canonical.sha256, "triple_count": canonical.triple_count}
            or conformance.get("canonical_sha256") != canonical.sha256
            or payloads["comparison.nt"] != canonical.payload):
        _fail("ATLAS_CANONICAL_RDF_MISMATCH")

    if not isinstance(source_rows, list) or any(
            not isinstance(item, dict) or set(item) != {"domain", "table", "key"}
            or any(not isinstance(item[field], str) or not item[field]
                   for field in ("domain", "table", "key")) for item in source_rows):
        _fail("ATLAS_SOURCE_CENSUS_INVALID")
    if len(source_rows) != coverage["totals"]["source_rows"]:
        _fail("ATLAS_SOURCE_CENSUS_COUNT_MISMATCH")
    no_omission = next(item for item in gates if item["gate"] == "no-omission")
    if no_omission.get("evidence", {}).get("source_rows") != len(source_rows):
        _fail("ATLAS_SOURCE_CENSUS_GATE_MISMATCH")

    source_by_semantic: dict[str, list[SourceRecordRef]] = {}
    held = []
    for domain, domain_receipt in sorted(coverage["domains"].items()):
        for row in domain_receipt["rows"]:
            semantic_id = row.get("semantic_iri")
            ref = SourceRecordRef(domain, row["table"], row["key"])
            if row["status"] == "EMITTED" and isinstance(semantic_id, str) and semantic_id:
                source_by_semantic.setdefault(semantic_id, []).append(ref)
            elif domain == "mapping" and row["status"] in {"HELD", "REJECTED", "UNSUPPORTED"}:
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

    prior_schema, prior_digest = _prior_abi(prior_abi)
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
        concepts=tuple(concepts),
        held_mappings=tuple(sorted(held)),
        formal_domain_bindings=_normalize_bindings(formal_domain_bindings),
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
                release.prior_abi_sha256))
            or type(release.source_row_count) is not int or release.source_row_count < 1):
        _fail("ATLAS_RELEASE_IDENTITY_INVALID")
    if release.concepts != tuple(sorted(release.concepts, key=lambda item: item.semantic_id)):
        _fail("ATLAS_CONCEPT_ORDER_INVALID")
    ids = tuple(item.semantic_id for item in release.concepts)
    if len(ids) != len(set(ids)) or any(not item.source_rows for item in release.concepts):
        _fail("ATLAS_CONCEPT_IDENTITY_INVALID")
    held_ids = {item.semantic_id for item in release.held_mappings if item.semantic_id}
    if held_ids & set(ids):
        _fail("ATLAS_HELD_IDENTITY_ADMITTED")
    if release.held_mappings != tuple(sorted(release.held_mappings)):
        _fail("ATLAS_HELD_MAPPING_ORDER_INVALID")
    if release.formal_domain_bindings != tuple(sorted(release.formal_domain_bindings)):
        _fail("ATLAS_FORMAL_DOMAIN_BINDING_ORDER_INVALID")
    if not {"boolean", "numeric"} <= {item.family for item in release.formal_domain_bindings}:
        _fail("ATLAS_FORMAL_DOMAIN_BINDING_REQUIRED")
    return ReleaseValidation(
        schema=ATLAS_VALIDATION_SCHEMA,
        status="valid",
        release_sha256=release.digest,
        source_row_count=release.source_row_count,
        concept_count=len(release.concepts),
        held_mapping_count=len(release.held_mappings),
        formal_binding_count=len(release.formal_domain_bindings),
    )
