"""Lexicon root-domain projection over the merged #38/#39/#40 compiler corridor."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from rdflib import Graph

from .builder import BuildIssue, build_core_graph
from .errors import ProfileError
from .identity import Identity
from .preflight import CompilerClosure
from .resolver import RecordRef, ResolvedResource, resolve_identities
from .source import SourceProjector


@dataclass(frozen=True, order=True)
class LexiconRootIssue:
    code: str
    root_id: str
    record_refs: tuple[RecordRef, ...]
    details: tuple[str, ...] = ()


@dataclass(frozen=True, order=True)
class LexiconRootRecord:
    identity: Identity
    source_root_id: str
    raw_notation: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class LexiconRootProjection:
    graph: Graph
    records: tuple[LexiconRootRecord, ...]
    emitted_ids: tuple[str, ...]
    held_ids: tuple[str, ...]
    issues: tuple[LexiconRootIssue, ...]


def _root_id(resource: ResolvedResource) -> str | None:
    if resource.role != "root" or resource.identity.kind != "root":
        return None
    if not any(ref.table == "lexicon_roots" for ref in resource.source_records):
        return None
    return resource.identity.keys[1]


def _build_issue(problem: BuildIssue, iri_to_id: dict[str, str]) -> LexiconRootIssue | None:
    root_id = iri_to_id.get(problem.resource_iri)
    if root_id is None:
        return None
    return LexiconRootIssue(problem.code, root_id, problem.record_refs, problem.details)


def project_lexicon_roots(closure: CompilerClosure) -> LexiconRootProjection:
    """Project only current lexicon root resources through the existing compiler stages.

    `lexicon_root_evidence` remains supporting IR. It is checked here for stable-root
    form consistency and exposed in the result records, but its prose is not promoted
    into root semantics or extra RDF assertions.
    """
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)

    root_rows = {row["lexicon_root_id"]: row for row in closure.table("lexicon_roots").rows}
    evidence = defaultdict(list)
    issues: list[LexiconRootIssue] = []
    invalid: set[str] = set()
    for row in closure.table("lexicon_root_evidence").rows:
        root_id = row["lexicon_root_id"]
        evidence[root_id].append(row)
        root = root_rows.get(root_id)
        ref = RecordRef("lexicon_root_evidence", row["lexicon_evidence_id"])
        if root is None:
            invalid.add(root_id)
            issues.append(LexiconRootIssue("LEXICON_EVIDENCE_ROOT_NOT_FOUND", root_id, (ref,)))
        elif row["root_form_raw"] != root["root_form_raw"]:
            invalid.add(root_id)
            issues.append(LexiconRootIssue(
                "LEXICON_ROOT_FORM_CONFLICT", root_id,
                (RecordRef("lexicon_roots", root_id), ref),
                (f"root={root['root_form_raw']!r}", f"evidence={row['root_form_raw']!r}"),
            ))

    resolution = resolve_identities(closure)
    root_resources = []
    iri_to_id = {}
    for resource in resolution.resources:
        root_id = _root_id(resource)
        if root_id is None:
            continue
        iri_to_id[resource.identity.iri] = root_id
        if root_id not in invalid:
            root_resources.append(resource)
    for problem in resolution.issues:
        refs = tuple(ref for ref in problem.record_refs if ref.table == "lexicon_roots")
        if not refs:
            continue
        root_id = refs[0].key
        invalid.add(root_id)
        issues.append(LexiconRootIssue(problem.code, root_id, problem.record_refs, problem.details))

    built = build_core_graph(root_resources, SourceProjector(closure))
    for problem in built.issues:
        converted = _build_issue(problem, iri_to_id)
        if converted is not None:
            invalid.add(converted.root_id)
            issues.append(converted)

    emitted_resources = {
        resource.identity.keys[1]: resource
        for resource in built.emitted
        if _root_id(resource) is not None
    }
    records = []
    for root_id, resource in sorted(emitted_resources.items()):
        row = root_rows[root_id]
        records.append(LexiconRootRecord(
            resource.identity,
            root_id,
            row["root_form_raw"],
            tuple(sorted(item["lexicon_evidence_id"] for item in evidence.get(root_id, ()))),
        ))
    all_ids = set(root_rows)
    emitted_ids = tuple(sorted(emitted_resources))
    held_ids = tuple(sorted(all_ids - set(emitted_ids)))
    return LexiconRootProjection(
        built.graph,
        tuple(records),
        emitted_ids,
        held_ids,
        tuple(sorted(set(issues))),
    )
