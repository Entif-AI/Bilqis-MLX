"""Atlas projection compiler ownership; canonical algorithms preserved."""
from __future__ import annotations
from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SEMANTIC_COVERAGE
from collections.abc import Mapping
from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.coverage_schema import validate_coverage_receipt
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.rdf_read import read_canonical_graph
from pathlib import Path
from rdflib import URIRef
from rdflib.namespace import RDF
from rdflib.namespace import SKOS
import json
from .abi import _build_abi_entries, _json_input, _prior_abi
from .bundle import _validated_gates, _verify_bundle
from .common import ATLAS_RELEASE_SCHEMA, BANK_SIZE, CONFORMANCE_SCHEMA, COVERAGE_SCHEMA, SHAPE_POLICY, _canonical_bytes, _digest, _fail
from .concepts import FormalDomainBinding, HeldMapping, SourceRecordRef
from .coverage import _coverage_record, _validate_source_census
from .rdf import _concept, _concept_kind
from .releases import AtlasCounts, AtlasRelease
from .snapshots import FrozenAtlasSnapshot
from .validation import validate_atlas_release


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
