"""Deterministic atomic concept-definition normalization for issue #46."""
from __future__ import annotations

from dataclasses import dataclass, replace

from rdflib import Graph

from .errors import ProfileError
from .preflight import CompilerClosure
from .realization import RealizationNormalization, normalize_atomic_realizations
from .resolver import RecordRef, Resolution, ResolutionIssue, ResolvedResource
from .text import TextAssertion as ProfileTextAssertion, project_text


CONCEPT_DEFINITION = "CONCEPT_DEFINITION"
REALIZATION_NOTE = "REALIZATION_NOTE"
SOURCE_EDITORIAL = "SOURCE_EDITORIAL"
HELD_CONFLICT = "HELD_CONFLICT"
IGNORE_WITH_REASON = "IGNORE_WITH_REASON"
DEFINITION_CLASSES = (
    CONCEPT_DEFINITION,
    REALIZATION_NOTE,
    SOURCE_EDITORIAL,
    HELD_CONFLICT,
    IGNORE_WITH_REASON,
)


@dataclass(frozen=True, order=True)
class DefinitionCandidate:
    identity_iri: str
    record_ref: RecordRef
    text: str
    classification: str
    reason: str


@dataclass(frozen=True, order=True)
class ConceptDefinition:
    identity_iri: str
    text: str
    record_refs: tuple[RecordRef, ...]


@dataclass(frozen=True)
class DefinitionNormalization:
    resolution: Resolution
    definitions: tuple[ConceptDefinition, ...]
    candidates: tuple[DefinitionCandidate, ...]
    added_issues: tuple[ResolutionIssue, ...]

    @property
    def definition_count(self) -> int:
        return len(self.definitions)


def _conflict(identity, refs, summaries) -> ResolutionIssue:
    return ResolutionIssue(
        "CONFLICTING_SEMANTIC_MEANING",
        identity.keys,
        tuple(sorted(set(refs))),
        tuple(sorted(("field=semantic_summary", *(f"value={value}" for value in summaries)))),
    )


def _classify_group(identity, rows):
    """Return (definition text, per-row classification, optional issue)."""
    summaries = {row.get("semantic_summary") for _, row in rows if row.get("semantic_summary")}
    refs = [ref for ref, _ in rows]
    if len(summaries) == 1:
        text = next(iter(summaries))
        return text, {ref: (CONCEPT_DEFINITION, "stable identity-level source summary") for ref in refs}, None

    if len(rows) == 2:
        by_type = {row.get("realization_type"): (ref, row) for ref, row in rows}
        if set(by_type) == {"underlying_glottal", "realized_allomorph"}:
            base_ref, base = by_type["underlying_glottal"]
            realized_ref, realized = by_type["realized_allomorph"]
            base_text = base.get("semantic_summary")
            realized_text = realized.get("semantic_summary")
            same_group = base.get("allomorph_group_id") == realized.get("allomorph_group_id")
            if same_group and realized_text == f"{base_text} realized glottal form":
                return (
                    base_text,
                    {
                        base_ref: (CONCEPT_DEFINITION, "exact underlying source summary"),
                        realized_ref: (REALIZATION_NOTE, "explicit realized-glottal qualifier"),
                    },
                    None,
                )

    if rows and all(
        row.get("morpheme_class") == "fixed_register_adjunct"
        and row.get("slot") in {"register initial", "register final"}
        and row.get("semantic_summary", "").endswith(f" {row.get('slot')} adjunct")
        for _, row in rows
    ):
        return (
            None,
            {ref: (REALIZATION_NOTE, "summary explicitly names register realization slot") for ref, _ in rows},
            None,
        )

    classifications = {ref: (HELD_CONFLICT, "non-equivalent source summaries") for ref, _ in rows}
    return None, classifications, _conflict(identity, refs, sorted(summaries))


def normalize_atomic_definitions(
    closure: CompilerClosure,
    resolution: Resolution,
    realizations: RealizationNormalization | None = None,
) -> DefinitionNormalization:
    """Normalize atomic summaries without paraphrase or row-order authority."""
    normalized = realizations or normalize_atomic_realizations(closure, resolution)
    if normalized.issues:
        codes = ",".join(sorted({issue.code for issue in normalized.issues}))
        raise ProfileError("REALIZATION_NORMALIZATION_NOT_GREEN", codes)

    rows = {RecordRef("morphemes_atomic", row.get("atomic_id")): row
            for row in closure.table("morphemes_atomic").rows if row.get("atomic_id")}
    resource_by_iri = {resource.identity.iri: resource for resource in resolution.resources}
    transformed: dict[str, ResolvedResource] = {}
    definitions: list[ConceptDefinition] = []
    candidates: list[DefinitionCandidate] = []
    added_issues: list[ResolutionIssue] = []

    for group in normalized.groups:
        if group.identity.kind != "grammar":
            continue
        resource = resource_by_iri.get(group.identity.iri)
        if resource is None:
            continue
        group_rows = [(ref, rows[ref]) for ref in group.source_records if ref in rows]
        definition, classifications, issue = _classify_group(group.identity, group_rows)
        if issue is not None:
            added_issues.append(issue)
        for ref, row in group_rows:
            classification, reason = classifications[ref]
            candidates.append(DefinitionCandidate(
                group.identity.iri,
                ref,
                row.get("semantic_summary"),
                classification,
                reason,
            ))
        if issue is not None:
            continue
        if definition is not None:
            definition_refs = tuple(sorted(
                ref for ref, (classification, _) in classifications.items()
                if classification == CONCEPT_DEFINITION
            ))
            definitions.append(ConceptDefinition(group.identity.iri, definition, definition_refs))

        note_refs = {
            ref for ref, (classification, _) in classifications.items()
            if classification == REALIZATION_NOTE
        }
        texts = tuple(
            text for text in resource.texts
            if not (
                text.field == "semantic_summary"
                and text.role == "source_note"
                and text.record_ref not in note_refs
            )
        )
        transformed[group.identity.iri] = replace(resource, texts=texts)

    held_iris = {issue.semantic_key for issue in added_issues}
    output_resources = []
    for resource in resolution.resources:
        if resource.identity.kind == "grammar" and resource.identity.keys in held_iris:
            continue
        output_resources.append(transformed.get(resource.identity.iri, resource))
    output_issues = tuple(sorted(set((*resolution.issues, *added_issues))))
    return DefinitionNormalization(
        Resolution(tuple(output_resources), output_issues),
        tuple(sorted(definitions)),
        tuple(sorted(candidates)),
        tuple(sorted(set(added_issues))),
    )


def definition_graph(normalization: DefinitionNormalization) -> Graph:
    """Project selected exact source text as concept-scoped SKOS definitions."""
    assertions = []
    for definition in normalization.definitions:
        for ref in definition.record_refs:
            assertions.append(ProfileTextAssertion(
                resource=definition.identity_iri,
                field="semantic_summary",
                value=definition.text,
                language="en",
                source_ref=f"{ref.table}:{ref.key}",
                scope="concept",
            ))
    return project_text(assertions)
