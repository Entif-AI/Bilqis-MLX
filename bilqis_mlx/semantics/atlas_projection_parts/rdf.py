"""Atlas projection rdf ownership; canonical algorithms preserved."""
from __future__ import annotations
from rdflib import BNode
from rdflib import Literal
from rdflib import URIRef
from rdflib.namespace import DCTERMS
from rdflib.namespace import RDF
from rdflib.namespace import SKOS
import json
from .concepts import AtlasConcept, AtlasLabel, AtlasRealization, AtlasRelation, SourceLocus, SourceRecordRef


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
