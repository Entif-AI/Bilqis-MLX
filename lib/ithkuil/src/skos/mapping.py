"""Normative cross-scheme SKOS mapping admission for issue #36."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
import re
import unicodedata

from rdflib import Graph, URIRef
from rdflib.namespace import SKOS

from .errors import ProfileError


PREDICATE_IRIS = {
    "exactMatch": SKOS.exactMatch,
    "closeMatch": SKOS.closeMatch,
    "broadMatch": SKOS.broadMatch,
    "narrowMatch": SKOS.narrowMatch,
    "relatedMatch": SKOS.relatedMatch,
}

ADMITTED_STATE_BY_PREDICATE = {
    "exactMatch": "admitted_exact_equivalence",
    "closeMatch": "admitted_close_match",
    "broadMatch": "admitted_broad_match",
    "narrowMatch": "admitted_narrow_match",
    "relatedMatch": "admitted_related_match",
}

HELD_REASON_BY_STATE = {
    "proposal": "MAPPING_PROPOSAL_HELD",
    "blocked": "MAPPING_BLOCKED_HELD",
    "deferred": "MAPPING_DEFERRED_HELD",
    "historical_only": "MAPPING_HISTORICAL_ONLY_HELD",
    "rejected_equivalence": "MAPPING_REJECTED_EQUIVALENCE_HELD",
    "ambiguous": "MAPPING_AMBIGUOUS_HELD",
}

KNOWN_REVIEW_STATES = frozenset(
    set(ADMITTED_STATE_BY_PREDICATE.values()) | set(HELD_REASON_BY_STATE)
)

ABSOLUTE_IRI = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
IRI_FORBIDDEN = frozenset('<>"{}|\\^') | {chr(96)}


def _validate_iri(value: str, code: str) -> str:
    if not isinstance(value, str) or not value or not ABSOLUTE_IRI.match(value):
        raise ProfileError(code, repr(value))
    if any(
        char.isspace()
        or char in IRI_FORBIDDEN
        or 0xD800 <= ord(char) <= 0xDFFF
        or unicodedata.category(char) in {"Cc", "Cs"}
        for char in value
    ):
        raise ProfileError(code, repr(value))
    return value


def _required_ref(value: str | None, code: str, *details: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProfileError(code, *details)
    return value


@dataclass(frozen=True)
class MappingClaim:
    """A normalized review-state claim, never a raw crosswalk/bridge row."""

    source_iri: str
    target_iri: str
    source_scheme_iri: str
    target_scheme_iri: str
    predicate: str
    review_state: str
    source_ref: str
    evidence_ref: str
    independent_schemes: bool | None = None
    exactness_proof_ref: str | None = None
    qualification_ref: str | None = None
    direction_ref: str | None = None

    def __post_init__(self) -> None:
        _validate_iri(self.source_iri, "INVALID_MAPPING_SOURCE_IRI")
        _validate_iri(self.target_iri, "INVALID_MAPPING_TARGET_IRI")
        _validate_iri(self.source_scheme_iri, "INVALID_MAPPING_SOURCE_SCHEME_IRI")
        _validate_iri(self.target_scheme_iri, "INVALID_MAPPING_TARGET_SCHEME_IRI")
        _required_ref(self.source_ref, "MAPPING_SOURCE_REF_REQUIRED")
        _required_ref(self.evidence_ref, "MAPPING_EVIDENCE_REF_REQUIRED")
        if not isinstance(self.predicate, str) or not isinstance(self.review_state, str):
            raise ProfileError("INVALID_MAPPING_REVIEW_FIELDS")
        if self.independent_schemes is not True and self.independent_schemes is not False:
            raise ProfileError("MAPPING_SCHEME_DISPOSITION_REQUIRED")


@dataclass(frozen=True)
class MappingDecision:
    """One normalized claim's deterministic emit/hold disposition."""

    claim: MappingClaim
    disposition: str
    reason_code: str | None = None

    @property
    def emitted(self) -> bool:
        return self.disposition == "emit"


def decide_mapping(claim: MappingClaim) -> MappingDecision:
    """Decide one normalized claim without reading raw corpus adapter state."""
    if not isinstance(claim, MappingClaim):
        raise ProfileError("MAPPING_CLAIM_REQUIRED", repr(claim))
    if claim.predicate not in PREDICATE_IRIS:
        raise ProfileError("UNKNOWN_MAPPING_PREDICATE", claim.predicate)
    if claim.review_state not in KNOWN_REVIEW_STATES:
        raise ProfileError("UNSUPPORTED_MAPPING_REVIEW_STATE", claim.review_state)
    if claim.source_iri == claim.target_iri:
        raise ProfileError("MAPPING_SELF_RELATION_FORBIDDEN", claim.source_iri)

    if not claim.independent_schemes:
        return MappingDecision(claim, "hold", "MAPPING_NOT_INDEPENDENT_SCHEMES")
    if claim.source_scheme_iri == claim.target_scheme_iri:
        return MappingDecision(claim, "hold", "MAPPING_SAME_SCHEME_HELD")

    if claim.review_state in HELD_REASON_BY_STATE:
        return MappingDecision(claim, "hold", HELD_REASON_BY_STATE[claim.review_state])

    required_state = ADMITTED_STATE_BY_PREDICATE[claim.predicate]
    if claim.review_state != required_state:
        raise ProfileError(
            "MAPPING_STATE_PREDICATE_MISMATCH",
            claim.predicate,
            claim.review_state,
            required_state,
        )

    if claim.predicate == "exactMatch":
        _required_ref(
            claim.exactness_proof_ref,
            "EXACT_MATCH_PROOF_REQUIRED",
            claim.source_iri,
            claim.target_iri,
        )
    elif claim.predicate == "closeMatch":
        _required_ref(
            claim.qualification_ref,
            "CLOSE_MATCH_QUALIFICATION_REQUIRED",
            claim.source_iri,
            claim.target_iri,
        )
    elif claim.predicate in {"broadMatch", "narrowMatch"}:
        _required_ref(
            claim.direction_ref,
            "DIRECTIONAL_MAPPING_EVIDENCE_REQUIRED",
            claim.source_iri,
            claim.target_iri,
        )

    return MappingDecision(claim, "emit")


def decide_mappings(claims: Iterable[MappingClaim]) -> tuple[MappingDecision, ...]:
    """Return stable decisions independent of input order."""
    def key(decision: MappingDecision) -> tuple[str, ...]:
        claim = decision.claim
        return (
            claim.source_iri,
            claim.target_iri,
            claim.source_scheme_iri,
            claim.target_scheme_iri,
            claim.predicate,
            claim.review_state,
            claim.source_ref,
            claim.evidence_ref,
            str(claim.independent_schemes),
            claim.exactness_proof_ref or "",
            claim.qualification_ref or "",
            claim.direction_ref or "",
            decision.disposition,
            decision.reason_code or "",
        )

    decisions, failures = [], []
    for claim in claims:
        try:
            decisions.append(decide_mapping(claim))
        except ProfileError as error:
            failures.append(error)
    if failures:
        raise min(failures, key=lambda error: (error.code, error.details))
    return tuple(sorted(decisions, key=key))


def _pair_key(claim: MappingClaim) -> tuple[str, str]:
    return tuple(sorted((claim.source_iri, claim.target_iri)))


def _reachable(source: str, target: str, adjacency: dict[str, set[str]]) -> bool:
    pending, visited = [source], set()
    while pending:
        node = pending.pop()
        if node in visited:
            continue
        visited.add(node)
        for successor in adjacency.get(node, set()):
            if successor == target:
                return True
            if successor not in visited:
                pending.append(successor)
    return False


def validate_mapping_conflicts(
    decisions: Iterable[MappingDecision],
) -> tuple[MappingDecision, ...]:
    """Reject SKOS disjoint-property clashes, including bounded entailed paths.

    Exact/close coexistence and source-qualified hierarchy cycles are legal SKOS.
    Reachability is used for validation only; no inferred triples are emitted.
    """
    rows = tuple(decisions)
    by_pair: dict[tuple[str, str], list[MappingDecision]] = defaultdict(list)
    for decision in rows:
        if decision.emitted:
            by_pair[_pair_key(decision.claim)].append(decision)

    for pair, group in sorted(by_pair.items()):
        kinds = {decision.claim.predicate for decision in group}
        hierarchy = bool(kinds & {"broadMatch", "narrowMatch"})
        if (("exactMatch" in kinds and (hierarchy or "relatedMatch" in kinds))
                or (hierarchy and "relatedMatch" in kinds)):
            predicates = tuple(
                sorted(
                    f"{decision.claim.source_iri} {decision.claim.predicate} "
                    f"{decision.claim.target_iri}"
                    for decision in group
                )
            )
            raise ProfileError("CONFLICTING_MAPPING_PREDICATES", *pair, *predicates)
    exact: dict[str, set[str]] = defaultdict(set)
    broader: dict[str, set[str]] = defaultdict(set)
    for decision in rows:
        if not decision.emitted:
            continue
        claim = decision.claim
        if claim.predicate == "exactMatch":
            exact[claim.source_iri].add(claim.target_iri)
            exact[claim.target_iri].add(claim.source_iri)
        elif claim.predicate == "broadMatch":
            broader[claim.source_iri].add(claim.target_iri)
        elif claim.predicate == "narrowMatch":
            broader[claim.target_iri].add(claim.source_iri)
    for pair, group in sorted(by_pair.items()):
        kinds = {decision.claim.predicate for decision in group}
        if kinds & {"broadMatch", "narrowMatch", "relatedMatch"} and _reachable(*pair, exact):
            raise ProfileError("ENTAILED_MAPPING_CONFLICT", *pair, "EXACT_MATCH_TRANSITIVE_CLASH")
        if "relatedMatch" in kinds and (_reachable(*pair, broader) or _reachable(*reversed(pair), broader)):
            raise ProfileError("ENTAILED_MAPPING_CONFLICT", *pair, "HIERARCHY_RELATED_CLASH")
    return rows


def _mapping_triples(claim: MappingClaim) -> set[tuple[URIRef, URIRef, URIRef]]:
    source = URIRef(claim.source_iri)
    target = URIRef(claim.target_iri)
    predicate = PREDICATE_IRIS[claim.predicate]
    triples = {(source, predicate, target)}
    if claim.predicate in {"exactMatch", "closeMatch", "relatedMatch"}:
        triples.add((target, predicate, source))
    elif claim.predicate == "broadMatch":
        triples.add((target, SKOS.narrowMatch, source))
    elif claim.predicate == "narrowMatch":
        triples.add((target, SKOS.broadMatch, source))
    return triples


def project_mappings(
    claims: Iterable[MappingClaim],
) -> tuple[Graph, tuple[MappingDecision, ...]]:
    """Build only admitted SKOS mappings and retain all held decisions separately."""
    decisions = validate_mapping_conflicts(decide_mappings(claims))
    graph = Graph()
    for decision in decisions:
        if not decision.emitted:
            continue
        for triple in sorted(
            _mapping_triples(decision.claim),
            key=lambda row: tuple(term.n3() for term in row),
        ):
            graph.add(triple)
    return graph, decisions
