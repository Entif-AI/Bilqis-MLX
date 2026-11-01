"""Exact tracked-row byte witnesses for source-owned SKOS/Ithkuil adapters."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
from pathlib import Path

from ...ingestion_semantic import _frontier
from ..errors import ProfileError
from ..preflight_manifest import DEFAULT_MANIFEST_PATH, load_manifest


@dataclass(frozen=True)
class SourceRowByteWitness:
    domain: str
    table: str
    key: str
    relative_path: str
    primary_key: tuple[str, ...]
    record_start_byte: int
    record_end_byte: int
    record_sha256: str
    file_sha256: str
    frontier_sha256: str
    frontier_receipt_sha256: str
    values: tuple[tuple[str, str], ...]
    owner: str = "#57"

    @property
    def source_reference(self) -> str:
        return (
            "ithkuil-csv:" + self.domain + "/" + self.relative_path
            + "#" + self.key
            + "@sha256:" + self.record_sha256
        )


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _verified_file(root: Path, table: str):
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)
    try:
        spec = manifest.table(table)
    except KeyError as error:
        raise ProfileError("SOURCE_ROW_TABLE_UNKNOWN", table) from error
    repo_root = Path(__file__).resolve().parents[5]
    frontier_path = root / "sources/extraction_frontier.json"
    try:
        frontier, frontier_sha, receipt_sha = _frontier(
            frontier_path, root, repo_root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ProfileError(
            "SOURCE_ROW_FRONTIER_INVALID", table, type(error).__name__) from error
    expected = frontier["inputs"].get(spec.path)
    path = root / spec.path
    if (not isinstance(expected, str)
            or path.is_symlink() or not path.is_file()):
        raise ProfileError("SOURCE_ROW_FILE_UNPINNED", table, spec.path)
    payload = path.read_bytes()
    if _sha(payload) != expected:
        raise ProfileError("SOURCE_ROW_FILE_DRIFT", table, spec.path)
    return spec, payload, frontier_sha, receipt_sha


def _record_bounds(
    payload: bytes, columns: tuple[str, ...], primary_key: tuple[str, ...],
    key: str,
) -> tuple[int, int, tuple[tuple[str, str], ...]]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ProfileError("SOURCE_ROW_UTF8_INVALID", key) from error
    physical = text.splitlines(keepends=True)
    starts = [0]
    for line in physical:
        starts.append(starts[-1] + len(line.encode("utf-8")))
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error) as error:
        raise ProfileError("SOURCE_ROW_CSV_INVALID", key) from error
    if tuple(header) != columns:
        raise ProfileError("SOURCE_ROW_HEADER_DRIFT", key)
    positions = {field: header.index(field) for field in columns}
    previous_line = reader.line_num
    matched = []
    try:
        for raw in reader:
            start_line = previous_line
            end_line = reader.line_num
            previous_line = end_line
            if len(raw) != len(header):
                raise ProfileError("SOURCE_ROW_CSV_INVALID", key)
            row_key = "|".join(raw[positions[field]] for field in primary_key)
            if row_key == key:
                values = tuple(
                    (field, raw[positions[field]]) for field in columns)
                matched.append((starts[start_line], starts[end_line], values))
    except csv.Error as error:
        raise ProfileError("SOURCE_ROW_CSV_INVALID", key) from error
    if len(matched) != 1:
        raise ProfileError("SOURCE_ROW_KEY_NOT_UNIQUE", key)
    return matched[0]


def source_row_byte_witness(
    root: str | Path, domain: str, table: str, key: str,
) -> SourceRowByteWitness:
    if (not isinstance(domain, str) or not domain
            or not isinstance(table, str) or not table
            or not isinstance(key, str) or not key):
        raise ProfileError("SOURCE_ROW_ID_INVALID")
    path_root = Path(root)
    spec, payload, frontier_sha, receipt_sha = _verified_file(path_root, table)
    start, end, values = _record_bounds(
        payload, spec.columns, spec.primary_key, key)
    if not 0 <= start < end <= len(payload):
        raise ProfileError("SOURCE_ROW_BYTE_SPAN_INVALID", table, key)
    record = payload[start:end]
    return SourceRowByteWitness(
        domain, table, key, spec.path, spec.primary_key, start, end, _sha(record),
        _sha(payload), frontier_sha, receipt_sha, values)
