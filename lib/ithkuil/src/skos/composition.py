"""Source-faithful RDF projection for morpheme compositions (#57)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from urllib.parse import quote

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS, XSD

from .errors import ProfileError
from .identity import BASE, Identity
from .notation import NEW_ITHKUIL_DATATYPE_IRI, typed_notation
from .relations import RelationDisposition, decide_relation
from .source_public import PublicLocus, clean_locator_parts, public_source_url, safe_public_literal


PROFILE_VERSION = "bilqis-composition-profile/1"
TYPE_BASE = BASE + "id/composition-type/"
DERIVATION_BASE = BASE + "id/composition-derivation/"
REQUIRED_PROPERTIES = {
    "surfacePattern": "surface_pattern",
    "condition": "condition",
    "componentCount": "component_count",
}


@dataclass(frozen=True)
class CompositionProperty:
    key: str
    iri: str
    source_field: str


@dataclass(frozen=True)
class CompositionProfile:
    admitted_types: frozenset[str]
    admitted_derivations: frozenset[str]
    properties: tuple[CompositionProperty, ...]

    def property(self, key: str) -> URIRef:
        for item in self.properties:
            if item.key == key:
                return URIRef(item.iri)
        raise KeyError(key)


@dataclass(frozen=True, order=True)
class CompositionIssue:
    code: str
    composition_id: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompositionProjection:
    graph: Graph
    emitted_ids: tuple[str, ...]
    held_ids: tuple[str, ...]
    issues: tuple[CompositionIssue, ...]


def _encoded_source_key(value: str) -> str:
    Identity("term", (value,))  # Reuse the canonical source-key validation contract.
    return quote(value, safe="-._~", encoding="utf-8", errors="strict")


def composition_iri(composition_id: str) -> str:
    return BASE + "id/composition/" + _encoded_source_key(composition_id)


def _class_iri(base: str, value: str) -> URIRef:
    return URIRef(base + _encoded_source_key(value))


def load_composition_profile(
    path: str | Path, closure, negative_fixture_path: str | Path,
) -> CompositionProfile:
    """Load the bounded #57 profile and bind its three extension terms to source proof."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ProfileError("COMPOSITION_PROFILE_INVALID", type(error).__name__) from error
    if not isinstance(data, dict) or data.get("profile_version") != PROFILE_VERSION:
        raise ProfileError("COMPOSITION_PROFILE_INVALID")
    relation = decide_relation("composition_membership", source_attested=True)
    if relation.disposition is not RelationDisposition.RELATIONAL_IR_ONLY:
        raise ProfileError("COMPOSITION_SKOS_BOUNDARY_CHANGED")

    rows = {row["composition_id"]: row for row in closure.table("morpheme_compositions").rows}
    observed_types = {row["composition_type"] for row in rows.values()}
    observed_derivations = {row["derivation"] for row in rows.values()}
    admitted_types = data.get("admitted_composition_types")
    admitted_derivations = data.get("admitted_derivations")
    if (not isinstance(admitted_types, list)
            or any(not isinstance(value, str) or not value for value in admitted_types)
            or len(admitted_types) != len(set(admitted_types))
            or not set(admitted_types) <= observed_types):
        raise ProfileError("COMPOSITION_TYPE_PROFILE_INVALID")
    if (not isinstance(admitted_derivations, list)
            or any(not isinstance(value, str) or not value for value in admitted_derivations)
            or len(admitted_derivations) != len(set(admitted_derivations))
            or not set(admitted_derivations) <= observed_derivations):
        raise ProfileError("COMPOSITION_DERIVATION_PROFILE_INVALID")

    raw_terms = data.get("extension_terms")
    if (not isinstance(raw_terms, list) or len(raw_terms) != len(REQUIRED_PROPERTIES)
            or any(not isinstance(item, dict) for item in raw_terms)
            or {item.get("key") for item in raw_terms} != set(REQUIRED_PROPERTIES)):
        raise ProfileError("COMPOSITION_EXTENSION_PROFILE_INVALID")
    properties = []
    for item in raw_terms:
        key = item.get("key")
        expected_field = REQUIRED_PROPERTIES[key]
        fixture = rows.get(item.get("source_fixture"))
        required_text = ("definition", "domain", "range", "source_justification", "skos_gap", "rdf_gap")
        if (item.get("source_field") != expected_field or fixture is None
                or not fixture.get(expected_field)
                or any(not isinstance(item.get(field), str) or not item[field].strip() for field in required_text)
                or item.get("recurring") is not True or item.get("machine_required") is not True):
            raise ProfileError("COMPOSITION_EXTENSION_SOURCE_PROOF_INVALID", str(key))
        iri = Identity("term", (key,)).iri
        if item.get("iri") != iri:
            raise ProfileError("COMPOSITION_EXTENSION_IRI_INVALID", str(key))
        properties.append(CompositionProperty(key, iri, expected_field))

    fixture_id = data.get("negative_source_fixture")
    try:
        negative = Graph().parse(Path(negative_fixture_path), format="turtle")
    except Exception as error:
        raise ProfileError("COMPOSITION_NEGATIVE_PROOF_INVALID") from error
    subject = URIRef(composition_iri(fixture_id)) if isinstance(fixture_id, str) else None
    if (subject is None or (subject, RDF.type, SKOS.Concept) not in negative
            or not any((subject, predicate, None) in negative for predicate in
                       (SKOS.notation, SKOS.broader, SKOS.narrower, SKOS.related))):
        raise ProfileError("COMPOSITION_NEGATIVE_PROOF_INVALID")
    return CompositionProfile(frozenset(admitted_types), frozenset(admitted_derivations),
                              tuple(sorted(properties, key=lambda item: item.key)))


def _locus(row, *, primary: bool, sources, sections, tables) -> tuple[PublicLocus | None, str | None]:
    prefix = "primary_" if primary else ""
    source_id = row.get(prefix + "source_id", "")
    source = sources.get(source_id)
    if source is None:
        return None, "SOURCE_REGISTRY_NOT_FOUND"
    source_url = row.get(prefix + "source_url", "")
    if source_url != source["final_url"] or not public_source_url(source_url):
        return None, "SOURCE_URL_REGISTRY_MISMATCH"
    title = safe_public_literal(source["title"])
    if title is None or safe_public_literal(source_id) is None:
        return None, "SOURCE_PUBLIC_LITERAL_REJECTED"
    section_id = row.get(prefix + "section_id", "")
    table_id = row.get(prefix + "table_id", "")
    if section_id and (source_id, section_id) not in sections:
        return None, "SOURCE_SECTION_NOT_FOUND"
    if table_id and (source_id, table_id) not in tables:
        return None, "SOURCE_TABLE_NOT_FOUND"
    parts = clean_locator_parts([
        ("source", source_id), ("section", section_id), ("table", table_id),
        ("line", row.get(prefix + "source_line", "")),
        ("anchor", row.get(prefix + "source_anchor", "")),
    ])
    if parts is None:
        return None, "SOURCE_PUBLIC_LITERAL_REJECTED"
    identifier = ";".join(f"{label}={value}" for label, value in parts)
    citation = "; ".join([title, *(f"{label} {value}" for label, value in parts)]) + "."
    if safe_public_literal(citation) is None:
        return None, "SOURCE_PUBLIC_LITERAL_REJECTED"
    return PublicLocus(source_url, source_id, title, parts, identifier, citation), None


def _source_graph(resource: URIRef, loci: set[PublicLocus]) -> Graph:
    graph = Graph()
    for locus in sorted(loci):
        locus_iri, source_iri = URIRef(locus.iri), URIRef(locus.source_url)
        graph.add((resource, DCTERMS.source, locus_iri))
        graph.add((locus_iri, DCTERMS.source, source_iri))
        graph.add((locus_iri, DCTERMS.identifier, Literal(locus.identifier)))
        graph.add((locus_iri, DCTERMS.bibliographicCitation, Literal(locus.citation)))
        graph.add((source_iri, DCTERMS.identifier, Literal(locus.source_id)))
        graph.add((source_iri, DCTERMS.bibliographicCitation, Literal(locus.source_title)))
    return graph


def project_compositions(closure, profile: CompositionProfile) -> CompositionProjection:
    """Project #57 composition resources; #58 owns component edges and order."""
    sources = {row["source_id"]: row for row in closure.table("source_manifest").rows}
    sections = {(row["source_id"], row["section_id"]) for row in closure.table("source_sections").rows}
    tables = {(row["source_id"], row["table_id"]) for row in closure.table("source_tables").rows}
    assertions = defaultdict(list)
    for row in closure.table("source_assertions").rows:
        if row["entity_kind"] == "morpheme_composition":
            assertions[row["entity_id"]].append(row)

    graph, emitted, held, issues = Graph(), [], [], []
    pattern_property = profile.property("surfacePattern")
    condition_property = profile.property("condition")
    count_property = profile.property("componentCount")
    for row in sorted(closure.table("morpheme_compositions").rows, key=lambda item: item["composition_id"]):
        cid = row["composition_id"]
        problems = []
        if row["composition_type"] not in profile.admitted_types:
            problems.append(("UNKNOWN_COMPOSITION_TYPE", row["composition_type"]))
        if row["derivation"] not in profile.admitted_derivations:
            problems.append(("UNKNOWN_COMPOSITION_DERIVATION", row["derivation"]))
        try:
            expected_count = int(row["component_count"])
            if expected_count < 0:
                raise ValueError
        except ValueError:
            expected_count = -1
            problems.append(("INVALID_COMPONENT_COUNT", row["component_count"]))
        if not row["surface_pattern"]:
            problems.append(("MISSING_SURFACE_PATTERN",))
        for field in ("construction_name", "semantic_summary", "surface_pattern", "condition"):
            if row[field] and safe_public_literal(row[field]) is None:
                problems.append(("SOURCE_PUBLIC_LITERAL_REJECTED", field))

        loci = set()
        locus, code = _locus(row, primary=True, sources=sources, sections=sections, tables=tables)
        if locus:
            loci.add(locus)
        elif code:
            problems.append((code, "primary"))
        for assertion in sorted(assertions.get(cid, ()), key=lambda item: item["assertion_id"]):
            locus, code = _locus(assertion, primary=False, sources=sources, sections=sections, tables=tables)
            if locus:
                loci.add(locus)
            elif code:
                problems.append((code, assertion["assertion_id"]))
        if not loci:
            problems.append(("NO_PUBLIC_SOURCE_LOCUS",))
        if problems:
            held.append(cid)
            for problem in problems:
                issues.append(CompositionIssue(problem[0], cid, tuple(sorted(problem[1:]))))
            continue

        try:
            resource = URIRef(composition_iri(cid))
            kind = _class_iri(TYPE_BASE, row["composition_type"])
            derivation = _class_iri(DERIVATION_BASE, row["derivation"])
            surface = (typed_notation(row["surface_form_raw"], NEW_ITHKUIL_DATATYPE_IRI)
                       if row["surface_form_raw"] else None)
            if surface is not None and safe_public_literal(row["surface_form_raw"]) is None:
                raise ProfileError("SOURCE_PUBLIC_LITERAL_REJECTED", "surface_form_raw")
        except ProfileError as error:
            held.append(cid)
            issues.append(CompositionIssue(error.code, cid, tuple(error.details)))
            continue
        local = Graph()
        local.add((resource, RDF.type, kind)); local.add((kind, RDF.type, RDFS.Class))
        local.add((kind, DCTERMS.identifier, Literal(row["composition_type"])))
        local.add((resource, RDF.type, derivation)); local.add((derivation, RDF.type, RDFS.Class))
        local.add((derivation, DCTERMS.identifier, Literal(row["derivation"])))
        local.add((resource, DCTERMS.identifier, Literal(cid)))
        local.add((resource, DCTERMS.title, Literal(row["construction_name"])))
        local.add((resource, DCTERMS.description, Literal(row["semantic_summary"])))
        local.add((resource, pattern_property, Literal(row["surface_pattern"])))
        local.add((resource, count_property, Literal(expected_count, datatype=XSD.nonNegativeInteger)))
        if surface is not None:
            local.add((resource, RDF.value, surface))
        if row["condition"]:
            local.add((resource, condition_property, Literal(row["condition"])))
        local += _source_graph(resource, loci)
        graph += local
        emitted.append(cid)
    return CompositionProjection(graph, tuple(emitted), tuple(sorted(held)), tuple(sorted(issues)))
