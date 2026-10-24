"""Source-grounded SKOS labels and notes; no paraphrase or authority guessing."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
import re

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import SKOS

from .errors import ProfileError


MAX_SOURCE_TEXT = 180
FIELD_PROPERTIES = {
    "value_name": "prefLabel",
    "category_name": "prefLabel",
    "root_gloss": "prefLabel",
    "preferred_label": "prefLabel",
    "alternate_label": "altLabel",
    "hidden_label": "hiddenLabel",
    "sense_summary": "definition",
    "definition": "definition",
    "scope_note": "scopeNote",
    "note": "note",
    "example": "example",
    "history_note": "historyNote",
    "change_note": "changeNote",
    "editorial_note": "editorialNote",
}
LABEL_PROPERTIES = frozenset({"prefLabel", "altLabel", "hiddenLabel"})
LANGUAGE = re.compile(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*\Z")


@dataclass(frozen=True)
class TextAssertion:
    resource: str
    field: str
    value: str
    language: str | None
    source_ref: str
    scope: str | None = None
    generated: bool = False


def _property(assertion: TextAssertion) -> str:
    if assertion.scope not in {None, "concept", "realization"}:
        raise ProfileError("UNKNOWN_TEXT_SCOPE", assertion.resource, assertion.source_ref)
    if assertion.field == "semantic_summary":
        if assertion.scope is None:
            raise ProfileError("UNKNOWN_TEXT_SCOPE", assertion.resource, assertion.source_ref)
        return "definition" if assertion.scope == "concept" else "note"
    if assertion.field not in FIELD_PROPERTIES:
        raise ProfileError("UNCLASSIFIED_SOURCE_TEXT", assertion.resource, assertion.field)
    prop = FIELD_PROPERTIES[assertion.field]
    if assertion.scope == "realization" and prop in LABEL_PROPERTIES | {"definition"}:
        raise ProfileError("REALIZATION_TEXT_NOT_IDENTITY", assertion.resource, assertion.source_ref)
    return prop


def _term(assertion: TextAssertion) -> tuple[URIRef, URIRef, Literal]:
    if not isinstance(assertion.resource, str) or not assertion.resource.startswith(("http://", "https://", "urn:")):
        raise ProfileError("INVALID_TEXT_RESOURCE", repr(assertion.resource))
    if not isinstance(assertion.source_ref, str) or not assertion.source_ref.strip():
        raise ProfileError("MISSING_TEXT_SOURCE", assertion.resource)
    if assertion.generated is not False:
        raise ProfileError("GENERATED_TEXT_NOT_ADMITTED", assertion.resource, assertion.source_ref)
    if not isinstance(assertion.value, str) or not assertion.value.strip():
        raise ProfileError("EMPTY_SOURCE_TEXT", assertion.resource, assertion.field)
    if len(assertion.value) > MAX_SOURCE_TEXT:
        raise ProfileError("SOURCE_TEXT_TOO_LONG", assertion.resource, assertion.source_ref)
    if not isinstance(assertion.language, str) or not LANGUAGE.fullmatch(assertion.language):
        raise ProfileError("MISSING_OR_INVALID_TEXT_LANGUAGE", assertion.resource, repr(assertion.language))
    return (URIRef(assertion.resource), SKOS[_property(assertion)],
            Literal(assertion.value, lang=assertion.language.lower(), normalize=False))


def project_text(assertions: Iterable[TextAssertion]) -> Graph:
    """Return the complete validated text graph, or a reportable held reason.

    Call per semantic resource in a compiler. No partial graph escapes on a
    conflicting preferred label or identity-level definition. Equal assertions
    deduplicate; differences never resolve by input order, length or popularity.
    """
    rows = tuple(assertions)
    triples = set()
    failures = []
    for row in rows:
        try:
            triples.add(_term(row))
        except ProfileError as error:
            failures.append(error)
    if failures:
        raise min(failures, key=lambda error: (error.code, error.details))
    preferred: dict[tuple[str, str], set[str]] = defaultdict(set)
    definitions: dict[tuple[str, str], set[str]] = defaultdict(set)
    label_kinds: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for subject, predicate, value in triples:
        language = value.language or ""
        if predicate == SKOS.prefLabel:
            preferred[(str(subject), language)].add(str(value))
        if predicate == SKOS.definition:
            definitions[(str(subject), language)].add(str(value))
        if predicate in {SKOS[name] for name in LABEL_PROPERTIES}:
            label_kinds[(str(subject), language, str(value))].add(str(predicate))
    for (resource, language), values in sorted(preferred.items()):
        if len(values) > 1:
            raise ProfileError("PREFERRED_LABEL_CONFLICT", resource, language, *sorted(values))
    for (resource, language), values in sorted(definitions.items()):
        if len(values) > 1:
            raise ProfileError("DEFINITION_CONFLICT", resource, language, *sorted(values))
    for (resource, language, value), kinds in sorted(label_kinds.items()):
        if len(kinds) > 1:
            raise ProfileError("LABEL_KIND_CONFLICT", resource, language, value, *sorted(kinds))
    graph = Graph()
    for triple in sorted(triples, key=lambda t: tuple(term.n3() for term in t)):
        graph.add(triple)
    return graph
