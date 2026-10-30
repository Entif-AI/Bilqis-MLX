"""Small public-source bridge for deferred linguistic-residue tables."""

from __future__ import annotations

from dataclasses import dataclass

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS

from .preflight import CompilerClosure
from .source_public import PublicLocus, clean_locator_parts, public_source_url, safe_public_literal


@dataclass(frozen=True)
class WebSourceIndex:
    sources: dict[str, object]
    sections: frozenset[tuple[str, str]]
    tables: frozenset[tuple[str, str]]

    @classmethod
    def from_closure(cls, closure: CompilerClosure) -> "WebSourceIndex":
        return cls(
            {row["source_id"]: row for row in closure.table("source_manifest").rows},
            frozenset((row["source_id"], row["section_id"])
                      for row in closure.table("source_sections").rows),
            frozenset((row["source_id"], row["table_id"])
                      for row in closure.table("source_tables").rows),
        )


def web_locus(index: WebSourceIndex, row, *, prefix: str = "") -> tuple[PublicLocus | None, str | None]:
    source_id = row.get(prefix + "source_id", "")
    source = index.sources.get(source_id)
    if source is None:
        return None, "SOURCE_REGISTRY_NOT_FOUND"
    source_url = row.get(prefix + "source_url", "")
    if source_url != source["final_url"] or not public_source_url(source_url):
        return None, "SOURCE_URL_REGISTRY_MISMATCH"
    source_title = safe_public_literal(source["title"])
    if source_title is None or safe_public_literal(source_id) is None:
        return None, "SOURCE_PUBLIC_LITERAL_REJECTED"
    section_id = row.get(prefix + "section_id", "")
    table_id = row.get(prefix + "table_id", "")
    if section_id and (source_id, section_id) not in index.sections:
        return None, "SOURCE_SECTION_NOT_FOUND"
    if table_id and (source_id, table_id) not in index.tables:
        return None, "SOURCE_TABLE_NOT_FOUND"
    parts = clean_locator_parts([
        ("source", source_id),
        ("section", section_id),
        ("table", table_id),
        ("line", row.get(prefix + "source_line", "")),
        ("anchor", row.get(prefix + "source_anchor", "")),
    ])
    if parts is None:
        return None, "SOURCE_PUBLIC_LITERAL_REJECTED"
    identifier = ";".join(f"{label}={value}" for label, value in parts)
    citation = "; ".join([source_title, *(f"{label} {value}" for label, value in parts)]) + "."
    if safe_public_literal(citation) is None:
        return None, "SOURCE_PUBLIC_LITERAL_REJECTED"
    return PublicLocus(source_url, source_id, source_title, parts, identifier, citation), None


def add_source_locus(graph: Graph, resource: URIRef, locus: PublicLocus) -> None:
    locus_iri, source_iri = URIRef(locus.iri), URIRef(locus.source_url)
    graph.add((resource, DCTERMS.source, locus_iri))
    graph.add((locus_iri, DCTERMS.source, source_iri))
    graph.add((locus_iri, DCTERMS.identifier, Literal(locus.identifier)))
    graph.add((locus_iri, DCTERMS.bibliographicCitation, Literal(locus.citation)))
    graph.add((source_iri, DCTERMS.identifier, Literal(locus.source_id)))
    graph.add((source_iri, DCTERMS.bibliographicCitation, Literal(locus.source_title)))
