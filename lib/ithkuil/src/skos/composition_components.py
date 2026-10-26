"""Ordered linguistic composition-component projection for issue #58."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping
from urllib.parse import quote

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS

from .errors import ProfileError
from .identity import BASE, Identity
from .preflight import CompilerClosure
from .resolver import resolve_identities
from .source_public import safe_public_literal


COMPONENT_ROLE = URIRef(Identity("term", ("componentRole",)).iri)
SLOT_LABEL = URIRef(Identity("term", ("slotLabel",)).iri)
CONDITION = URIRef(Identity("term", ("condition",)).iri)


@dataclass(frozen=True, order=True)
class ComponentIssue:
    code: str
    component_ids: tuple[str, ...]
    composition_id: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True, order=True)
class ComponentRecord:
    component_id: str
    iri: str
    composition_id: str
    position: int
    role: str
    atomic_id: str
    literal: str
    slot_label: str
    condition: str
    atomic_identity: Identity | None


@dataclass(frozen=True)
class ComponentProjection:
    graph: Graph
    records: tuple[ComponentRecord, ...]
    emitted_ids: tuple[str, ...]
    held_ids: tuple[str, ...]
    issues: tuple[ComponentIssue, ...]


def _key(value: str) -> str:
    Identity("term", (value,))
    return quote(value, safe="-._~", encoding="utf-8", errors="strict")


def component_iri(component_id: str) -> str:
    return BASE + "id/composition-component/" + _key(component_id)


def _atomic_identity_map(closure: CompilerClosure) -> dict[str, Identity]:
    by_atomic = defaultdict(set)
    for resource in resolve_identities(closure).resources:
        for ref in resource.source_records:
            if ref.table == "morphemes_atomic":
                by_atomic[ref.key].add(resource.identity)
    return {
        atomic_id: next(iter(identities))
        for atomic_id, identities in by_atomic.items()
        if len(identities) == 1
    }


def project_composition_components(
    closure: CompilerClosure,
    component_rows: Iterable[Mapping[str, str]],
    compositions,
) -> ComponentProjection:
    """Project only groups whose parent, order, count and value kind are complete."""
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)
    if not hasattr(compositions, "emitted_ids"):
        raise ProfileError("COMPOSITION_PROJECTION_REQUIRED", type(compositions).__name__)
    from .composition import composition_iri

    rows = [dict(row.items()) if hasattr(row, "items") else dict(row.values) for row in component_rows]
    source_keys = [row.get("component_id", "") for row in rows]
    if any(not key for key in source_keys):
        raise ProfileError("COMPOSITION_COMPONENT_SOURCE_ID_REQUIRED")
    duplicate_keys = sorted(key for key, count in Counter(source_keys).items() if count > 1)
    if duplicate_keys:
        raise ProfileError("DUPLICATE_COMPOSITION_COMPONENT_SOURCE_ID", *duplicate_keys)
    parents = {row["composition_id"]: row for row in closure.table("morpheme_compositions").rows}
    admitted_parents = set(compositions.emitted_ids)
    atomic_identities = _atomic_identity_map(closure)
    groups = defaultdict(list)
    for row in rows:
        groups[row.get("composition_id", "")].append(row)
    missing_groups = sorted(
        parent_id for parent_id in admitted_parents
        if parent_id in parents and int(parents[parent_id]["component_count"]) > 0
        and parent_id not in groups
    )
    if missing_groups:
        raise ProfileError("COMPONENT_GROUP_MISSING", *missing_groups)

    graph, records = Graph(), []
    emitted, held = set(), set()
    issues = []
    for parent_id, group in sorted(groups.items()):
        component_ids = tuple(sorted(row.get("component_id", "") for row in group if row.get("component_id")))
        problems = []
        parent = parents.get(parent_id)
        if parent is None:
            problems.append(("COMPONENT_PARENT_NOT_FOUND", parent_id))
        elif parent_id not in admitted_parents:
            problems.append(("COMPONENT_PARENT_NOT_EMITTED", parent_id))
        positions = []
        for row in group:
            try:
                position = int(row.get("position_in_form", ""))
                if position <= 0 or str(position) != row.get("position_in_form", ""):
                    raise ValueError
                positions.append(position)
            except ValueError:
                problems.append(("INVALID_COMPONENT_POSITION", row.get("component_id", "")))
            atomic_id, literal = row.get("atomic_id", ""), row.get("literal_form_or_symbol", "")
            if bool(atomic_id) == bool(literal):
                problems.append(("INVALID_COMPONENT_VALUE_KIND", row.get("component_id", "")))
            if atomic_id and atomic_id not in atomic_identities:
                problems.append(("COMPONENT_ATOMIC_ID_NOT_RESOLVED", row.get("component_id", ""), atomic_id))
            for field in ("component_role", "literal_form_or_symbol", "slot_label", "condition"):
                if row.get(field, "") and safe_public_literal(row[field]) is None:
                    problems.append(("SOURCE_PUBLIC_LITERAL_REJECTED", row.get("component_id", ""), field))
        if len(positions) != len(set(positions)):
            problems.append(("DUPLICATE_COMPONENT_POSITION", parent_id))
        if parent is not None:
            expected = int(parent["component_count"])
            if len(group) != expected:
                problems.append(("COMPONENT_COUNT_MISMATCH", f"expected={expected}", f"actual={len(group)}"))
            if positions and sorted(positions) != list(range(1, expected + 1)):
                problems.append(("COMPONENT_POSITION_SEQUENCE_INVALID", parent_id))
        if problems:
            held.update(component_ids)
            for problem in problems:
                issues.append(ComponentIssue(problem[0], component_ids, parent_id, tuple(sorted(problem[1:]))))
            continue

        parent_iri = URIRef(composition_iri(parent_id))
        for row in sorted(group, key=lambda item: int(item["position_in_form"])):
            component_id = row["component_id"]
            position = int(row["position_in_form"])
            subject = URIRef(component_iri(component_id))
            atomic_id = row["atomic_id"]
            atomic_identity = atomic_identities.get(atomic_id) if atomic_id else None
            graph.add((subject, RDF.type, RDFS.Resource))
            graph.add((subject, DCTERMS.identifier, Literal(component_id)))
            graph.add((subject, DCTERMS.isPartOf, parent_iri))
            graph.add((parent_iri, URIRef(str(RDF) + "_" + str(position)), subject))
            graph.add((subject, COMPONENT_ROLE, Literal(row["component_role"], normalize=False)))
            if row["slot_label"]:
                graph.add((subject, SLOT_LABEL, Literal(row["slot_label"], normalize=False)))
            if row["condition"]:
                graph.add((subject, CONDITION, Literal(row["condition"], normalize=False)))
            if atomic_identity is not None:
                graph.add((subject, RDF.value, Literal(atomic_id, normalize=False)))
                graph.add((subject, DCTERMS.references, URIRef(atomic_identity.iri)))
            else:
                graph.add((subject, RDF.value, Literal(row["literal_form_or_symbol"], normalize=False)))
            records.append(ComponentRecord(
                component_id, str(subject), parent_id, position, row["component_role"],
                atomic_id, row["literal_form_or_symbol"], row["slot_label"], row["condition"],
                atomic_identity,
            ))
            emitted.add(component_id)
    all_ids = {row.get("component_id", "") for row in rows if row.get("component_id")}
    return ComponentProjection(
        graph, tuple(sorted(records)), tuple(sorted(emitted)),
        tuple(sorted(all_ids - emitted | held)), tuple(sorted(set(issues)))
    )


def ordered_components(
    records: tuple[ComponentRecord, ...], composition_id: str
) -> tuple[ComponentRecord, ...]:
    return tuple(sorted(
        (record for record in records if record.composition_id == composition_id),
        key=lambda record: (record.position, record.component_id),
    ))
