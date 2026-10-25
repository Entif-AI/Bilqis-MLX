"""Source-faithful semantic projection of current affix-degree rows (#56)."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping
from urllib.parse import quote

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS, XSD

from .errors import ProfileError
from .identity import BASE, Identity
from .preflight import CompilerClosure
from .resolver import RecordRef, resolve_identities
from .residue_source import WebSourceIndex, add_source_locus, web_locus
from .source_public import safe_public_literal


DEGREE_OF = URIRef(Identity("term", ("degreeOf",)).iri)
SCHEME = URIRef(Identity("scheme", ("new-ithkuil",)).iri)


@dataclass(frozen=True, order=True)
class AffixDegreeIssue:
    code: str
    source_degree_ids: tuple[str, ...]
    details: tuple[str, ...] = ()


@dataclass(frozen=True, order=True)
class AffixDegreeRecord:
    iri: str
    affix_root_atomic_id: str
    affix_root_identity: Identity
    degree: int
    source_degree_ids: tuple[str, ...]
    meaning_summary: str


@dataclass(frozen=True)
class AffixDegreeProjection:
    graph: Graph
    records: tuple[AffixDegreeRecord, ...]
    emitted_source_ids: tuple[str, ...]
    held_source_ids: tuple[str, ...]
    issues: tuple[AffixDegreeIssue, ...]


def _component(value: str) -> str:
    Identity("term", (value,))
    return quote(value, safe="-._~", encoding="utf-8", errors="strict")


def affix_degree_iri(affix_root_atomic_id: str, degree: int | str) -> str:
    degree_text = str(degree)
    if not degree_text.isascii() or not degree_text.isdigit() or str(int(degree_text)) != degree_text:
        raise ProfileError("INVALID_AFFIX_DEGREE", degree_text)
    return BASE + "id/affix-degree/" + _component(affix_root_atomic_id) + "/" + degree_text


def _atomic_identity_map(closure: CompilerClosure) -> dict[str, Identity]:
    result = defaultdict(set)
    for resource in resolve_identities(closure).resources:
        for ref in resource.source_records:
            if ref.table == "morphemes_atomic":
                result[ref.key].add(resource.identity)
    output = {}
    for atomic_id, identities in result.items():
        if len(identities) == 1:
            output[atomic_id] = next(iter(identities))
    return output


def project_affix_degrees(
    closure: CompilerClosure,
    degree_rows: Iterable[Mapping[str, str]],
) -> AffixDegreeProjection:
    """Project stable `(affix_root_atomic_id, degree)` concepts from deferred rows."""
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)
    rows = [dict(row.items()) if hasattr(row, "items") else dict(row.values) for row in degree_rows]
    source_keys = [row.get("degree_id", "") for row in rows]
    if any(not key for key in source_keys):
        raise ProfileError("AFFIX_DEGREE_SOURCE_ID_REQUIRED")
    duplicate_keys = sorted(key for key, count in Counter(source_keys).items() if count > 1)
    if duplicate_keys:
        raise ProfileError("DUPLICATE_AFFIX_DEGREE_SOURCE_ID", *duplicate_keys)
    atomic_identities = _atomic_identity_map(closure)
    affix_roots = {
        row["atomic_id"] for row in closure.table("morphemes_atomic").rows
        if row["morpheme_family"] == "affix_root"
    }
    source_index = WebSourceIndex.from_closure(closure)
    by_coordinate = defaultdict(list)
    for row in rows:
        by_coordinate[(row.get("affix_root_atomic_id", ""), row.get("degree", ""))].append(row)

    graph = Graph()
    records = []
    emitted, held = set(), set()
    issues = []
    for (root_id, degree_text), grouped in sorted(by_coordinate.items()):
        source_ids = tuple(sorted(row.get("degree_id", "") for row in grouped if row.get("degree_id")))
        problems = []
        if not source_ids or len(source_ids) != len(grouped) or len(set(source_ids)) != len(source_ids):
            problems.append(("INVALID_AFFIX_DEGREE_SOURCE_ID",))
        try:
            degree = int(degree_text)
            if degree < 0 or str(degree) != degree_text:
                raise ValueError
            iri = affix_degree_iri(root_id, degree)
        except (ValueError, ProfileError):
            degree, iri = -1, ""
            problems.append(("INVALID_AFFIX_DEGREE", degree_text))
        root_identity = atomic_identities.get(root_id)
        if root_identity is None:
            problems.append(("AFFIX_DEGREE_ROOT_NOT_RESOLVED", root_id))
        elif root_id not in affix_roots:
            problems.append(("AFFIX_DEGREE_ROOT_KIND_INVALID", root_id))
        meanings = {row.get("meaning_summary", "") for row in grouped}
        if len(meanings) != 1 or not next(iter(meanings), ""):
            problems.append(("AFFIX_DEGREE_MEANING_CONFLICT",))
        meaning = next(iter(meanings), "")
        if meaning and safe_public_literal(meaning) is None:
            problems.append(("SOURCE_PUBLIC_LITERAL_REJECTED", "meaning_summary"))
        loci = set()
        for row in grouped:
            locus, code = web_locus(source_index, row)
            if locus is not None:
                loci.add(locus)
            elif code:
                problems.append((code, row.get("degree_id", "")))
        if not loci:
            problems.append(("NO_PUBLIC_SOURCE_LOCUS",))
        if problems:
            held.update(source_ids)
            for problem in problems:
                issues.append(AffixDegreeIssue(problem[0], source_ids, tuple(sorted(problem[1:]))))
            continue

        subject = URIRef(iri)
        graph.add((subject, RDF.type, SKOS.Concept))
        graph.add((subject, SKOS.inScheme, SCHEME))
        graph.add((subject, SKOS.definition, Literal(meaning, lang="en")))
        graph.add((subject, RDF.value, Literal(degree, datatype=XSD.nonNegativeInteger)))
        graph.add((subject, DEGREE_OF, URIRef(root_identity.iri)))
        for source_id in source_ids:
            graph.add((subject, DCTERMS.identifier, Literal(source_id)))
        for locus in sorted(loci):
            add_source_locus(graph, subject, locus)
        records.append(AffixDegreeRecord(iri, root_id, root_identity, degree, source_ids, meaning))
        emitted.update(source_ids)
    all_ids = {row.get("degree_id", "") for row in rows if row.get("degree_id")}
    return AffixDegreeProjection(
        graph,
        tuple(records),
        tuple(sorted(emitted)),
        tuple(sorted(all_ids - emitted | held)),
        tuple(sorted(set(issues))),
    )


def degrees_for_root(
    records: tuple[AffixDegreeRecord, ...], affix_root_atomic_id: str
) -> tuple[AffixDegreeRecord, ...]:
    """Source degree order for query/display only; it asserts no RDF ordering relation."""
    return tuple(sorted(
        (record for record in records if record.affix_root_atomic_id == affix_root_atomic_id),
        key=lambda record: (record.degree, record.iri),
    ))
