"""Deterministic atomic realization normalization for issue #45."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .identity import Identity
from .notation import NEW_ITHKUIL_DATATYPE_IRI
from .preflight import CompilerClosure
from .resolver import (
    GRAMMAR_ATOM_CLASSES,
    ROOT_ATOM_CLASSES,
    RecordRef,
    Resolution,
    ResolvedResource,
)


REALIZATION_TYPES = frozenset({
    "conditioned_allomorph",
    "overt",
    "overt_optional",
    "realized_allomorph",
    "standalone_allomorph",
    "underlying_glottal",
    "zero",
})


@dataclass(frozen=True, order=True)
class NormalizedRealization:
    record_ref: RecordRef
    raw_form: str
    normalized_form: str
    notation_datatype_iri: str
    realization_type: str
    allomorph_group_id: str
    condition: str
    family: str
    morpheme_class: str
    slot: str
    source_id: str
    section_id: str
    table_id: str
    source_line: str
    source_url: str
    source_anchor: str


@dataclass(frozen=True)
class RealizationGroup:
    identity: Identity
    role: str
    schemes: tuple[Identity, ...]
    source_records: tuple[RecordRef, ...]
    realizations: tuple[NormalizedRealization, ...]


@dataclass(frozen=True, order=True)
class NormalizationIssue:
    code: str
    semantic_key: tuple[str, ...]
    record_refs: tuple[RecordRef, ...]
    details: tuple[str, ...]


@dataclass(frozen=True)
class RealizationNormalization:
    groups: tuple[RealizationGroup, ...]
    issues: tuple[NormalizationIssue, ...]
    source_row_count: int

    @property
    def grammar_group_count(self) -> int:
        return sum(group.identity.kind == "grammar" for group in self.groups)

    @property
    def atomic_root_group_count(self) -> int:
        return sum(group.identity.kind == "root" for group in self.groups)


def _ref(row) -> RecordRef:
    key = row.get("atomic_id")
    return RecordRef("morphemes_atomic", key if key else f"row:{row.fingerprint}")


def _expected_identity(row) -> Identity | None:
    atom_class = row.get("morpheme_class")
    if atom_class in GRAMMAR_ATOM_CLASSES:
        category, value = row.get("category_code"), row.get("value_code")
        if not category or not value:
            return None
        return Identity("grammar", (category, value))
    if atom_class in ROOT_ATOM_CLASSES:
        source_id, atomic_id = row.get("primary_source_id"), row.get("atomic_id")
        if not source_id or not atomic_id:
            return None
        return Identity("root", (source_id, atomic_id))
    return None


def _issue(code: str, identity: Identity | None, refs, *details: str) -> NormalizationIssue:
    semantic_key = identity.keys if identity is not None else ()
    return NormalizationIssue(
        code,
        semantic_key,
        tuple(sorted(set(refs))),
        tuple(sorted(str(detail) for detail in details)),
    )


def _normalized(row, ref: RecordRef) -> NormalizedRealization:
    return NormalizedRealization(
        record_ref=ref,
        raw_form=row.get("surface_form_raw"),
        normalized_form=row.get("surface_form_normalized"),
        notation_datatype_iri=NEW_ITHKUIL_DATATYPE_IRI,
        realization_type=row.get("realization_type"),
        allomorph_group_id=row.get("allomorph_group_id"),
        condition=row.get("allomorph_condition"),
        family=row.get("morpheme_family"),
        morpheme_class=row.get("morpheme_class"),
        slot=row.get("slot"),
        source_id=row.get("primary_source_id"),
        section_id=row.get("primary_section_id"),
        table_id=row.get("primary_table_id"),
        source_line=row.get("primary_source_line"),
        source_url=row.get("primary_source_url"),
        source_anchor=row.get("primary_source_anchor"),
    )


def normalize_atomic_realizations(
    closure: CompilerClosure, resolution: Resolution
) -> RealizationNormalization:
    """Normalize atomic source rows through already-resolved semantic identities.

    Grammar concepts use the declared category/value semantic key. Atomic roots retain
    their source-qualified root identity. Senses are not realization groups. Surface
    strings, English text, row order, and store state never participate in identity.
    """
    rows = closure.table("morphemes_atomic").rows
    row_by_ref: dict[RecordRef, list[object]] = defaultdict(list)
    expected_candidates: dict[RecordRef, set[Identity | None]] = defaultdict(set)
    issues: list[NormalizationIssue] = []

    for row in rows:
        ref = _ref(row)
        row_by_ref[ref].append(row)
        identity = _expected_identity(row)
        expected_candidates[ref].add(identity)
        realization_type = row.get("realization_type")
        if realization_type not in REALIZATION_TYPES:
            issues.append(_issue(
                "UNKNOWN_REALIZATION_TYPE", identity, (ref,),
                f"realization_type={realization_type}",
            ))
        if not row.get("surface_form_raw") or not row.get("surface_form_normalized"):
            issues.append(_issue("MISSING_REALIZATION_FORM", identity, (ref,)))
        if not row.get("allomorph_group_id"):
            issues.append(_issue("MISSING_ALLOMORPH_GROUP", identity, (ref,)))

    expected_by_ref: dict[RecordRef, Identity | None] = {}
    for ref, source_rows in sorted(row_by_ref.items()):
        candidates = expected_candidates[ref]
        expected = next(iter(candidates)) if len(candidates) == 1 else None
        expected_by_ref[ref] = expected
        if len(source_rows) > 1:
            details = tuple(
                f"semantic_iri={identity.iri if identity is not None else 'missing'}"
                for identity in sorted(candidates, key=lambda value: value.iri if value else "")
            )
            issues.append(_issue(
                "DUPLICATE_REALIZATION_SOURCE_REF", expected, (ref,),
                f"rows={len(source_rows)}", *details,
            ))

    group_claims: dict[str, dict[Identity, list[RecordRef]]] = defaultdict(lambda: defaultdict(list))
    for ref, source_rows in row_by_ref.items():
        for row in source_rows:
            identity = _expected_identity(row)
            group_id = row.get("allomorph_group_id")
            if identity is not None and identity.kind == "grammar" and group_id:
                group_claims[group_id][identity].append(ref)
    for group_id, identity_map in sorted(group_claims.items()):
        if len(identity_map) <= 1:
            continue
        refs = [ref for values in identity_map.values() for ref in values]
        details = tuple(f"semantic_iri={identity.iri}" for identity in sorted(identity_map))
        issues.append(_issue("ALLOMORPH_GROUP_SEMANTIC_CONFLICT", None, refs, f"group={group_id}", *details))

    resource_by_ref: dict[RecordRef, list[ResolvedResource]] = defaultdict(list)
    for resource in resolution.resources:
        for ref in resource.source_records:
            if ref.table == "morphemes_atomic":
                resource_by_ref[ref].append(resource)

    issue_refs = {
        ref
        for issue in resolution.issues
        for ref in issue.record_refs
        if ref.table == "morphemes_atomic"
    }
    invalid_refs = {ref for issue in issues for ref in issue.record_refs}
    groups: list[RealizationGroup] = []
    seen_resources: set[ResolvedResource] = set()
    for ref in sorted(row_by_ref):
        expected = expected_by_ref[ref]
        if ref in issue_refs:
            upstream = tuple(
                sorted({issue.code for issue in resolution.issues if ref in issue.record_refs})
            )
            issues.append(_issue("UPSTREAM_RESOLUTION_HELD", expected, (ref,), *upstream))
            continue
        if ref in invalid_refs:
            continue
        resources = tuple(sorted(set(resource_by_ref.get(ref, ())), key=lambda item: item.identity.iri))
        if len(resources) != 1:
            issues.append(_issue(
                "REALIZATION_RESOURCE_CARDINALITY", expected, (ref,), f"count={len(resources)}"
            ))
            continue
        resource = resources[0]
        if expected is None or resource.identity != expected:
            issues.append(_issue(
                "INCOMPATIBLE_REALIZATION_SEMANTIC_KEY", expected, (ref,),
                f"resolved={resource.identity.iri}",
            ))
            continue
        seen_resources.add(resource)

    blocked_refs = {ref for issue in issues for ref in issue.record_refs}
    for resource in sorted(seen_resources, key=lambda item: item.identity.iri):
        refs = tuple(ref for ref in resource.source_records if ref.table == "morphemes_atomic")
        if not refs or any(ref in blocked_refs for ref in refs):
            continue
        source_rows = [row_by_ref[ref][0] for ref in refs]
        expected = {_expected_identity(row) for row in source_rows}
        if expected != {resource.identity}:
            issues.append(_issue(
                "INCOMPATIBLE_REALIZATION_SEMANTIC_KEY", resource.identity, refs,
                *(f"source_identity={item.iri if item else 'missing'}" for item in sorted(expected, key=lambda value: value.iri if value else "")),
            ))
            continue
        normalized = tuple(sorted(_normalized(row, _ref(row)) for row in source_rows))
        groups.append(RealizationGroup(
            identity=resource.identity,
            role=resource.role,
            schemes=resource.schemes,
            source_records=tuple(sorted(refs)),
            realizations=normalized,
        ))

    return RealizationNormalization(
        groups=tuple(groups),
        issues=tuple(sorted(set(issues))),
        source_row_count=len(rows),
    )
