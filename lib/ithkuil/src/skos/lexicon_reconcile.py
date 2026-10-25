"""Deterministic Chapter 1-2 lexicon-domain reconciliation for issue #55."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, SKOS

from .build import input_receipt
from .canonical import CanonicalRdf, canonicalize
from .errors import ProfileError
from .lexicon_dimensions import project_lexicon_dimensions
from .lexicon_links import load_root_sense_term, project_root_sense_links
from .lexicon_roots import project_lexicon_roots
from .lexicon_senses import project_lexicon_senses
from .preflight import CompilerClosure, preflight
from .publication import json_bytes


SCHEMA = "bilqis.skos.lexicon-reconciliation/v1"
FRONTIER = "tracked-new-ithkuil-lexicon-chapters-1-2"
OUTSIDE_CLOSURE = (
    "New Ithkuil Lexicon Chapters 3-7",
    "pinned New Ithkuil affix-reference source",
)


@dataclass(frozen=True)
class LexiconReconciliation:
    graph: Graph
    canonical: CanonicalRdf
    receipt: dict


def validate_dispositions(
    all_ids: set[str], emitted_ids: set[str], held_ids: set[str], *, domain: str
) -> None:
    """Require exactly one emitted-or-held disposition for every source record."""
    overlap = emitted_ids & held_ids
    missing = all_ids - (emitted_ids | held_ids)
    extra = (emitted_ids | held_ids) - all_ids
    if overlap:
        raise ProfileError("LEXICON_DUPLICATE_ACCOUNTING", domain, *sorted(overlap))
    if missing:
        raise ProfileError("LEXICON_MISSING_ACCOUNTING", domain, *sorted(missing))
    if extra:
        raise ProfileError("LEXICON_OUT_OF_SCOPE_ACCOUNTING", domain, *sorted(extra))


def _reason_maps(roots, senses, dimensions, links):
    root_reasons = defaultdict(set)
    sense_reasons = defaultdict(set)
    for issue in roots.issues:
        root_reasons[issue.root_id].add(issue.code)
    for issue in senses.issues:
        for source_id in issue.source_sense_ids:
            sense_reasons[source_id].add(issue.code)
    for issue in dimensions.issues:
        for source_id in issue.source_sense_ids:
            sense_reasons[source_id].add(issue.code)
    for issue in links.issues:
        for source_id in issue.source_sense_ids:
            sense_reasons[source_id].add(issue.code)
    return root_reasons, sense_reasons


def _complete_graph(roots, senses, dimensions, links, complete_sense_ids: set[str]) -> Graph:
    """Merge layers while excluding incomplete sense subjects and their private loci."""
    graph = Graph()
    for triple in roots.graph:
        graph.add(triple)

    complete_iris = {
        record.identity.iri
        for record in senses.records
        if set(record.source_sense_ids) <= complete_sense_ids
    }
    incomplete_iris = {
        record.identity.iri for record in senses.records if record.identity.iri not in complete_iris
    }
    complete_loci = {
        obj for iri in complete_iris
        for obj in senses.graph.objects(URIRef(iri), DCTERMS.source)
    }
    incomplete_loci = {
        obj for iri in incomplete_iris
        for obj in senses.graph.objects(URIRef(iri), DCTERMS.source)
    } - complete_loci
    for subject, predicate, obj in senses.graph:
        if str(subject) in incomplete_iris or str(obj) in incomplete_iris or subject in incomplete_loci:
            continue
        graph.add((subject, predicate, obj))
    for source in (dimensions.graph, links.graph):
        for subject, predicate, obj in source:
            if str(subject) in incomplete_iris or str(obj) in incomplete_iris:
                continue
            graph.add((subject, predicate, obj))
    return graph


def reconcile_lexicon_closure(
    closure: CompilerClosure,
    *,
    source_csv_root: str | Path,
    relation_profile_path: str | Path,
    negative_fixture_path: str | Path,
) -> LexiconReconciliation:
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)
    roots = project_lexicon_roots(closure)
    senses = project_lexicon_senses(closure)
    dimensions = project_lexicon_dimensions(closure, senses)
    term = load_root_sense_term(
        relation_profile_path,
        source_csv_root=source_csv_root,
        negative_fixture_path=negative_fixture_path,
    )
    links = project_root_sense_links(
        closure, term, roots=roots, senses=senses, dimensions=dimensions
    )

    root_rows = tuple(closure.table("lexicon_roots").rows)
    sense_rows = tuple(closure.table("lexicon_root_senses").rows)
    all_root_ids = {row["lexicon_root_id"] for row in root_rows}
    all_sense_ids = {row["lexicon_sense_id"] for row in sense_rows}
    emitted_roots, held_roots = set(roots.emitted_ids), set(roots.held_ids)
    emitted_senses = set(links.linked_sense_ids)
    held_senses = all_sense_ids - emitted_senses
    validate_dispositions(all_root_ids, emitted_roots, held_roots, domain="root")
    validate_dispositions(all_sense_ids, emitted_senses, held_senses, domain="sense")

    root_reasons, sense_reasons = _reason_maps(roots, senses, dimensions, links)
    for root_id in held_roots:
        if not root_reasons[root_id]:
            raise ProfileError("LEXICON_HELD_REASON_MISSING", "root", root_id)
    for source_id in held_senses:
        if not sense_reasons[source_id]:
            raise ProfileError("LEXICON_HELD_REASON_MISSING", "sense", source_id)

    graph = _complete_graph(roots, senses, dimensions, links, emitted_senses)
    canonical = canonicalize(graph)
    source_counts = Counter(row["lexicon_root_id"] for row in sense_rows)
    zero_sense = tuple(sorted(root_id for root_id in all_root_ids if source_counts[root_id] == 0))
    multi_sense = tuple(sorted(root_id for root_id, count in source_counts.items() if count > 1))
    stem_counts = Counter((row["stem"] or "ROOT-WIDE") for row in sense_rows)
    specification_counts = Counter(row["specification"] for row in sense_rows)
    locus_kind_counts = Counter(row["source_locus_kind"] for row in sense_rows)
    root_chapters = Counter(row["lexicon_chapter"] for row in root_rows)
    sense_chapters = Counter(row["lexicon_chapter"] for row in sense_rows)
    notation_count = sum(
        1 for record in roots.records
        if any(roots.graph.triples((URIRef(record.identity.iri), SKOS.notation, None)))
    )

    input_data = input_receipt(closure)
    source_tables = {
        name: input_data["tables"][name]
        for name in ("lexicon_root_evidence", "lexicon_root_senses", "lexicon_roots")
    }
    source_digest = hashlib.sha256(json_bytes(source_tables)).hexdigest()
    held_by_reason = Counter()
    for root_id in held_roots:
        held_by_reason.update(root_reasons[root_id])
    for source_id in held_senses:
        held_by_reason.update(sense_reasons[source_id])

    body = {
        "schema": SCHEMA,
        "frontier": {
            "scope": FRONTIER,
            "source_id": "NI-LEXICON-CURRICULUM",
            "included_chapters": ["1", "2"],
            "outside_closure": list(OUTSIDE_CLOSURE),
            "claim": "current tracked Chapter 1-2 source frontier only; not complete official lexicon coverage",
        },
        "counts": {
            "root_rows_consumed": len(root_rows),
            "root_resources_emitted": len(emitted_roots),
            "root_resources_held": len(held_roots),
            "sense_rows_consumed": len(sense_rows),
            "sense_concepts_emitted": len(emitted_senses),
            "sense_rows_held": len(held_senses),
            "roots_with_zero_parsed_senses": len(zero_sense),
            "roots_with_multiple_parsed_senses": len(multi_sense),
            "notation_count": notation_count,
        },
        "coverage": {
            "stem": dict(sorted(stem_counts.items())),
            "specification": dict(sorted(specification_counts.items())),
            "source_locus_kind": dict(sorted(locus_kind_counts.items())),
            "root_chapters": dict(sorted(root_chapters.items())),
            "sense_chapters": dict(sorted(sense_chapters.items())),
        },
        "debt": {
            "roots_with_zero_parsed_sense_ids": list(zero_sense),
            "held_roots": [
                {"root_id": root_id, "reasons": sorted(root_reasons[root_id])}
                for root_id in sorted(held_roots)
            ],
            "held_senses": [
                {"source_sense_id": source_id, "reasons": sorted(sense_reasons[source_id])}
                for source_id in sorted(held_senses)
            ],
            "held_by_reason": dict(sorted(held_by_reason.items())),
        },
        "source": {
            "normalization": input_data["normalization"],
            "compiler_input_closure_sha256": input_data["sha256"],
            "lexicon_tables": source_tables,
            "lexicon_source_sha256": source_digest,
        },
        "canonical_rdf": canonical.metadata(),
    }
    receipt = {
        **body,
        "receipt_sha256": hashlib.sha256(json_bytes(body)).hexdigest(),
    }
    return LexiconReconciliation(graph, canonical, receipt)


def reconcile_lexicon_frontier(
    input_root: str | Path,
    *,
    relation_profile_path: str | Path,
    negative_fixture_path: str | Path,
) -> LexiconReconciliation:
    closure = preflight(input_root).require_valid()
    return reconcile_lexicon_closure(
        closure,
        source_csv_root=input_root,
        relation_profile_path=relation_profile_path,
        negative_fixture_path=negative_fixture_path,
    )


def reconciliation_json_bytes(result: LexiconReconciliation) -> bytes:
    if not isinstance(result, LexiconReconciliation):
        raise ProfileError("LEXICON_RECONCILIATION_REQUIRED", type(result).__name__)
    return json_bytes(result.receipt)
