"""Pure relational compiler preflight for issue #37."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .errors import ProfileError
from .preflight_io import (
    FrozenRow,
    LoadedInput,
    LoadedTable,
    ValidationFinding,
    finding,
    load_input_root,
)
from .preflight_manifest import DEFAULT_MANIFEST_PATH, InputManifest, TableSpec, load_manifest
from .preflight_rules import validate_semantic_invariants


@dataclass(frozen=True)
class CompilerClosure:
    manifest_version: str
    tables: tuple[LoadedTable, ...]

    def table(self, name: str) -> LoadedTable:
        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(name)


@dataclass(frozen=True)
class PreflightResult:
    manifest_version: str
    findings: tuple[ValidationFinding, ...]
    closure: CompilerClosure | None

    @property
    def ok(self) -> bool:
        return not self.findings and self.closure is not None

    def as_dict(self) -> dict:
        return {
            "manifest_version": self.manifest_version,
            "ok": self.ok,
            "findings": [item.as_dict() for item in self.findings],
        }

    def require_valid(self) -> CompilerClosure:
        if self.ok:
            assert self.closure is not None
            return self.closure
        item = self.findings[0]
        raise ProfileError(
            item.code,
            f"table={item.table}",
            f"key={item.key}",
            f"field={item.field}",
            f"locus={item.locus}",
            *item.details,
        )


def _row_key(row: FrozenRow, spec: TableSpec) -> tuple[str, ...]:
    return tuple(row.get(field) for field in spec.primary_key)


def _key_text(values: Iterable[str]) -> str:
    return "|".join(values)


def _indexes(
    loaded: LoadedInput, manifest: InputManifest
) -> dict[tuple[str, tuple[str, ...]], set[tuple[str, ...]]]:
    indexes = {}
    for spec in manifest.tables:
        table = loaded.table(spec.name)
        field_sets = {spec.primary_key}
        for source in manifest.tables:
            for foreign_key in source.foreign_keys:
                if foreign_key.target == spec.name:
                    field_sets.add(foreign_key.target_fields)
        for fields in field_sets:
            indexes[(spec.name, fields)] = {
                tuple(row.get(field) for field in fields) for row in table.rows
            }
    return indexes



def validate_loaded(loaded: LoadedInput, manifest: InputManifest) -> PreflightResult:
    """Pure validation over immutable loaded rows."""
    if loaded.findings:
        return PreflightResult(manifest.version, loaded.findings, None)
    findings = []
    indexes = _indexes(loaded, manifest)

    for spec in manifest.tables:
        table = loaded.table(spec.name)
        seen: dict[tuple[str, ...], list[FrozenRow]] = {}
        for row in table.rows:
            key_values = _row_key(row, spec)
            key = _key_text(key_values)
            locus = f"row={row.fingerprint}"
            if any(value.strip() == "" for value in key_values):
                findings.append(
                    finding(
                        "BLANK_PRIMARY_KEY",
                        spec.name,
                        key=key,
                        field=",".join(spec.primary_key),
                        locus=locus,
                    )
                )
            seen.setdefault(key_values, []).append(row)
            for field in spec.required_nonblank:
                if row[field].strip() == "":
                    findings.append(
                        finding(
                            "BLANK_REQUIRED_FIELD",
                            spec.name,
                            key=key,
                            field=field,
                            locus=locus,
                        )
                    )
            for field, allowed in spec.enums:
                value = row[field]
                if value not in allowed:
                    findings.append(
                        finding(
                            "INVALID_ENUM_STATE",
                            spec.name,
                            key=key,
                            field=field,
                            locus=locus,
                            details=(f"value={value!r}",),
                        )
                    )
        for key_values, rows in seen.items():
            if len(rows) > 1:
                findings.append(
                    finding(
                        "DUPLICATE_PRIMARY_KEY",
                        spec.name,
                        key=_key_text(key_values),
                        field=",".join(spec.primary_key),
                        locus=",".join(sorted(row.fingerprint for row in rows)),
                    )
                )

    for spec in manifest.tables:
        table = loaded.table(spec.name)
        for foreign_key in spec.foreign_keys:
            target = indexes[(foreign_key.target, foreign_key.target_fields)]
            for row in table.rows:
                values = tuple(row[field] for field in foreign_key.fields)
                if foreign_key.optional_if_any_blank and any(value.strip() == "" for value in values):
                    continue
                if values not in target:
                    findings.append(
                        finding(
                            "UNKNOWN_FOREIGN_KEY",
                            spec.name,
                            key=_key_text(_row_key(row, spec)),
                            field=",".join(foreign_key.fields),
                            locus=f"row={row.fingerprint}",
                            details=(
                                f"target={foreign_key.target}",
                                f"target_fields={','.join(foreign_key.target_fields)}",
                                f"value={_key_text(values)}",
                            ),
                        )
                    )

    for conditional in manifest.conditional_foreign_keys:
        table = loaded.table(conditional.table)
        targets = {
            selector: (target, field)
            for selector, target, field in conditional.targets
        }
        spec = manifest.table(conditional.table)
        for row in table.rows:
            selector = row[conditional.selector_field]
            if selector not in targets:
                continue
            target_name, target_field = targets[selector]
            target_values = indexes[(target_name, (target_field,))]
            value = (row[conditional.source_field],)
            if value not in target_values:
                findings.append(
                    finding(
                        "UNKNOWN_SOURCE_ASSERTION_ENTITY",
                        conditional.table,
                        key=_key_text(_row_key(row, spec)),
                        field=conditional.source_field,
                        locus=f"row={row.fingerprint}",
                        details=(f"target={target_name}", f"value={value[0]}"),
                    )
                )

    sources = {
        row["source_id"]: row for row in loaded.table("source_manifest").rows
    }
    for binding in manifest.source_bindings:
        table = loaded.table(binding.table)
        spec = manifest.table(binding.table)
        for row in table.rows:
            source = sources.get(row[binding.source_field])
            if source is not None and row[binding.url_field] != source["final_url"]:
                findings.append(
                    finding(
                        "SOURCE_URL_BINDING_CONFLICT",
                        binding.table,
                        key=_key_text(_row_key(row, spec)),
                        field=binding.url_field,
                        locus=f"row={row.fingerprint}",
                        details=(f"source_id={row[binding.source_field]}",),
                    )
                )

    findings.extend(validate_semantic_invariants(loaded, manifest))
    ordered = tuple(sorted(set(findings)))
    if ordered:
        return PreflightResult(manifest.version, ordered, None)

    normalized = []
    for spec in manifest.tables:
        table = loaded.table(spec.name)
        rows = tuple(
            sorted(table.rows, key=lambda row: (_row_key(row, spec), row.values))
        )
        normalized.append(LoadedTable(table.name, table.columns, rows))
    return PreflightResult(
        manifest.version,
        (),
        CompilerClosure(manifest.version, tuple(normalized)),
    )


def preflight(
    input_root: str | Path,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> PreflightResult:
    """Validate an explicit CSV root; this function never writes output artifacts."""
    manifest = load_manifest(manifest_path)
    loaded = load_input_root(input_root, manifest)
    return validate_loaded(loaded, manifest)
