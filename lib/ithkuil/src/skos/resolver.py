"""Deterministic semantic identity resolution over the #37 compiler closure."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .errors import ProfileError
from .identity import Identity, sense_from_source
from .preflight import CompilerClosure


NEW_ITHKUIL = Identity("scheme", ("new-ithkuil",))
ROOT_ATOM_CLASSES = frozenset({"lexical_consonantal_root", "CS_consonantal_root"})
GRAMMAR_ATOM_CLASSES = frozenset({
    "CA_consonantal_exponent", "CA_fused_exponent", "CN_consonantal_exponent",
    "CP_consonantal_exponent", "VC_vocalic_exponent", "VK_vocalic_exponent",
    "VN_vocalic_exponent", "VR_vocalic_exponent", "VX_vocalic_exponent",
    "fixed_consonantal_adjunct", "fixed_register_adjunct",
    "referential_consonantal_exponent", "vocalic_exponent",
})
PRIMARY_KEYS = {
    "grammatical_categories": "category_id",
    "morphemes_atomic": "atomic_id",
    "root_senses": "sense_id",
    "lexicon_roots": "lexicon_root_id",
    "lexicon_root_senses": "lexicon_sense_id",
}


@dataclass(frozen=True, order=True)
class RecordRef:
    table: str
    key: str


@dataclass(frozen=True, order=True)
class Realization:
    record_ref: RecordRef
    lexical_form: str
    realization_type: str
    condition: str


@dataclass(frozen=True, order=True)
class TextAssertion:
    record_ref: RecordRef
    field: str
    text: str
    role: str
    scope: str
    language: str | None


@dataclass(frozen=True)
class ResolvedResource:
    identity: Identity
    role: str
    source_records: tuple[RecordRef, ...]
    realizations: tuple[Realization, ...]
    families: tuple[str, ...]
    texts: tuple[TextAssertion, ...]
    schemes: tuple[Identity, ...]


@dataclass(frozen=True, order=True)
class ResolutionIssue:
    code: str
    semantic_key: tuple[str, ...]
    record_refs: tuple[RecordRef, ...]
    details: tuple[str, ...]


@dataclass(frozen=True)
class Resolution:
    resources: tuple[ResolvedResource, ...]
    issues: tuple[ResolutionIssue, ...]


def _ref(table: str, row) -> RecordRef:
    primary = PRIMARY_KEYS[table]
    key = row.get(primary)
    return RecordRef(table, key if key else f"row:{row.fingerprint}")


def _issue(code: str, key: Iterable[str], refs: Iterable[RecordRef], *details: str) -> ResolutionIssue:
    return ResolutionIssue(code, tuple(key), tuple(sorted(set(refs))), tuple(sorted(details)))


def _identity(kind: str, keys: tuple[str, ...], ref: RecordRef, issues: list[ResolutionIssue]) -> Identity | None:
    if any(not key for key in keys):
        issues.append(_issue("MISSING_SEMANTIC_KEY", keys, (ref,), f"identity_kind={kind}"))
        return None
    try:
        return Identity(kind, keys)
    except ProfileError as exc:
        issues.append(_issue(exc.code, keys, (ref,), *map(str, exc.details)))
        return None


def _text(ref: RecordRef, row, field: str, role: str, scope: str, language: str | None) -> TextAssertion | None:
    value = row.get(field)
    if not value:
        return None
    return TextAssertion(ref, field, value, role, scope, language)


def _atom_payload(row, ref: RecordRef) -> tuple[Realization, tuple[TextAssertion, ...]]:
    realization = Realization(
        ref, row.get("surface_form_normalized"), row.get("realization_type"), row.get("allomorph_condition")
    )
    texts = tuple(sorted(filter(None, (
        _text(ref, row, "surface_form_raw", "source_notation_raw", "realization", None),
        _text(ref, row, "value_name", "source_pref_label", "resource", "en"),
        _text(ref, row, "semantic_summary", "source_note", "realization", "en"),
    ))))
    return realization, texts


def _resource(identity: Identity, role: str, rows: list[tuple[str, object]], families: Iterable[str] = ()) -> ResolvedResource:
    refs: list[RecordRef] = []
    realizations: list[Realization] = []
    texts: list[TextAssertion] = []
    for table, row in rows:
        ref = _ref(table, row)
        refs.append(ref)
        if table == "morphemes_atomic":
            realization, atom_texts = _atom_payload(row, ref)
            realizations.append(realization)
            texts.extend(atom_texts)
        elif table == "lexicon_roots":
            realizations.append(Realization(ref, row.get("root_form_normalized"), "source_root_form", ""))
            texts.extend(filter(None, (
                _text(ref, row, "root_form_raw", "source_notation_raw", "realization", None),
                _text(ref, row, "root_gloss", "source_pref_label", "resource", "en"),
            )))
        else:
            texts.extend(filter(None, (
                _text(ref, row, "sense_summary", "identity_definition", "resource", "en"),
                _text(ref, row, "source_example_excerpt", "source_excerpt", "resource", "en"),
            )))
    return ResolvedResource(
        identity=identity,
        role=role,
        source_records=tuple(sorted(set(refs))),
        realizations=tuple(sorted(set(realizations))),
        families=tuple(sorted(set(f for f in families if f))),
        texts=tuple(sorted(set(texts))),
        schemes=(NEW_ITHKUIL,) if role == "concept" else (),
    )


def _meaning_conflict(
    identity: Identity, rows: list[tuple[str, object]], field: str, issues: list[ResolutionIssue]
) -> bool:
    values = {row.get(field) for _, row in rows if row.get(field)}
    if len(values) <= 1:
        return False
    refs = [_ref(table, row) for table, row in rows]
    issues.append(_issue(
        "CONFLICTING_SEMANTIC_MEANING", identity.keys, refs,
        f"field={field}", *(f"value={value}" for value in sorted(values)),
    ))
    return True


def _resolve_atoms(closure: CompilerClosure, issues: list[ResolutionIssue]) -> tuple[list[ResolvedResource], set[Identity]]:
    allowed_families = {
        (row["category_code"], row["family"])
        for row in closure.table("grammatical_categories").rows
    }
    grammar: dict[Identity, list[tuple[str, object]]] = defaultdict(list)
    roots: dict[Identity, list[tuple[str, object]]] = defaultdict(list)
    for row in closure.table("morphemes_atomic").rows:
        ref = _ref("morphemes_atomic", row)
        atom_class = row.get("morpheme_class")
        if atom_class in ROOT_ATOM_CLASSES:
            identity = _identity("root", (row.get("primary_source_id"), row.get("atomic_id")), ref, issues)
            if identity:
                roots[identity].append(("morphemes_atomic", row))
            continue
        if atom_class not in GRAMMAR_ATOM_CLASSES:
            issues.append(_issue("UNKNOWN_ATOM_SHAPE", (atom_class,), (ref,), f"morpheme_class={atom_class}"))
            continue
        keys = (row.get("category_code"), row.get("value_code"))
        identity = _identity("grammar", keys, ref, issues)
        if identity is None:
            continue
        if (row.get("category_code"), row.get("morpheme_family")) not in allowed_families:
            issues.append(_issue(
                "UNKNOWN_SOURCE_FAMILY", identity.keys, (ref,), f"family={row.get('morpheme_family')}"
            ))
            continue
        grammar[identity].append(("morphemes_atomic", row))

    resources: list[ResolvedResource] = []
    resolved_roots: set[Identity] = set()
    for identity, rows in grammar.items():
        if not _meaning_conflict(identity, rows, "value_name", issues):
            resources.append(_resource(identity, "concept", rows, (row["morpheme_family"] for _, row in rows)))
    for identity, rows in roots.items():
        if not _meaning_conflict(identity, rows, "value_name", issues):
            resources.append(_resource(identity, "root", rows, (row["morpheme_family"] for _, row in rows)))
            resolved_roots.add(identity)
    return resources, resolved_roots


def _resolve_lexicon_roots(closure: CompilerClosure, issues: list[ResolutionIssue]) -> tuple[list[ResolvedResource], set[Identity]]:
    grouped: dict[Identity, list[tuple[str, object]]] = defaultdict(list)
    for row in closure.table("lexicon_roots").rows:
        ref = _ref("lexicon_roots", row)
        identity = _identity("root", (row.get("source_id"), row.get("lexicon_root_id")), ref, issues)
        if identity:
            grouped[identity].append(("lexicon_roots", row))
    resources = []
    resolved_roots: set[Identity] = set()
    for identity, rows in grouped.items():
        if not _meaning_conflict(identity, rows, "root_gloss", issues):
            resources.append(_resource(identity, "root", rows))
            resolved_roots.add(identity)
    return resources, resolved_roots


def _resolve_senses(
    closure: CompilerClosure, root_ids: set[Identity], issues: list[ResolutionIssue]
) -> list[ResolvedResource]:
    grouped: dict[Identity, list[tuple[str, object]]] = defaultdict(list)
    for table in ("root_senses", "lexicon_root_senses"):
        for row in closure.table(table).rows:
            ref = _ref(table, row)
            try:
                identity = sense_from_source(table, dict(row.values))
            except ProfileError as exc:
                root_field = "atomic_id" if table == "root_senses" else "lexicon_root_id"
                attempted_key = (
                    row.get("source_id"), row.get(root_field), row.get("stem"), row.get("specification")
                )
                issues.append(_issue(exc.code, attempted_key, (ref,), *map(str, exc.details)))
                continue
            parent = Identity("root", identity.keys[:2])
            if parent not in root_ids:
                issues.append(_issue("SENSE_ROOT_NOT_RESOLVED", identity.keys, (ref,), parent.iri))
                continue
            grouped[identity].append((table, row))
    resources = []
    for identity, rows in grouped.items():
        if not _meaning_conflict(identity, rows, "sense_summary", issues):
            resources.append(_resource(identity, "concept", rows))
    return resources


def _remove_iri_collisions(resources: list[ResolvedResource], issues: list[ResolutionIssue]) -> list[ResolvedResource]:
    by_iri: dict[str, list[ResolvedResource]] = defaultdict(list)
    for resource in resources:
        by_iri[resource.identity.iri].append(resource)
    rejected: set[Identity] = set()
    for iri, group in by_iri.items():
        identities = {resource.identity for resource in group}
        refs = [ref for resource in group for ref in resource.source_records]
        if len(identities) > 1:
            issues.append(_issue("IRI_COLLISION", (iri,), refs, *(repr(item) for item in sorted(identities))))
            rejected.update(identities)
        elif len(group) > 1:
            identity = next(iter(identities))
            source_tables = sorted({ref.table for ref in refs})
            issues.append(_issue(
                "SOURCE_IDENTITY_CONFLICT", identity.keys, refs,
                *(f"table={table}" for table in source_tables),
            ))
            rejected.add(identity)
    return [resource for resource in resources if resource.identity not in rejected]


def _remove_orphan_senses(resources: list[ResolvedResource], issues: list[ResolutionIssue]) -> list[ResolvedResource]:
    roots = {resource.identity for resource in resources if resource.role == "root"}
    kept: list[ResolvedResource] = []
    for resource in resources:
        if resource.identity.kind != "sense":
            kept.append(resource)
            continue
        parent = Identity("root", resource.identity.keys[:2])
        if parent in roots:
            kept.append(resource)
            continue
        issues.append(_issue(
            "SENSE_ROOT_NOT_RESOLVED", resource.identity.keys, resource.source_records, parent.iri
        ))
    return kept


def resolve_identities(closure: CompilerClosure) -> Resolution:
    """Resolve semantic identities from one immutable validated #37 closure."""
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)
    issues: list[ResolutionIssue] = []
    atom_resources, atom_roots = _resolve_atoms(closure, issues)
    lexicon_resources, lexicon_roots = _resolve_lexicon_roots(closure, issues)
    resources = atom_resources + lexicon_resources
    resources.extend(_resolve_senses(closure, atom_roots | lexicon_roots, issues))
    resources = _remove_iri_collisions(resources, issues)
    resources = _remove_orphan_senses(resources, issues)
    ordered_resources = tuple(sorted(resources, key=lambda resource: resource.identity.iri))
    return Resolution(ordered_resources, tuple(sorted(set(issues))))
