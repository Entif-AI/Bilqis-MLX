"""Normative minimal Bilqis RDF extension vocabulary freeze (#60)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path

from rdflib import Graph

from .errors import ProfileError
from .identity import BASE, Identity


SCHEMA = "bilqis-extension-vocabulary/v1"
VOCAB_PREFIX = BASE + "vocab/"


@dataclass(frozen=True, order=True)
class VocabularyTerm:
    key: str
    iri: str
    definition: str
    domain: str
    range: str
    cardinality: str
    source_table: str
    source_key_field: str
    source_fixture: str
    source_fields: tuple[str, ...]
    source_justification: str
    owner_issues: tuple[int, ...]
    rejected_alternatives: tuple[tuple[str, str], ...]
    non_goals: tuple[str, ...]
    subproperty_of: str | None


@dataclass(frozen=True, order=True)
class RejectedTerm:
    key: str
    iri: str
    reason: str
    owner_issues: tuple[int, ...]


@dataclass(frozen=True)
class ExtensionVocabulary:
    terms: tuple[VocabularyTerm, ...]
    reviewed_not_admitted: tuple[RejectedTerm, ...]

    @property
    def admitted_iris(self) -> frozenset[str]:
        return frozenset(term.iri for term in self.terms)

    @property
    def admitted_keys(self) -> frozenset[str]:
        return frozenset(term.key for term in self.terms)


def _required_text(item: dict, fields: tuple[str, ...], code: str, key: str) -> None:
    if any(not isinstance(item.get(field), str) or not item[field].strip() for field in fields):
        raise ProfileError(code, key)


def _source_fixture(item: dict, source_csv_root: Path) -> None:
    key = item["key"]
    relative = Path(item["source_table"])
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".csv":
        raise ProfileError("EXTENSION_VOCAB_SOURCE_PATH_INVALID", key)
    path = source_csv_root / relative
    if not path.resolve().is_relative_to(source_csv_root.resolve()):
        raise ProfileError("EXTENSION_VOCAB_SOURCE_PATH_INVALID", key)
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, strict=True)
            rows = list(reader)
            fields = reader.fieldnames or []
    except (OSError, UnicodeError, csv.Error) as error:
        raise ProfileError("EXTENSION_VOCAB_SOURCE_MISSING", key, item["source_table"]) from error
    required = {item["source_key_field"], *item["source_fields"]}
    if not required <= set(fields):
        raise ProfileError("EXTENSION_VOCAB_SOURCE_SHAPE_INVALID", key)
    matches = [row for row in rows if row[item["source_key_field"]] == item["source_fixture"]]
    if len(matches) != 1:
        raise ProfileError("EXTENSION_VOCAB_SOURCE_FIXTURE_CARDINALITY", key, str(len(matches)))
    if any(not matches[0][field].strip() for field in item["source_fields"]):
        raise ProfileError("EXTENSION_VOCAB_SOURCE_FIXTURE_INCOMPLETE", key)


def load_extension_vocabulary(path: str | Path, source_csv_root: str | Path) -> ExtensionVocabulary:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ProfileError("EXTENSION_VOCAB_INVALID", type(error).__name__) from error
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ProfileError("EXTENSION_VOCAB_INVALID")
    raw_terms = data.get("admitted_terms")
    raw_rejected = data.get("reviewed_not_admitted")
    if not isinstance(raw_terms, list) or not isinstance(raw_rejected, list):
        raise ProfileError("EXTENSION_VOCAB_INVALID")

    terms = []
    seen_keys, seen_iris = set(), set()
    source_root = Path(source_csv_root)
    for item in raw_terms:
        if not isinstance(item, dict):
            raise ProfileError("EXTENSION_VOCAB_TERM_INVALID")
        key = item.get("key", "")
        _required_text(item, (
            "key", "iri", "definition", "domain", "range", "cardinality",
            "source_table", "source_key_field", "source_fixture", "source_justification",
        ), "EXTENSION_VOCAB_TERM_INVALID", key)
        expected_iri = Identity("term", (key,)).iri
        if item["iri"] != expected_iri or key in seen_keys or item["iri"] in seen_iris:
            raise ProfileError("EXTENSION_VOCAB_IDENTITY_INVALID", key)
        source_fields = item.get("source_fields")
        owners = item.get("owner_issues")
        alternatives = item.get("rejected_alternatives")
        non_goals = item.get("non_goals")
        if (not isinstance(source_fields, list) or not source_fields
                or any(not isinstance(value, str) or not value for value in source_fields)
                or not isinstance(owners, list) or not owners or any(type(value) is not int or value < 1 for value in owners)
                or not isinstance(alternatives, list) or not alternatives
                or not isinstance(non_goals, list) or any(not isinstance(value, str) or not value for value in non_goals)):
            raise ProfileError("EXTENSION_VOCAB_TERM_INVALID", key)
        rejected_pairs = []
        for alt in alternatives:
            if not isinstance(alt, dict):
                raise ProfileError("EXTENSION_VOCAB_ALTERNATIVE_INVALID", key)
            _required_text(alt, ("candidate", "reason"), "EXTENSION_VOCAB_ALTERNATIVE_INVALID", key)
            rejected_pairs.append((alt["candidate"], alt["reason"]))
        if item.get("subproperty_of") is not None:
            raise ProfileError("EXTENSION_VOCAB_UNPROVEN_SUBPROPERTY", key)
        _source_fixture(item, source_root)
        terms.append(VocabularyTerm(
            key, item["iri"], item["definition"], item["domain"], item["range"],
            item["cardinality"], item["source_table"], item["source_key_field"],
            item["source_fixture"], tuple(source_fields), item["source_justification"],
            tuple(sorted(set(owners))), tuple(sorted(rejected_pairs)), tuple(non_goals), None,
        ))
        seen_keys.add(key); seen_iris.add(item["iri"])

    rejected = []
    for item in raw_rejected:
        if not isinstance(item, dict):
            raise ProfileError("EXTENSION_VOCAB_REJECTION_INVALID")
        key = item.get("key", "")
        _required_text(item, ("key", "iri", "reason"), "EXTENSION_VOCAB_REJECTION_INVALID", key)
        owners = item.get("owner_issues")
        if (not isinstance(owners, list) or not owners or any(type(value) is not int or value < 1 for value in owners)
                or item["iri"] != Identity("term", (key,)).iri or key in seen_keys):
            raise ProfileError("EXTENSION_VOCAB_REJECTION_INVALID", key)
        rejected.append(RejectedTerm(key, item["iri"], item["reason"], tuple(sorted(set(owners)))))
        seen_keys.add(key)
    return ExtensionVocabulary(tuple(sorted(terms)), tuple(sorted(rejected)))


def validate_graph_vocabulary(graph: Graph, vocabulary: ExtensionVocabulary) -> frozenset[str]:
    if not isinstance(graph, Graph) or not isinstance(vocabulary, ExtensionVocabulary):
        raise ProfileError("EXTENSION_VOCAB_VALIDATION_INPUT_INVALID")
    used = frozenset(
        str(predicate) for _, predicate, _ in graph
        if str(predicate).startswith(VOCAB_PREFIX)
    )
    unadmitted = used - vocabulary.admitted_iris
    if unadmitted:
        raise ProfileError("UNADMITTED_EXTENSION_TERM", *sorted(unadmitted))
    return used
