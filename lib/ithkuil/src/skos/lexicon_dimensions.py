"""Queryable lexicon Stem/Specification dimensions for issue #52."""

from __future__ import annotations

from dataclasses import dataclass

from rdflib import Graph, Literal, URIRef

from .errors import ProfileError
from .identity import Identity
from .lexicon_senses import LexiconSenseProjection, project_lexicon_senses
from .preflight import CompilerClosure


STEM = URIRef(Identity("term", ("lexiconStem",)).iri)
SPECIFICATION = URIRef(Identity("term", ("lexiconSpecification",)).iri)

ALLOWED_STEMS = frozenset({"ROOT-WIDE", "STEM 1", "STEM 2", "STEM 3", "STEMS 1-3"})
ALLOWED_SPECIFICATIONS = frozenset({"BSC", "CTE", "CSV", "OBJ"})
ALLOWED_SOURCE_LOCUS_KINDS = frozenset({"table", "prose", "compact_numbered_stem"})


@dataclass(frozen=True, order=True)
class LexiconDimensionIssue:
    code: str
    source_sense_ids: tuple[str, ...]
    details: tuple[str, ...] = ()


@dataclass(frozen=True, order=True)
class LexiconDimensionRecord:
    sense: Identity
    parent_root: Identity
    source_sense_ids: tuple[str, ...]
    stem: str
    specification: str
    source_locus_kinds: tuple[str, ...]


@dataclass(frozen=True)
class LexiconDimensionProjection:
    graph: Graph
    records: tuple[LexiconDimensionRecord, ...]
    held_source_ids: tuple[str, ...]
    issues: tuple[LexiconDimensionIssue, ...]


def project_lexicon_dimensions(
    closure: CompilerClosure,
    senses: LexiconSenseProjection | None = None,
) -> LexiconDimensionProjection:
    """Emit only source dimensions; no hierarchy, ordering, or pedagogy."""
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)
    if senses is None:
        senses = project_lexicon_senses(closure)
    if not isinstance(senses, LexiconSenseProjection):
        raise ProfileError("LEXICON_SENSE_PROJECTION_REQUIRED", type(senses).__name__)

    graph = Graph()
    records = []
    issues = []
    held = set(senses.held_source_ids)
    for record in senses.records:
        problems = []
        if record.canonical_stem not in ALLOWED_STEMS:
            problems.append(("INVALID_LEXICON_STEM", record.canonical_stem))
        if record.specification not in ALLOWED_SPECIFICATIONS:
            problems.append(("INVALID_LEXICON_SPECIFICATION", record.specification))
        invalid_modes = sorted(set(record.source_locus_kinds) - ALLOWED_SOURCE_LOCUS_KINDS)
        if invalid_modes:
            problems.append(("UNKNOWN_LEXICON_SOURCE_LOCUS_KIND", *invalid_modes))
        if not record.source_locus_kinds:
            problems.append(("MISSING_LEXICON_SOURCE_LOCUS_KIND",))
        if problems:
            held.update(record.source_sense_ids)
            for problem in problems:
                issues.append(LexiconDimensionIssue(
                    problem[0], record.source_sense_ids, tuple(sorted(problem[1:]))
                ))
            continue

        subject = URIRef(record.identity.iri)
        graph.add((subject, STEM, Literal(record.canonical_stem, normalize=False)))
        graph.add((subject, SPECIFICATION, Literal(record.specification, normalize=False)))
        records.append(LexiconDimensionRecord(
            record.identity,
            record.parent_root,
            record.source_sense_ids,
            record.canonical_stem,
            record.specification,
            record.source_locus_kinds,
        ))
    return LexiconDimensionProjection(
        graph, tuple(records), tuple(sorted(held)), tuple(sorted(set(issues)))
    )


def query_senses(
    records: tuple[LexiconDimensionRecord, ...],
    *,
    parent_root: Identity,
    stem: str,
    specification: str,
) -> tuple[Identity, ...]:
    """Return stable sense identities for an exact root + dimension query."""
    if not isinstance(parent_root, Identity) or parent_root.kind != "root":
        raise ProfileError("ROOT_IDENTITY_REQUIRED", repr(parent_root))
    if stem not in ALLOWED_STEMS:
        raise ProfileError("INVALID_LEXICON_STEM", stem)
    if specification not in ALLOWED_SPECIFICATIONS:
        raise ProfileError("INVALID_LEXICON_SPECIFICATION", specification)
    return tuple(sorted(
        record.sense for record in records
        if record.parent_root == parent_root
        and record.stem == stem
        and record.specification == specification
    ))
