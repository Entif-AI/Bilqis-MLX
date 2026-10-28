"""Small immutable records used by the #39 source projector."""

from __future__ import annotations

from dataclasses import dataclass

from rdflib import Graph

from .resolver import RecordRef


PRIMARY_KEYS = {
    "grammatical_categories": "category_id",
    "morphemes_atomic": "atomic_id",
    "root_senses": "sense_id",
    "lexicon_roots": "lexicon_root_id",
    "lexicon_root_senses": "lexicon_sense_id",
    "lexicon_root_evidence": "lexicon_evidence_id",
    "source_assertions": "assertion_id",
}


@dataclass(frozen=True, order=True)
class SourceIssue:
    code: str
    resource_iri: str
    record_refs: tuple[RecordRef, ...]
    details: tuple[str, ...]


@dataclass(frozen=True)
class SourceProjection:
    source_graph: Graph
    issues: tuple[SourceIssue, ...]
    held: tuple[RecordRef, ...]
