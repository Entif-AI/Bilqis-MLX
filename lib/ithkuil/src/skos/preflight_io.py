"""Strict tracked-CSV loading boundary for issue #37."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
from typing import Iterable

from .preflight_manifest import InputManifest, TableSpec


@dataclass(frozen=True)
class FrozenRow:
    values: tuple[tuple[str, str], ...]

    def __getitem__(self, field: str) -> str:
        for key, value in self.values:
            if key == field:
                return value
        raise KeyError(field)

    def get(self, field: str, default: str = "") -> str:
        try:
            return self[field]
        except KeyError:
            return default

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.values, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class LoadedTable:
    name: str
    columns: tuple[str, ...]
    rows: tuple[FrozenRow, ...]


@dataclass(frozen=True, order=True)
class ValidationFinding:
    code: str
    table: str
    key: str
    field: str
    locus: str
    details: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "table": self.table,
            "key": self.key,
            "field": self.field,
            "locus": self.locus,
            "details": list(self.details),
        }


@dataclass(frozen=True)
class LoadedInput:
    manifest_version: str
    tables: tuple[LoadedTable, ...]
    findings: tuple[ValidationFinding, ...] = ()

    def table(self, name: str) -> LoadedTable:
        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(name)


def finding(
    code: str,
    table: str,
    *,
    key: str = "",
    field: str = "",
    locus: str = "",
    details: Iterable[str] = (),
) -> ValidationFinding:
    return ValidationFinding(code, table, key, field, locus, tuple(sorted(details)))

def _raw_record_fingerprint(raw: list[str]) -> str:
    payload = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

def _read_table(
    root: Path, spec: TableSpec
) -> tuple[LoadedTable | None, tuple[ValidationFinding, ...]]:
    path = root / spec.path
    try:
        exists = path.is_file()
    except OSError as error:
        return None, (
            finding("TABLE_READ_ERROR", spec.name, locus=spec.path, details=(type(error).__name__,)),
        )
    if not exists:
        return None, (finding("MISSING_TABLE", spec.name, locus=spec.path),)
    try:
        text = path.read_bytes().decode("utf-8", errors="strict")
    except OSError as error:
        return None, (
            finding("TABLE_READ_ERROR", spec.name, locus=spec.path, details=(type(error).__name__,)),
        )
    except UnicodeDecodeError as error:
        return None, (
            finding(
                "MALFORMED_UTF8",
                spec.name,
                locus=spec.path,
                details=(f"byte={error.start}",),
            ),
        )
    try:
        parsed = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as error:
        return None, (
            finding("MALFORMED_CSV", spec.name, locus=spec.path, details=(str(error),)),
        )
    if not parsed:
        return None, (
            finding("MALFORMED_CSV", spec.name, locus=spec.path, details=("empty file",)),
        )
    header = tuple(parsed[0])
    duplicates = sorted({name for name in header if header.count(name) > 1})
    if duplicates:
        return None, (
            finding(
                "DUPLICATE_CSV_HEADER",
                spec.name,
                field=",".join(duplicates),
                locus="header",
            ),
        )
    missing = sorted(set(spec.columns) - set(header))
    unexpected = sorted(set(header) - set(spec.columns))
    findings = [
        *(finding("MISSING_COLUMN", spec.name, field=field, locus="header") for field in missing),
        *(
            finding("UNEXPECTED_COLUMN", spec.name, field=field, locus="header")
            for field in unexpected
        ),
    ]
    if findings:
        return None, tuple(sorted(findings))
    positions = {field: header.index(field) for field in spec.columns}
    rows = []
    for raw in parsed[1:]:
        if len(raw) != len(header):
            findings.append(
                finding(
                    "MALFORMED_CSV",
                    spec.name,
                    locus=f"record={_raw_record_fingerprint(raw)}",
                    details=(f"fields={len(raw)}", f"expected={len(header)}"),
                )
            )
            continue
        rows.append(
            FrozenRow(tuple((field, raw[positions[field]]) for field in spec.columns))
        )
    if findings:
        return None, tuple(sorted(findings))
    return LoadedTable(spec.name, spec.columns, tuple(rows)), ()


def load_input_root(root: str | Path, manifest: InputManifest) -> LoadedInput:
    """Read only manifest-declared tracked CSVs; no semantic validation occurs here."""
    tables = []
    findings = []
    for spec in manifest.tables:
        table, table_findings = _read_table(Path(root), spec)
        findings.extend(table_findings)
        if table is not None:
            tables.append(table)
    return LoadedInput(manifest.version, tuple(tables), tuple(sorted(findings)))
