"""Stable lexicon sense concepts over the merged resolver/source/builder corridor."""

from __future__ import annotations

from dataclasses import dataclass

from rdflib import Graph

from .builder import BuildIssue, build_core_graph
from .errors import ProfileError
from .identity import Identity
from .preflight import CompilerClosure
from .resolver import RecordRef, ResolvedResource, resolve_identities
from .source import SourceProjector


@dataclass(frozen=True, order=True)
class LexiconSenseIssue:
    code: str
    source_sense_ids: tuple[str, ...]
    record_refs: tuple[RecordRef, ...]
    details: tuple[str, ...] = ()


@dataclass(frozen=True, order=True)
class LexiconSenseRecord:
    identity: Identity
    parent_root: Identity
    source_sense_ids: tuple[str, ...]
    raw_stems: tuple[str, ...]
    canonical_stem: str
    specification: str
    evidence_statuses: tuple[str, ...]
    source_locus_kinds: tuple[str, ...]


@dataclass(frozen=True)
class LexiconSenseProjection:
    graph: Graph
    records: tuple[LexiconSenseRecord, ...]
    emitted_source_ids: tuple[str, ...]
    held_source_ids: tuple[str, ...]
    issues: tuple[LexiconSenseIssue, ...]


def _is_lexicon_sense(resource: ResolvedResource) -> bool:
    return (
        resource.role == "concept"
        and resource.identity.kind == "sense"
        and any(ref.table == "lexicon_root_senses" for ref in resource.source_records)
    )


def _ids(refs: tuple[RecordRef, ...]) -> tuple[str, ...]:
    return tuple(sorted(ref.key for ref in refs if ref.table == "lexicon_root_senses"))


def _build_issue(problem: BuildIssue, by_iri: dict[str, tuple[str, ...]]) -> LexiconSenseIssue | None:
    source_ids = by_iri.get(problem.resource_iri)
    if source_ids is None:
        return None
    return LexiconSenseIssue(problem.code, source_ids, problem.record_refs, problem.details)


def project_lexicon_senses(closure: CompilerClosure) -> LexiconSenseProjection:
    """Project one SKOS concept per stable source/root/stem/specification coordinate."""
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)

    rows = {row["lexicon_sense_id"]: row for row in closure.table("lexicon_root_senses").rows}
    resolution = resolve_identities(closure)
    resources = tuple(resource for resource in resolution.resources if _is_lexicon_sense(resource))
    by_iri = {resource.identity.iri: _ids(resource.source_records) for resource in resources}
    issues: list[LexiconSenseIssue] = []
    held = set()
    for problem in resolution.issues:
        refs = tuple(ref for ref in problem.record_refs if ref.table == "lexicon_root_senses")
        if not refs:
            continue
        source_ids = _ids(problem.record_refs)
        held.update(source_ids)
        issues.append(LexiconSenseIssue(problem.code, source_ids, problem.record_refs, problem.details))

    built = build_core_graph(resources, SourceProjector(closure))
    for problem in built.issues:
        converted = _build_issue(problem, by_iri)
        if converted is None:
            continue
        held.update(converted.source_sense_ids)
        issues.append(converted)

    records = []
    emitted_ids = set()
    for resource in sorted((item for item in built.emitted if _is_lexicon_sense(item)),
                           key=lambda item: item.identity.iri):
        source_ids = _ids(resource.source_records)
        source_rows = [rows[source_id] for source_id in source_ids]
        raw_stems = {row["stem"] for row in source_rows}
        canonical_stems = {(row["stem"] or "ROOT-WIDE").upper() for row in source_rows}
        specifications = {row["specification"].upper() for row in source_rows}
        if canonical_stems != {resource.identity.keys[2]} or specifications != {resource.identity.keys[3]}:
            held.update(source_ids)
            issues.append(LexiconSenseIssue(
                "LEXICON_SENSE_COORDINATE_CONFLICT", source_ids, resource.source_records,
                tuple(sorted([*(f"stem={value!r}" for value in raw_stems),
                              *(f"specification={value!r}" for value in specifications)])),
            ))
            continue
        records.append(LexiconSenseRecord(
            resource.identity,
            Identity("root", resource.identity.keys[:2]),
            source_ids,
            tuple(sorted(raw_stems)),
            resource.identity.keys[2],
            resource.identity.keys[3],
            tuple(sorted({row["evidence_status"] for row in source_rows})),
            tuple(sorted({row["source_locus_kind"] for row in source_rows})),
        ))
        emitted_ids.update(source_ids)

    # A post-build metadata conflict must not leave partial semantic RDF.
    rejected_iris = {
        resource.identity.iri for resource in built.emitted if set(_ids(resource.source_records)) & held
    }
    if rejected_iris:
        graph = Graph()
        for triple in built.graph:
            if str(triple[0]) not in rejected_iris and str(triple[2]) not in rejected_iris:
                graph.add(triple)
        records = [record for record in records if record.identity.iri not in rejected_iris]
        emitted_ids -= held
    else:
        graph = built.graph

    all_ids = set(rows)
    return LexiconSenseProjection(
        graph,
        tuple(records),
        tuple(sorted(emitted_ids)),
        tuple(sorted(all_ids - emitted_ids)),
        tuple(sorted(set(issues))),
    )
