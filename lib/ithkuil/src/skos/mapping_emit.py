"""Emit reviewed mappings against admitted endpoint graphs and finite policy."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, SKOS

from .errors import ProfileError
from .mapping import MappingClaim, decide_mapping, project_mappings
from .mapping_admission import PolicyTable, decide_normalized
from .resolver import RecordRef


OUTCOME_PREDICATES = {
    "EMIT_EXACT": "exactMatch", "EMIT_CLOSE": "closeMatch",
    "EMIT_BROAD": "broadMatch", "EMIT_NARROW": "narrowMatch",
    "EMIT_RELATED": "relatedMatch",
}


@dataclass(frozen=True)
class ReviewedMappingRow:
    """A separately reviewed normalized claim; raw workbook rows are not claims."""

    record_ref: RecordRef
    claim: MappingClaim


@dataclass(frozen=True, order=True)
class MappingIssue:
    code: str
    record_refs: tuple[RecordRef, ...]
    details: tuple[str, ...] = ()


@dataclass(frozen=True, order=True)
class MappingAssertion:
    source_iri: str
    predicate_iri: str
    target_iri: str
    record_refs: tuple[RecordRef, ...]


@dataclass(frozen=True)
class MappingEmission:
    graph: Graph
    emitted_records: tuple[RecordRef, ...]
    held_records: tuple[RecordRef, ...]
    issues: tuple[MappingIssue, ...]
    assertions: tuple[MappingAssertion, ...]

    @property
    def complete(self) -> bool:
        return not self.issues


def _pair(row: ReviewedMappingRow) -> tuple[str, str]:
    return tuple(sorted((row.claim.source_iri, row.claim.target_iri)))


def _conflicting_predicates(details: tuple[str, ...]) -> frozenset[str]:
    """Recover only predicate kinds participating in a #36 direct-pair clash."""
    kinds = {
        parts[1]
        for detail in details
        if len(parts := detail.split()) == 3 and parts[1] in OUTCOME_PREDICATES.values()
    }
    hierarchy = kinds & {"broadMatch", "narrowMatch"}
    conflicting: set[str] = set()
    if "exactMatch" in kinds and (hierarchy or "relatedMatch" in kinds):
        conflicting.add("exactMatch")
        conflicting.update(hierarchy)
        if "relatedMatch" in kinds:
            conflicting.add("relatedMatch")
    elif hierarchy and "relatedMatch" in kinds:
        conflicting.update(hierarchy)
        conflicting.add("relatedMatch")
    return frozenset(conflicting)


def _support_edges(row: ReviewedMappingRow, mode: str) -> tuple[tuple[str, str], ...]:
    claim = row.claim
    if mode == "exact" and claim.predicate == "exactMatch":
        return ((claim.source_iri, claim.target_iri), (claim.target_iri, claim.source_iri))
    if mode == "hierarchy":
        if claim.predicate == "broadMatch":
            return ((claim.source_iri, claim.target_iri),)
        if claim.predicate == "narrowMatch":
            return ((claim.target_iri, claim.source_iri),)
    return ()


def _path_witness_refs(
    rows: tuple[ReviewedMappingRow, ...], start: str, target: str, mode: str,
) -> set[RecordRef]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    support: dict[tuple[str, str], set[RecordRef]] = defaultdict(set)
    for row in rows:
        for edge in _support_edges(row, mode):
            adjacency[edge[0]].add(edge[1])
            support[edge].add(row.record_ref)
    pending = deque((start,))
    previous: dict[str, str | None] = {start: None}
    while pending:
        current = pending.popleft()
        for successor in sorted(adjacency.get(current, ())):
            if successor in previous:
                continue
            previous[successor] = current
            if successor == target:
                refs: set[RecordRef] = set()
                cursor = target
                while previous[cursor] is not None:
                    parent = previous[cursor]
                    refs.update(support[(parent, cursor)])
                    cursor = parent
                return refs
            pending.append(successor)
    return set()


def _conflict_witness_refs(
    error: ProfileError, rows: tuple[ReviewedMappingRow, ...],
) -> tuple[RecordRef, ...]:
    """Localize a #36 conflict without re-deciding its semantic validity."""
    all_refs = tuple(sorted(row.record_ref for row in rows))
    details = tuple(map(str, error.details))
    if len(details) < 3:
        return all_refs
    if error.code == "CONFLICTING_MAPPING_PREDICATES":
        assertions = tuple(
            parts for detail in details
            if len(parts := detail.split()) == 3 and parts[1] in OUTCOME_PREDICATES.values()
        )
        if not assertions:
            return all_refs
        pair = tuple(sorted((assertions[0][0], assertions[0][2])))
        predicates = _conflicting_predicates(details)
        refs = {
            row.record_ref for row in rows
            if _pair(row) == pair and row.claim.predicate in predicates
        }
        return tuple(sorted(refs)) if refs else all_refs
    if error.code != "ENTAILED_MAPPING_CONFLICT":
        return all_refs

    reasons = {"EXACT_MATCH_TRANSITIVE_CLASH", "HIERARCHY_RELATED_CLASH"}
    reason = next((detail for detail in details if detail in reasons), None)
    endpoints = tuple(sorted(detail for detail in details if detail != reason))
    if reason is None or len(endpoints) != 2:
        return all_refs
    pair = endpoints
    refs: set[RecordRef] = set()
    if reason == "EXACT_MATCH_TRANSITIVE_CLASH":
        refs.update(
            row.record_ref for row in rows
            if _pair(row) == pair and row.claim.predicate in {"broadMatch", "narrowMatch", "relatedMatch"}
        )
        refs.update(_path_witness_refs(rows, pair[0], pair[1], "exact"))
    elif reason == "HIERARCHY_RELATED_CLASH":
        refs.update(
            row.record_ref for row in rows
            if _pair(row) == pair and row.claim.predicate == "relatedMatch"
        )
        path = _path_witness_refs(rows, pair[0], pair[1], "hierarchy")
        if not path:
            path = _path_witness_refs(rows, pair[1], pair[0], "hierarchy")
        refs.update(path)
    return tuple(sorted(refs)) if refs else all_refs


def _endpoint_issue(claim: MappingClaim, graph: Graph) -> tuple[str, ...] | None:
    for label, iri, scheme in (
        ("SOURCE", claim.source_iri, claim.source_scheme_iri),
        ("TARGET", claim.target_iri, claim.target_scheme_iri),
    ):
        resource, scheme_node = URIRef(iri), URIRef(scheme)
        types = frozenset(graph.objects(resource, RDF.type))
        if SKOS.Concept not in types:
            if types:
                return ("MAPPING_ENDPOINT_KIND_UNSUPPORTED", label, iri)
            return (f"MAPPING_{label}_ENDPOINT_MISSING", iri)
        if types & {SKOS.Collection, SKOS.OrderedCollection, SKOS.ConceptScheme}:
            return ("MAPPING_ENDPOINT_AMBIGUOUS", label, iri)
        if (scheme_node, RDF.type, SKOS.ConceptScheme) not in graph:
            return ("MAPPING_SCHEME_NOT_ADMITTED", label, scheme)
        if (resource, SKOS.inScheme, scheme_node) not in graph:
            return ("MAPPING_ENDPOINT_SCHEME_MISMATCH", label, iri, scheme)
    return None


def emit_admitted_mappings(
    rows: Iterable[ReviewedMappingRow], endpoint_graph: Graph, policy: PolicyTable,
) -> MappingEmission:
    """Recheck policy and endpoint membership before projecting any strong mapping.

    Source review is an explicit upstream premise, never inferred from the shape
    of the graph or a raw APPROVED strategy label. All output triples retain their
    contributing source-row identities, including equivalent duplicates.
    """
    items = tuple(rows)
    if any(not isinstance(row, ReviewedMappingRow) for row in items):
        raise ProfileError("REVIEWED_MAPPING_ROW_REQUIRED")
    refs = [row.record_ref for row in items]
    duplicate = tuple(sorted(ref for ref in set(refs) if refs.count(ref) > 1))
    if duplicate:
        raise ProfileError("DUPLICATE_MAPPING_RECORD_ID", *(f"{ref.table}:{ref.key}" for ref in duplicate))
    accepted, held, issues = [], set(), []
    for row in sorted(items, key=lambda value: value.record_ref):
        claim, ref = row.claim, row.record_ref
        try:
            decision = decide_normalized(claim.predicate, claim.review_state, policy)
            if not decision.emitting:
                raise ProfileError(decision.reason_code or "MAPPING_NOT_ADMITTED")
            if OUTCOME_PREDICATES.get(decision.outcome) != claim.predicate:
                raise ProfileError("MAPPING_POLICY_PREDICATE_MISMATCH", decision.outcome, claim.predicate)
            qualified = decide_mapping(claim)
            if not qualified.emitted:
                raise ProfileError(qualified.reason_code or "MAPPING_NOT_ADMITTED")
            problem = _endpoint_issue(claim, endpoint_graph)
            if problem:
                raise ProfileError(problem[0], *problem[1:])
        except ProfileError as error:
            held.add(ref)
            issues.append(MappingIssue(error.code, (ref,), tuple(error.details)))
            continue
        accepted.append(row)

    try:
        graph, _ = project_mappings(row.claim for row in accepted)
    except ProfileError as error:
        # A conflicting collection is not silently repaired by picking a row.
        accepted_rows = tuple(accepted)
        implicated = _conflict_witness_refs(error, accepted_rows)
        issues.append(MappingIssue(error.code, implicated, tuple(error.details)))
        held.update(row.record_ref for row in accepted_rows)
        return MappingEmission(Graph(), (), tuple(sorted(held)), tuple(sorted(issues)), ())

    bindings = defaultdict(set)
    for row in accepted:
        single, _ = project_mappings((row.claim,))
        for subject, predicate, target in single:
            bindings[(str(subject), str(predicate), str(target))].add(row.record_ref)
    assertions = tuple(MappingAssertion(*triple, tuple(sorted(record_refs)))
                       for triple, record_refs in sorted(bindings.items()))
    return MappingEmission(
        graph, tuple(sorted(row.record_ref for row in accepted)), tuple(sorted(held)),
        tuple(sorted(issues)), assertions,
    )
