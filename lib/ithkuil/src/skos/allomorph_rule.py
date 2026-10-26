"""Explicit allomorph substitution-rule resources for issue #59."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping
from urllib.parse import quote

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS

from .errors import ProfileError
from .identity import BASE, Identity
from .preflight import CompilerClosure
from .residue_source import WebSourceIndex, add_source_locus, web_locus
from .source_public import safe_public_literal


INPUT_PATTERN = URIRef(Identity("term", ("inputPattern",)).iri)
INTERMEDIATE_PATTERN = URIRef(Identity("term", ("intermediatePattern",)).iri)
OUTPUT_PATTERN = URIRef(Identity("term", ("outputPattern",)).iri)
ALLOMORPH_DOMAIN = URIRef(Identity("term", ("allomorphDomain",)).iri)
CONDITION = URIRef(Identity("term", ("condition",)).iri)


@dataclass(frozen=True, order=True)
class AllomorphRuleIssue:
    code: str
    rule_ids: tuple[str, ...]
    details: tuple[str, ...] = ()


@dataclass(frozen=True, order=True)
class AllomorphRuleRecord:
    rule_id: str
    iri: str
    domain: str
    input_pattern: str
    intermediate_pattern: str
    output_pattern: str
    condition: str


@dataclass(frozen=True)
class AllomorphRuleProjection:
    graph: Graph
    records: tuple[AllomorphRuleRecord, ...]
    emitted_ids: tuple[str, ...]
    held_ids: tuple[str, ...]
    issues: tuple[AllomorphRuleIssue, ...]


def _component(value: str) -> str:
    Identity("term", (value,))
    return quote(value, safe="-._~", encoding="utf-8", errors="strict")


def allomorph_rule_iri(rule_id: str) -> str:
    return BASE + "id/allomorph-rule/" + _component(rule_id)


def project_allomorph_rules(
    closure: CompilerClosure,
    rule_rows: Iterable[Mapping[str, str]],
) -> AllomorphRuleProjection:
    """Project source substitution rules without creating semantic concepts."""
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)
    rows = [dict(row.items()) if hasattr(row, "items") else dict(row.values) for row in rule_rows]
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get("allomorph_rule_id", "")].append(row)
    source_index = WebSourceIndex.from_closure(closure)
    graph, records = Graph(), []
    emitted, held = set(), set()
    issues = []
    for rule_id, group in sorted(grouped.items()):
        source_ids = tuple(sorted(row.get("allomorph_rule_id", "") for row in group if row.get("allomorph_rule_id")))
        problems = []
        if not rule_id or len(group) != 1:
            problems.append(("ALLOMORPH_RULE_ID_NOT_UNIQUE", rule_id))
        row = group[0]
        required = ("domain", "input_pattern", "output_pattern", "condition_summary")
        for field in required:
            value = row.get(field, "")
            if not value:
                problems.append(("ALLOMORPH_RULE_REQUIRED_FIELD_MISSING", field))
            elif safe_public_literal(value) is None:
                problems.append(("SOURCE_PUBLIC_LITERAL_REJECTED", field))
        intermediate = row.get("intermediate_pattern", "")
        if intermediate and safe_public_literal(intermediate) is None:
            problems.append(("SOURCE_PUBLIC_LITERAL_REJECTED", "intermediate_pattern"))
        locus, source_code = web_locus(source_index, row)
        if source_code:
            problems.append((source_code, rule_id))
        if problems:
            held.update(source_ids)
            for problem in problems:
                issues.append(AllomorphRuleIssue(problem[0], source_ids, tuple(sorted(problem[1:]))))
            continue

        subject = URIRef(allomorph_rule_iri(rule_id))
        graph.add((subject, RDF.type, RDFS.Resource))
        graph.add((subject, DCTERMS.identifier, Literal(rule_id)))
        graph.add((subject, ALLOMORPH_DOMAIN, Literal(row["domain"], normalize=False)))
        graph.add((subject, INPUT_PATTERN, Literal(row["input_pattern"], normalize=False)))
        if intermediate:
            graph.add((subject, INTERMEDIATE_PATTERN, Literal(intermediate, normalize=False)))
        graph.add((subject, OUTPUT_PATTERN, Literal(row["output_pattern"], normalize=False)))
        graph.add((subject, CONDITION, Literal(row["condition_summary"], normalize=False)))
        assert locus is not None
        add_source_locus(graph, subject, locus)
        records.append(AllomorphRuleRecord(
            rule_id, str(subject), row["domain"], row["input_pattern"], intermediate,
            row["output_pattern"], row["condition_summary"],
        ))
        emitted.add(rule_id)
    all_ids = {row.get("allomorph_rule_id", "") for row in rows if row.get("allomorph_rule_id")}
    return AllomorphRuleProjection(
        graph, tuple(records), tuple(sorted(emitted)), tuple(sorted(all_ids - emitted | held)),
        tuple(sorted(set(issues)))
    )
