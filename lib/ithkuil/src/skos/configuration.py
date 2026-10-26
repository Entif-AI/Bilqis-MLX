"""Bounded Configuration selector for the #44 golden SKOS projection."""
from __future__ import annotations

from dataclasses import dataclass

from .errors import ProfileError
from .preflight import CompilerClosure
from .resolver import RecordRef, Resolution, ResolvedResource


CONFIGURATION_CODE = "CONFIGURATION"
CONFIGURATION_TABLE = "morphemes_atomic"


@dataclass(frozen=True)
class ConfigurationSelection:
    source_records: tuple[RecordRef, ...]
    resources: tuple[ResolvedResource, ...]


def select_configuration_resources(
    closure: CompilerClosure, resolution: Resolution
) -> ConfigurationSelection:
    """Select every Configuration source row and its resolved semantic resources.

    The source class is defined by the explicit category code in the validated
    relational closure. Rows are never filtered by value, form, family, or resolver
    success, so an unsupported Configuration row cannot disappear from the slice.
    """
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)
    if not isinstance(resolution, Resolution):
        raise ProfileError("RESOLUTION_REQUIRED", type(resolution).__name__)

    categories = tuple(
        row
        for row in closure.table("grammatical_categories").rows
        if row.get("category_code") == CONFIGURATION_CODE
    )
    if len(categories) != 1:
        raise ProfileError("CONFIGURATION_CATEGORY_REGISTRY_COUNT", str(len(categories)))

    rows = tuple(
        row
        for row in closure.table(CONFIGURATION_TABLE).rows
        if row.get("category_code") == CONFIGURATION_CODE
    )
    if not rows:
        raise ProfileError("CONFIGURATION_SOURCE_ROWS_REQUIRED")

    refs = tuple(RecordRef(CONFIGURATION_TABLE, row.get("atomic_id")) for row in rows)
    if len(refs) != len(set(refs)):
        raise ProfileError("CONFIGURATION_DUPLICATE_SOURCE_RECORD")
    ref_set = frozenset(refs)

    implicated = tuple(
        issue
        for issue in resolution.issues
        if ref_set.intersection(issue.record_refs)
    )
    if implicated:
        issue = min(implicated)
        raise ProfileError(
            "CONFIGURATION_RESOLUTION_HELD",
            issue.code,
            *(f"{ref.table}:{ref.key}" for ref in issue.record_refs),
        )

    by_ref: dict[RecordRef, list[ResolvedResource]] = {ref: [] for ref in refs}
    for resource in resolution.resources:
        for ref in resource.source_records:
            if ref in by_ref:
                by_ref[ref].append(resource)

    missing = tuple(sorted(ref for ref, resources in by_ref.items() if not resources))
    if missing:
        raise ProfileError(
            "CONFIGURATION_SOURCE_ROW_UNRESOLVED",
            *(f"{ref.table}:{ref.key}" for ref in missing),
        )
    ambiguous = tuple(
        sorted(ref for ref, resources in by_ref.items() if len(set(resources)) != 1)
    )
    if ambiguous:
        raise ProfileError(
            "CONFIGURATION_SOURCE_ROW_AMBIGUOUS",
            *(f"{ref.table}:{ref.key}" for ref in ambiguous),
        )

    resources = tuple(
        sorted(
            {resources[0] for resources in by_ref.values()},
            key=lambda resource: resource.identity.iri,
        )
    )
    for resource in resources:
        outside = tuple(sorted(set(resource.source_records) - ref_set))
        if outside:
            raise ProfileError(
                "CONFIGURATION_RESOURCE_CROSSES_SOURCE_CLASS",
                resource.identity.iri,
                *(f"{ref.table}:{ref.key}" for ref in outside),
            )

    covered = frozenset(ref for resource in resources for ref in resource.source_records)
    if covered != ref_set:
        raise ProfileError("CONFIGURATION_SOURCE_COVERAGE_MISMATCH")
    return ConfigurationSelection(tuple(sorted(ref_set)), resources)
