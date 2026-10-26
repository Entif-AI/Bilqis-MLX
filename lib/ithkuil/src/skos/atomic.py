"""Generic full atomic-morphology compiler pass for issue #48."""
from __future__ import annotations
from dataclasses import dataclass
import json
from rdflib import Graph, URIRef

from .builder import BuildIssue, BuildResult, build_core_graph
from .collision import AtomicCollisionReport, HomographAdmission, analyze_atomic_collisions, collision_resolution
from .definition import DefinitionNormalization, definition_graph, normalize_atomic_definitions
from .errors import ProfileError
from .identity import Identity
from .preflight import CompilerClosure
from .realization import RealizationNormalization, normalize_atomic_realizations
from .resolver import (GRAMMAR_ATOM_CLASSES, ROOT_ATOM_CLASSES, RecordRef, Resolution,
                       ResolutionIssue, resolve_identities)
from .source import SourceProjector

@dataclass(frozen=True, order=True)
class AtomicRowOutcome:
    atomic_id: str
    category_code: str
    status: str
    reason_codes: tuple[str, ...]
    semantic_iri: str

@dataclass(frozen=True, order=True)
class AtomicCategoryOutcome:
    category_code: str
    source_rows: int
    emitted_rows: int
    held_rows: int
    rejected_rows: int

@dataclass(frozen=True)
class AtomicCompileResult:
    graph: Graph
    build: BuildResult
    resolution: Resolution
    realizations: RealizationNormalization
    definitions: DefinitionNormalization
    collisions: AtomicCollisionReport
    row_outcomes: tuple[AtomicRowOutcome, ...]
    categories: tuple[AtomicCategoryOutcome, ...]
    @property
    def release_eligible(self):
        return not any(r.status != "EMITTED" for r in self.row_outcomes) and self.collisions.release_eligible
    def as_dict(self):
        return {"schema":"bilqis.skos.atomic-compile/v1","release_eligible":self.release_eligible,
                "source_rows":len(self.row_outcomes),"category_count":len(self.categories),
                "emitted_resources":len(self.build.emitted),"graph_triples":len(self.graph),
                "rows":{"EMITTED":sum(r.status=='EMITTED' for r in self.row_outcomes),
                        "HELD":sum(r.status=='HELD' for r in self.row_outcomes),
                        "REJECTED":sum(r.status=='REJECTED' for r in self.row_outcomes)},
                "categories":[c.__dict__ for c in self.categories]}

def _atomic_resources(resolution):
    return tuple(r for r in resolution.resources if any(x.table=="morphemes_atomic" for x in r.source_records))

def _resolution_with_realization_issues(resolution, normalization):
    if not normalization.issues: return resolution, normalization
    refs={ref for issue in normalization.issues for ref in issue.record_refs}
    issues=list(resolution.issues)
    for issue in normalization.issues:
        issues.append(ResolutionIssue(issue.code,issue.semantic_key,issue.record_refs,issue.details))
    resources=tuple(r for r in resolution.resources if not any(ref in refs for ref in r.source_records))
    clean=RealizationNormalization(tuple(g for g in normalization.groups if not any(ref in refs for ref in g.source_records)),(),normalization.source_row_count)
    return Resolution(resources,tuple(sorted(set(issues)))),clean

def _attempted_iri(row):
    cls=row.get("morpheme_class")
    try:
        if cls in GRAMMAR_ATOM_CLASSES and row.get("category_code") and row.get("value_code"):
            return Identity("grammar",(row.get("category_code"),row.get("value_code"))).iri
        if cls in ROOT_ATOM_CLASSES and row.get("primary_source_id") and row.get("atomic_id"):
            return Identity("root",(row.get("primary_source_id"),row.get("atomic_id"))).iri
    except ProfileError: pass
    return ""

def compile_atomic(closure: CompilerClosure, resolution: Resolution | None=None,
                   admissions: tuple[HomographAdmission,...]=()) -> AtomicCompileResult:
    base=resolution or resolve_identities(closure)
    realizations=normalize_atomic_realizations(closure,base)
    realized_resolution,clean_realizations=_resolution_with_realization_issues(base,realizations)
    definitions=normalize_atomic_definitions(closure,realized_resolution,clean_realizations)
    collisions=analyze_atomic_collisions(closure,definitions.resolution,admissions)
    final_resolution=collision_resolution(definitions.resolution,collisions)
    build=build_core_graph(
        _atomic_resources(final_resolution), SourceProjector(closure),
        notation_admissions=admissions,
    )
    graph=Graph()
    for triple in build.graph: graph.add(triple)
    emitted_iris={r.identity.iri for r in build.emitted}
    for triple in definition_graph(definitions):
        if str(triple[0]) in emitted_iris: graph.add(triple)

    emitted_refs={ref for r in build.emitted for ref in r.source_records if ref.table=="morphemes_atomic"}
    held: dict[RecordRef,set[str]]={}
    for issue in final_resolution.issues:
        for ref in issue.record_refs:
            if ref.table=="morphemes_atomic": held.setdefault(ref,set()).add(issue.code)
    for issue in build.issues:
        for ref in issue.record_refs:
            if ref.table=="morphemes_atomic": held.setdefault(ref,set()).add(issue.code)
    rows=[]
    source_rows=closure.table("morphemes_atomic").rows
    for row in source_rows:
        ref=RecordRef("morphemes_atomic",row.get("atomic_id"))
        if ref in emitted_refs and ref not in held: status,reasons="EMITTED",("EMITTED_ATOMIC_SKOS",)
        elif ref in held: status,reasons="HELD",tuple(sorted(held[ref]))
        else: status,reasons="REJECTED",("ATOMIC_ROW_UNACCOUNTED",)
        rows.append(AtomicRowOutcome(ref.key,row.get("category_code"),status,reasons,_attempted_iri(row)))
    outcomes=tuple(sorted(rows))
    categories=[]
    for code in sorted({r.category_code for r in outcomes}):
        selected=[r for r in outcomes if r.category_code==code]
        categories.append(AtomicCategoryOutcome(code,len(selected),sum(r.status=='EMITTED' for r in selected),
                          sum(r.status=='HELD' for r in selected),sum(r.status=='REJECTED' for r in selected)))
    return AtomicCompileResult(graph,build,final_resolution,realizations,definitions,collisions,outcomes,tuple(categories))

def atomic_report_json_bytes(result: AtomicCompileResult) -> bytes:
    return (json.dumps(result.as_dict(),ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
