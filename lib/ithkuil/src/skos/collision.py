"""Atomic corpus notation-collision policy and report for issue #47."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
import json

from .notation import (GRAMMAR_CODE_DATATYPE_IRI, NEW_ITHKUIL_DATATYPE_IRI,
                       NotationClaim, NotationKey, analyze_notation_claims, typed_notation)
from .preflight import CompilerClosure
from .resolver import NEW_ITHKUIL, RecordRef, Resolution, ResolutionIssue, ResolvedResource

@dataclass(frozen=True, order=True)
class HomographAdmission:
    scheme_iri: str
    datatype_iri: str
    lexical: str
    resource_iris: tuple[str, ...]
    rule_id: str
    @property
    def key(self) -> NotationKey:
        return NotationKey(self.scheme_iri, self.datatype_iri, self.lexical)

@dataclass(frozen=True, order=True)
class CollisionSource:
    resource_iri: str
    record_ref: RecordRef
    source_id: str
    section_id: str
    table_id: str
    source_line: str
    source_url: str

@dataclass(frozen=True, order=True)
class CollisionRecord:
    key: NotationKey
    disposition: str
    reason_code: str
    resource_iris: tuple[str, ...]
    sources: tuple[CollisionSource, ...]
    admission_rule_id: str = ""
    def as_dict(self) -> dict:
        return {"scheme_iri":self.key.scheme_iri,"datatype_iri":self.key.datatype_iri,
                "lexical":self.key.lexical,"disposition":self.disposition,
                "reason_code":self.reason_code,"resource_iris":list(self.resource_iris),
                "admission_rule_id":self.admission_rule_id or None,
                "sources":[{"resource_iri":s.resource_iri,"table":s.record_ref.table,
                "key":s.record_ref.key,"source_id":s.source_id,"section_id":s.section_id,
                "table_id":s.table_id,"source_line":s.source_line,"source_url":s.source_url}
                for s in self.sources]}

@dataclass(frozen=True, order=True)
class AdmissionIssue:
    code: str
    rule_id: str
    details: tuple[str, ...]

@dataclass(frozen=True)
class AtomicCollisionReport:
    records: tuple[CollisionRecord, ...]
    admission_issues: tuple[AdmissionIssue, ...]
    claim_count: int
    @property
    def held(self): return tuple(r for r in self.records if r.disposition == "HELD")
    @property
    def admitted(self): return tuple(r for r in self.records if r.disposition == "ADMITTED")
    @property
    def held_resource_iris(self): return frozenset(i for r in self.held for i in r.resource_iris)
    @property
    def held_source_refs(self): return frozenset(s.record_ref for r in self.held for s in r.sources)
    @property
    def release_eligible(self): return not self.held and not self.admission_issues
    def as_dict(self) -> dict:
        return {"schema":"bilqis.skos.atomic-collision-report/v1","claim_count":self.claim_count,
                "held_collision_count":len(self.held),"admitted_homograph_count":len(self.admitted),
                "held_resource_count":len(self.held_resource_iris),"held_row_count":len(self.held_source_refs),
                "release_eligible":self.release_eligible,"records":[r.as_dict() for r in self.records],
                "admission_issues":[{"code":i.code,"rule_id":i.rule_id,"details":list(i.details)}
                for i in self.admission_issues]}

def resolve_homograph_admissions(conflicts, admissions: tuple[HomographAdmission,...]):
    """Validate exact-key, complete-claimant homograph admissions."""
    collisions={conflict.key:conflict for conflict in conflicts}; valid={}; issues=[]
    for admission in sorted(admissions):
        conflict=collisions.get(admission.key)
        if not admission.rule_id:
            issues.append(AdmissionIssue("HOMOGRAPH_ADMISSION_RULE_REQUIRED",admission.rule_id,(repr(admission.key.as_tuple()),))); continue
        if conflict is None or tuple(sorted(admission.resource_iris)) != conflict.resource_iris:
            actual=() if conflict is None else conflict.resource_iris
            issues.append(AdmissionIssue("HOMOGRAPH_ADMISSION_MISMATCH",admission.rule_id,
                        (f"key={admission.key.as_tuple()!r}",f"expected_resources={actual!r}",
                         f"admitted_resources={tuple(sorted(admission.resource_iris))!r}"))); continue
        if admission.key in valid:
            issues.append(AdmissionIssue("DUPLICATE_HOMOGRAPH_ADMISSION",admission.rule_id,
                                         (repr(admission.key.as_tuple()),))); continue
        valid[admission.key]=admission
    return valid, tuple(sorted(set(issues)))

def _atomic_resources(resolution: Resolution) -> tuple[ResolvedResource, ...]:
    return tuple(r for r in resolution.resources if any(x.table == "morphemes_atomic" for x in r.source_records))

def _claims(resources):
    claims=[]
    for resource in resources:
        schemes=resource.schemes if resource.role == "concept" else (NEW_ITHKUIL,)
        literals={typed_notation(t.text,NEW_ITHKUIL_DATATYPE_IRI)
                  for t in resource.texts if t.role == "source_notation_raw"}
        if resource.identity.kind == "grammar":
            literals.add(typed_notation(resource.identity.keys[1],GRAMMAR_CODE_DATATYPE_IRI))
        for scheme in schemes:
            for literal in sorted(literals,key=lambda x:x.n3()):
                claims.append(NotationClaim(scheme.iri,resource.identity.iri,literal))
    return tuple(claims)

def analyze_atomic_collisions(closure: CompilerClosure, resolution: Resolution,
                              admissions: tuple[HomographAdmission,...]=()) -> AtomicCollisionReport:
    resources=_atomic_resources(resolution); by_iri={r.identity.iri:r for r in resources}
    claims=_claims(resources); raw=analyze_notation_claims(claims)
    collisions={c.key:c for c in raw.collisions}
    valid, issues=resolve_homograph_admissions(raw.collisions, admissions)
    rows={RecordRef("morphemes_atomic",r.get("atomic_id")):r for r in closure.table("morphemes_atomic").rows}
    records=[]
    for conflict in raw.collisions:
        admission=valid.get(conflict.key); disposition="ADMITTED" if admission else "HELD"
        sources=[]
        for iri in conflict.resource_iris:
            resource=by_iri[iri]
            for ref in resource.source_records:
                if ref.table != "morphemes_atomic" or ref not in rows: continue
                row=rows[ref]
                sources.append(CollisionSource(iri,ref,row.get("primary_source_id"),row.get("primary_section_id"),
                    row.get("primary_table_id"),row.get("primary_source_line"),row.get("primary_source_url")))
        records.append(CollisionRecord(conflict.key,disposition,
            "EXPLICIT_HOMOGRAPH_ADMISSION" if admission else "NOTATION_COLLISION",
            conflict.resource_iris,tuple(sorted(sources)),admission.rule_id if admission else ""))
    return AtomicCollisionReport(tuple(sorted(records)),tuple(sorted(set(issues))),len(claims))

def collision_resolution(resolution: Resolution, report: AtomicCollisionReport) -> Resolution:
    held=report.held_resource_iris; by_iri={r.identity.iri:r for r in resolution.resources}
    issues=list(resolution.issues)
    for record in report.held:
        details=(f"scheme={record.key.scheme_iri}",f"datatype={record.key.datatype_iri}",
                 f"lexical={record.key.lexical!r}",*(f"resource={i}" for i in record.resource_iris))
        for iri in record.resource_iris:
            resource=by_iri[iri]
            issues.append(ResolutionIssue("NOTATION_COLLISION",resource.identity.keys,
                          tuple(sorted(resource.source_records)),tuple(sorted(details))))
    resources=tuple(r for r in resolution.resources if r.identity.iri not in held)
    return Resolution(resources,tuple(sorted(set(issues))))

def collision_report_json_bytes(report: AtomicCollisionReport) -> bytes:
    return (json.dumps(report.as_dict(),ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")
