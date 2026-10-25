"""Deterministic core SKOS graph assembly for issue #40."""
from __future__ import annotations
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, SKOS
from .errors import ProfileError
from .identity import Identity
from .collision import HomographAdmission, resolve_homograph_admissions
from .notation import (GRAMMAR_CODE_DATATYPE_IRI, NEW_ITHKUIL_DATATYPE_IRI,
                       NotationClaim, analyze_notation_claims, typed_notation)
from .resolver import NEW_ITHKUIL, RecordRef, ResolvedResource, TextAssertion
from .shapes import (CollectionShape, ConceptShape, OrderedCollectionShape,
                     RootResourceShape, SchemeShape, build_shape_graph)
from .source import SourceProjector
from .text import TextAssertion as ProfileTextAssertion
from .text import project_text
@dataclass(frozen=True, order=True)
class BuildIssue:
    code: str
    resource_iri: str
    record_refs: tuple[RecordRef, ...]
    details: tuple[str, ...]
@dataclass(frozen=True)
class BuildResult:
    graph: Graph
    emitted: tuple[ResolvedResource, ...]
    issues: tuple[BuildIssue, ...]
@dataclass(frozen=True)
class _Prepared:
    resource: ResolvedResource
    graph: Graph
    notation_claims: tuple[NotationClaim, ...]
def _semantic_issue(code: str, resource: ResolvedResource, *details: str) -> BuildIssue:
    return BuildIssue(code, resource.identity.iri, tuple(sorted(set(resource.source_records))),
                      tuple(sorted(details)))
def _group_issue(code: str, identity: Identity, members: Iterable[_Prepared], *details: str) -> BuildIssue:
    member_rows = tuple(sorted(members, key=lambda item: item.resource.identity.iri))
    navigation = tuple(
        f"source_ref={ref.table}:{ref.key}"
        for item in member_rows
        for ref in sorted(set(item.resource.source_records))
    )
    member_details = tuple(f"member={item.resource.identity.iri}" for item in member_rows)
    return BuildIssue(code, identity.iri, (), tuple(sorted((*details, *member_details, *navigation))))
def _merge(target: Graph, source: Graph) -> None:
    for triple in source:
        target.add(triple)
def _validate_resource_shape(resource: ResolvedResource) -> None:
    if resource.role == "concept":
        ConceptShape(resource.identity, resource.schemes)
        for family in resource.families:
            Identity("collection", (family,))
        return
    if resource.role == "root":
        RootResourceShape(resource.identity)
        return
    raise ProfileError("UNKNOWN_RESOLVED_RESOURCE_ROLE", resource.role, resource.identity.iri)
def _profile_text(resource: ResolvedResource, assertion: TextAssertion) -> ProfileTextAssertion | None:
    if assertion.record_ref not in resource.source_records:
        raise ProfileError("TEXT_SOURCE_REF_NOT_RESOURCE", resource.identity.iri,
                           f"{assertion.record_ref.table}:{assertion.record_ref.key}")
    if assertion.role == "source_notation_raw":
        if assertion.field not in {"surface_form_raw", "root_form_raw"} or assertion.scope != "realization":
            raise ProfileError("RAW_NOTATION_ASSERTION_SHAPE_INVALID", assertion.field,
                               assertion.scope)
        if assertion.language is not None:
            raise ProfileError("RAW_NOTATION_LANGUAGE_FORBIDDEN", assertion.language)
        return None
    role_shape = {
        "source_pref_label": ({"value_name", "root_gloss"}, "resource", None, None),
        "identity_definition": ({"sense_summary"}, "resource", None, None),
        "source_note": ({"semantic_summary"}, "realization", "semantic_summary", "realization"),
        "source_excerpt": ({"source_example_excerpt"}, "resource", "example", None),
    }
    spec = role_shape.get(assertion.role)
    if spec is None:
        raise ProfileError("UNSUPPORTED_TEXT_ASSERTION_ROLE", assertion.role, assertion.field)
    fields, expected_scope, replacement_field, profile_scope = spec
    if assertion.field not in fields or assertion.scope != expected_scope:
        raise ProfileError("TEXT_ASSERTION_SHAPE_INVALID", assertion.role,
                           assertion.field, assertion.scope)
    return ProfileTextAssertion(
        resource=resource.identity.iri,
        field=replacement_field or assertion.field,
        value=assertion.text,
        language=assertion.language,
        source_ref=f"{assertion.record_ref.table}:{assertion.record_ref.key}",
        scope=profile_scope,
    )
def _notation_graph_and_claims(resource: ResolvedResource) -> tuple[Graph, tuple[NotationClaim, ...]]:
    graph = Graph()
    literals = []
    for assertion in resource.texts:
        if assertion.role != "source_notation_raw":
            continue
        if assertion.record_ref not in resource.source_records:
            raise ProfileError("NOTATION_SOURCE_REF_NOT_RESOURCE",
                               f"{assertion.record_ref.table}:{assertion.record_ref.key}")
        if assertion.field not in {"surface_form_raw", "root_form_raw"} or assertion.scope != "realization":
            raise ProfileError("RAW_NOTATION_ASSERTION_SHAPE_INVALID", assertion.field,
                               assertion.scope)
        if assertion.language is not None:
            raise ProfileError("RAW_NOTATION_LANGUAGE_FORBIDDEN", assertion.language)
        literals.append(typed_notation(assertion.text, NEW_ITHKUIL_DATATYPE_IRI))
    if resource.identity.kind == "grammar":
        literals.append(typed_notation(resource.identity.keys[1], GRAMMAR_CODE_DATATYPE_IRI))
    subject = URIRef(resource.identity.iri)
    for literal in literals:
        graph.add((subject, SKOS.notation, literal))
    governing_schemes = resource.schemes if resource.role == "concept" else (NEW_ITHKUIL,)
    claims = tuple(
        NotationClaim(scheme.iri, resource.identity.iri, literal)
        for scheme in governing_schemes
        for literal in sorted(set(literals), key=lambda value: value.n3())
    )
    return graph, claims
def _prepare_resource(resource: ResolvedResource, source_projector: SourceProjector) -> tuple[_Prepared | None, tuple[BuildIssue, ...]]:
    issues: list[BuildIssue] = []
    try:
        _validate_resource_shape(resource)
    except ProfileError as error:
        issues.append(_semantic_issue(error.code, resource, *map(str, error.details)))
    if not resource.source_records:
        issues.append(_semantic_issue("RESOURCE_SOURCE_RECORD_REQUIRED", resource))
    text_graph = Graph()
    notation_graph = Graph()
    claims: tuple[NotationClaim, ...] = ()
    try:
        profile_assertions = tuple(
            item
            for item in (_profile_text(resource, assertion) for assertion in resource.texts)
            if item is not None
        )
        text_graph = project_text(profile_assertions)
    except ProfileError as error:
        issues.append(_semantic_issue(error.code, resource, *map(str, error.details)))
    try:
        notation_graph, claims = _notation_graph_and_claims(resource)
    except ProfileError as error:
        issues.append(_semantic_issue(error.code, resource, *map(str, error.details)))
    projection = source_projector.project_resource(resource.identity, resource.source_records)
    for problem in projection.issues:
        implicated = tuple(f"source_ref={ref.table}:{ref.key}" for ref in problem.record_refs)
        issues.append(_semantic_issue(problem.code, resource, *problem.details, *implicated))
    if projection.held and not projection.issues:
        held = tuple(f"source_ref={ref.table}:{ref.key}" for ref in projection.held)
        issues.append(_semantic_issue("SOURCE_PROJECTION_HELD", resource, *held))
    if not projection.issues and not projection.held:
        subject = URIRef(resource.identity.iri)
        if not any(projection.source_graph.triples((subject, DCTERMS.source, None))):
            issues.append(_semantic_issue("NO_PUBLIC_SOURCE_LOCUS", resource))
    if issues:
        return None, tuple(sorted(set(issues)))
    graph = Graph()
    _merge(graph, text_graph)
    _merge(graph, notation_graph)
    _merge(graph, projection.source_graph)
    return _Prepared(resource, graph, claims), ()
def _project_group(identity: Identity, members: tuple[_Prepared, ...],
                   source_projector: SourceProjector) -> tuple[Graph | None, tuple[BuildIssue, ...]]:
    refs = tuple(sorted({ref for item in members for ref in item.resource.source_records}))
    projection = source_projector.project_group(identity, refs)
    issues: list[BuildIssue] = []
    for problem in projection.issues:
        implicated = tuple(f"source_ref={ref.table}:{ref.key}" for ref in problem.record_refs)
        issues.append(_group_issue(problem.code, identity, members, *problem.details, *implicated))
    if projection.held and not projection.issues:
        held = tuple(f"source_ref={ref.table}:{ref.key}" for ref in projection.held)
        issues.append(_group_issue("SOURCE_PROJECTION_HELD", identity, members, *held))
    if not projection.issues and not projection.held:
        if not any(projection.source_graph.triples((URIRef(identity.iri), DCTERMS.source, None))):
            issues.append(_group_issue("NO_PUBLIC_SOURCE_LOCUS", identity, members))
    if issues:
        return None, tuple(sorted(set(issues)))
    return projection.source_graph, ()
def _deduplicate_resources(resources: Iterable[ResolvedResource]) -> tuple[tuple[ResolvedResource, ...], tuple[BuildIssue, ...]]:
    grouped: dict[str, list[ResolvedResource]] = defaultdict(list)
    for resource in resources:
        if not isinstance(resource, ResolvedResource):
            raise ProfileError("RESOLVED_RESOURCE_REQUIRED", type(resource).__name__)
        grouped[resource.identity.iri].append(resource)
    kept = []
    issues = []
    for iri, group in sorted(grouped.items()):
        distinct = set(group)
        if len(distinct) == 1:
            kept.append(next(iter(distinct)))
            continue
        refs = tuple(sorted({ref for item in group for ref in item.source_records}))
        issues.append(BuildIssue("RESOURCE_IDENTITY_REDEFINED", iri, refs, (f"variants={len(distinct)}",)))
    return tuple(kept), tuple(issues)
def build_core_graph(resources: Iterable[ResolvedResource], source_projector: SourceProjector, *,
                     ordered_collections: Iterable[OrderedCollectionShape] = (),
                     notation_admissions: Iterable[HomographAdmission] = ()) -> BuildResult:
    """Build the complete strong core graph; held resources emit no partial RDF."""
    unique, initial_issues = _deduplicate_resources(resources)
    issues = set(initial_issues)
    prepared: dict[str, _Prepared] = {}
    for resource in sorted(unique, key=lambda item: item.identity.iri):
        item, resource_issues = _prepare_resource(resource, source_projector)
        issues.update(resource_issues)
        if item is not None:
            prepared[resource.identity.iri] = item
    notation_report = analyze_notation_claims(
        claim for item in prepared.values() for claim in item.notation_claims
    )
    admitted, admission_issues = resolve_homograph_admissions(
        notation_report.collisions, tuple(notation_admissions)
    )
    if admission_issues:
        issue = admission_issues[0]
        raise ProfileError(issue.code, issue.rule_id, *issue.details)
    collision_iris = set()
    for conflict in notation_report.collisions:
        if conflict.key in admitted:
            continue
        details = (
            f"scheme={conflict.key.scheme_iri}",
            f"datatype={conflict.key.datatype_iri}",
            f"lexical={conflict.key.lexical!r}",
            *(f"resource={iri}" for iri in conflict.resource_iris),
        )
        for iri in conflict.resource_iris:
            item = prepared.get(iri)
            if item is not None:
                issues.add(_semantic_issue("NOTATION_COLLISION", item.resource, *details))
                collision_iris.add(iri)
    for iri in collision_iris:
        prepared.pop(iri, None)
    scheme_graphs: dict[Identity, Graph] = {}
    while True:
        scheme_members: dict[Identity, list[_Prepared]] = defaultdict(list)
        for item in prepared.values():
            if item.resource.role == "concept":
                for scheme in item.resource.schemes:
                    scheme_members[scheme].append(item)
        failed_schemes = set()
        candidate_graphs = {}
        for scheme, members in sorted(scheme_members.items(), key=lambda pair: pair[0].iri):
            ordered = tuple(sorted(members, key=lambda item: item.resource.identity.iri))
            graph, group_issues = _project_group(scheme, ordered, source_projector)
            issues.update(group_issues)
            if graph is None:
                failed_schemes.add(scheme)
            else:
                candidate_graphs[scheme] = graph
        if not failed_schemes:
            scheme_graphs = candidate_graphs
            break
        doomed = [
            item for item in prepared.values()
            if any(scheme in failed_schemes for scheme in item.resource.schemes)
        ]
        if not doomed:
            scheme_graphs = candidate_graphs
            break
        for item in doomed:
            blocked = tuple(
                f"scheme={scheme.iri}" for scheme in item.resource.schemes if scheme in failed_schemes
            )
            issues.add(_semantic_issue("SCHEME_SOURCE_BLOCKED", item.resource, *blocked))
            prepared.pop(item.resource.identity.iri, None)
    family_members: dict[str, list[_Prepared]] = defaultdict(list)
    for item in prepared.values():
        if item.resource.role == "concept":
            for family in item.resource.families:
                family_members[family].append(item)
    collection_shapes = []
    group_graphs = []
    for family, members in sorted(family_members.items()):
        identity = Identity("collection", (family,))
        ordered = tuple(sorted(members, key=lambda item: item.resource.identity.iri))
        graph, group_issues = _project_group(identity, ordered, source_projector)
        issues.update(group_issues)
        if graph is None:
            continue
        collection_shapes.append(CollectionShape(identity, tuple(item.resource.identity for item in ordered)))
        group_graphs.append(graph)
    ordered_shapes = []
    seen_ordered: dict[str, OrderedCollectionShape] = {}
    rejected_ordered = set()
    for shape in ordered_collections:
        if not isinstance(shape, OrderedCollectionShape):
            raise ProfileError("ORDERED_COLLECTION_SHAPE_REQUIRED", type(shape).__name__)
        prior = seen_ordered.get(shape.identity.iri)
        if prior is not None and prior != shape:
            variants = sorted({tuple(item.iri for item in prior.members),
                               tuple(item.iri for item in shape.members)})
            issues.add(BuildIssue("ORDERED_COLLECTION_REDEFINED", shape.identity.iri, (),
                                  tuple(f"members={members!r}" for members in variants)))
            rejected_ordered.add(shape.identity.iri)
        else:
            seen_ordered[shape.identity.iri] = shape
    for iri, shape in sorted(seen_ordered.items()):
        if iri in rejected_ordered:
            continue
        missing = tuple(member for member in shape.members if member.iri not in prepared)
        if missing:
            issues.add(BuildIssue("ORDERED_COLLECTION_MEMBER_NOT_EMITTED", shape.identity.iri, (),
                                  tuple(f"member={member.iri}" for member in missing)))
            continue
        members = tuple(prepared[member.iri] for member in shape.members)
        graph, group_issues = _project_group(shape.identity, members, source_projector)
        issues.update(group_issues)
        if graph is None:
            continue
        ordered_shapes.append(shape)
        group_graphs.append(graph)
    shapes = [SchemeShape(scheme) for scheme in sorted(scheme_graphs, key=lambda item: item.iri)]
    for item in sorted(prepared.values(), key=lambda value: value.resource.identity.iri):
        if item.resource.role == "concept":
            shapes.append(ConceptShape(item.resource.identity, item.resource.schemes))
        else:
            shapes.append(RootResourceShape(item.resource.identity))
    shapes.extend(collection_shapes)
    shapes.extend(ordered_shapes)
    graph = build_shape_graph(shapes)
    for item in sorted(prepared.values(), key=lambda value: value.resource.identity.iri):
        _merge(graph, item.graph)
    for scheme in sorted(scheme_graphs, key=lambda item: item.iri):
        _merge(graph, scheme_graphs[scheme])
    for group_graph in group_graphs:
        _merge(graph, group_graph)
    emitted = tuple(
        item.resource for item in sorted(prepared.values(), key=lambda value: value.resource.identity.iri)
    )
    return BuildResult(graph, emitted, tuple(sorted(issues)))
