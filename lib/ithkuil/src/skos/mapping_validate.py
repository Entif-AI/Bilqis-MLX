"""Reject contradictory mapping batches without semantic adjudication (#65)."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from rdflib import Graph

from .errors import ProfileError
from .mapping import HELD_REASON_BY_STATE
from .mapping_admission import PolicyTable
from .mapping_emit import MappingEmission, MappingIssue, ReviewedMappingRow, emit_admitted_mappings


def _pair(row: ReviewedMappingRow) -> tuple[str, str]:
    return tuple(sorted((row.claim.source_iri, row.claim.target_iri)))


def _signature(row: ReviewedMappingRow) -> tuple:
    claim = row.claim
    return (claim.predicate, claim.review_state, claim.source_scheme_iri,
            claim.target_scheme_iri, claim.independent_schemes, claim.exactness_proof_ref,
            claim.qualification_ref, claim.direction_ref)


def validate_mapping_batch(
    rows: Iterable[ReviewedMappingRow], endpoint_graph: Graph, policy: PolicyTable,
) -> MappingEmission:
    """A complete batch requires compatible review states and admitted endpoints.

    Two opposing hierarchical assertions are contradictory when they reuse the
    same source/review basis. Separately qualified cycles remain legal under #36.
    Non-admitted known review states are retained as held input, never promoted.
    """
    items = tuple(sorted(rows, key=lambda row: row.record_ref))
    pairs, declarations = defaultdict(list), defaultdict(list)
    issues = []
    for row in items:
        claim = row.claim
        pairs[_pair(row)].append(row)
        declarations[(claim.source_iri, claim.target_iri, claim.source_ref, claim.evidence_ref)].append(row)

    for key, group in sorted(declarations.items()):
        if len({_signature(row) for row in group}) > 1:
            issues.append(MappingIssue("MAPPING_CONFLICTING_SOURCE_ASSERTIONS",
                                       tuple(sorted(row.record_ref for row in group)),
                                       (*key[:2], *sorted({row.claim.predicate for row in group}))))
    for pair, group in sorted(pairs.items()):
        admitted_exact = [row for row in group if row.claim.review_state == "admitted_exact_equivalence"]
        rejected = [row for row in group if row.claim.review_state == "rejected_equivalence"]
        if admitted_exact and rejected:
            issues.append(MappingIssue("MAPPING_REJECTED_EQUIVALENCE_CONFLICT",
                                       tuple(sorted(row.record_ref for row in admitted_exact + rejected)), pair))
        bases = defaultdict(list)
        for row in group:
            if row.claim.predicate in {"broadMatch", "narrowMatch"}:
                bases[(row.claim.source_ref, row.claim.evidence_ref)].append(row)
        for basis, hierarchy in sorted(bases.items()):
            directions = {(row.claim.source_iri, row.claim.target_iri)
                          if row.claim.predicate == "broadMatch"
                          else (row.claim.target_iri, row.claim.source_iri) for row in hierarchy}
            if len(directions) > 1:
                issues.append(MappingIssue("MAPPING_DIRECTION_CONFLICT",
                                           tuple(sorted(row.record_ref for row in hierarchy)),
                                           (*pair, *basis)))

    candidates = tuple(row for row in items if row.claim.review_state not in HELD_REASON_BY_STATE)
    intentionally_held = {row.record_ref for row in items if row.claim.review_state in HELD_REASON_BY_STATE}
    try:
        emitted = emit_admitted_mappings(candidates, endpoint_graph, policy)
    except ProfileError as error:
        issues.append(MappingIssue(error.code, tuple(row.record_ref for row in candidates), tuple(error.details)))
        emitted = MappingEmission(Graph(), (), (), (), ())
    issues.extend(emitted.issues)
    if issues:
        return MappingEmission(Graph(), (), tuple(sorted({row.record_ref for row in items})),
                               tuple(sorted(set(issues))), ())
    return MappingEmission(emitted.graph, emitted.emitted_records,
                           tuple(sorted(intentionally_held | set(emitted.held_records))), (), emitted.assertions)
