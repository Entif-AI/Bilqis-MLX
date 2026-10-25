"""Compose domain reconciliation artifacts into the #67 coverage receipt (#68)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from rdflib import Graph

from .atomic import AtomicCompileResult
from .atomic_reconcile import AtomicReconciliation
from .canonical import CanonicalRdf, canonicalize
from .coverage_domains import (
    ZERO_SEMANTICS,
    atomic_domain,
    lexicon_domain,
    mapping_domain,
    residue_domain,
)
from .coverage_schema import STATUSES, coverage_receipt_json_bytes, validate_coverage_receipt
from .errors import ProfileError
from .lexicon_reconcile import LexiconReconciliation
from .mapping_corpus import MappingCorpusResult
from .preflight import CompilerClosure
from .residue_reconcile import ResidueReconciliation


COVERAGE_COMPILER_VERSION = "bilqis-skos-coverage/1"


@dataclass(frozen=True)
class CoverageBuild:
    graph: Graph
    canonical: CanonicalRdf
    receipt: dict


def _merge_graphs(graphs: Iterable[Graph]) -> Graph:
    graph = Graph()
    for source in graphs:
        for triple in source:
            graph.add(triple)
    return graph


def compose_coverage(
    domains: dict[str, dict],
    inputs: list[dict],
    graphs: Iterable[Graph],
    *,
    profile_version: str,
    profile_sha256: str,
    compiler_version: str = COVERAGE_COMPILER_VERSION,
    expected_canonical: CanonicalRdf | None = None,
) -> CoverageBuild:
    if not domains:
        raise ProfileError("COVERAGE_DOMAINS_REQUIRED")
    graph = _merge_graphs(graphs)
    canonical = canonicalize(graph)
    if expected_canonical is not None and (
        expected_canonical.sha256 != canonical.sha256
        or expected_canonical.payload != canonical.payload
        or expected_canonical.triple_count != canonical.triple_count
    ):
        raise ProfileError(
            "COVERAGE_CANONICAL_RDF_MISMATCH",
            f"expected={expected_canonical.sha256}",
            f"actual={canonical.sha256}",
        )
    total_dispositions = {
        status: sum(domain["dispositions"][status] for domain in domains.values())
        for status in STATUSES
    }
    total_rows = sum(domain["source_rows"] for domain in domains.values())
    conflicts = Counter()
    for domain in domains.values():
        for row in domain["rows"]:
            if row["status"] in {"HELD", "REJECTED", "UNSUPPORTED"}:
                conflicts[row["reason_code"]] += 1
    debt_count = sum(
        item["count"]
        for domain in domains.values()
        for item in domain["frontier_debt"]
    )
    blocking = sum(
        item["count"]
        for domain in domains.values()
        for item in domain["frontier_debt"]
        if item["blocking"]
    )
    noncomplete = sum(total_dispositions[status] for status in ("HELD", "REJECTED", "UNSUPPORTED"))
    status = "blocked" if blocking else ("partial" if noncomplete or debt_count else "complete")
    receipt = {
        "schema": "bilqis.skos.semantic-coverage/v1",
        "compiler": {
            "version": compiler_version,
            "profile_version": profile_version,
            "profile_sha256": profile_sha256,
        },
        "inputs": sorted(inputs, key=lambda item: (item["domain"], item["artifact"])),
        "canonical_rdf": {
            "sha256": canonical.sha256,
            "triple_count": canonical.triple_count,
        },
        "domains": dict(sorted(domains.items())),
        "totals": {"source_rows": total_rows, "dispositions": total_dispositions},
        "frontier_debt_declared": True,
        "conflicts": {"blocking": blocking, "by_reason": dict(sorted(conflicts.items()))},
        "build_status": status,
    }
    validate_coverage_receipt(receipt)
    return CoverageBuild(graph, canonical, receipt)


def build_coverage(
    closure: CompilerClosure,
    *,
    atomic_compiled: AtomicCompileResult,
    atomic_reconciliation: AtomicReconciliation,
    lexicon: LexiconReconciliation,
    residue: ResidueReconciliation,
    mapping: MappingCorpusResult,
    profile_version: str,
    profile_sha256: str,
    compiler_version: str = COVERAGE_COMPILER_VERSION,
    expected_canonical: CanonicalRdf | None = None,
) -> CoverageBuild:
    domains_and_sources = (
        ("atomic",) + atomic_domain(atomic_compiled, atomic_reconciliation),
        ("lexicon",) + lexicon_domain(closure, lexicon),
        ("residue",) + residue_domain(residue),
        ("mapping",) + mapping_domain(mapping),
    )
    domains = {name: domain for name, domain, _ in domains_and_sources}
    inputs = [source for _, _, source in domains_and_sources]
    return compose_coverage(
        domains,
        inputs,
        (atomic_compiled.graph, lexicon.graph, residue.graph, mapping.graph),
        profile_version=profile_version,
        profile_sha256=profile_sha256,
        compiler_version=compiler_version,
        expected_canonical=expected_canonical,
    )


def coverage_json_bytes(build: CoverageBuild) -> bytes:
    return coverage_receipt_json_bytes(build.receipt)
