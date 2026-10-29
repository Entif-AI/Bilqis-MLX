"""Read source-attested morphology rows without granting lesson authority.

The A01 bundle certifies source-row *identity*, not the contents of
research CSVs. The Ithkuil source owner's extraction-frontier receipt
separately binds the exact CSV bytes. Both must agree before a row
can be offered to a later A13-governed constructive lesson adapter.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.atlas_projection import _verify_bundle
from bilqis_mlx.semantics.atlas_snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)


MORPHOLOGY_SOURCE_SCHEMA = "bilqis.morphology-source-law-proposal/v1"
MORPHOLOGY_SOURCE_STATUS = "SOURCE_ROW_EVIDENCE_NOT_ADMITTED"
_CSV_ROOT = Path(__file__).resolve().parents[2] / "lib/ithkuil/_data/csv"
_TABLES = (
    ("morpheme_compositions.csv", "composition_id"),
    ("composition_components.csv", "component_id"),
    ("morphemes_atomic.csv", "atomic_id"),
    ("source_tables.csv", "table_id"),
    ("sources/source_manifest.csv", "source_id"),
)


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _ordinal(value: str) -> int:
    if type(value) is not str or not value.isascii() or not value.isdecimal():
        _fail("BAMF_MORPHOLOGY_SOURCE_LAW_HELD")
    return int(value)


def _frontier_receipt(root: Path) -> dict:
    path = root / "sources/extraction_frontier.json"
    if path.is_symlink() or not path.is_file():
        _fail("BAMF_MORPHOLOGY_FRONTIER_MISSING")
    try:
        receipt = json.loads(path.read_bytes())
    except (OSError, ValueError, UnicodeError):
        _fail("BAMF_MORPHOLOGY_FRONTIER_INVALID")
    if (type(receipt) is not dict
            or receipt.get("schema") != "bilqis.ithkuil.extraction-frontier/v1"
            or type(receipt.get("inputs")) is not dict
            or type(receipt.get("receipt_sha256")) is not str):
        _fail("BAMF_MORPHOLOGY_FRONTIER_INVALID")
    expected = receipt["receipt_sha256"]
    body = {key: value for key, value in receipt.items()
            if key != "receipt_sha256"}
    canonical_source = (
        json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n").encode("utf-8")
    if hashlib.sha256(canonical_source).hexdigest() != expected:
        _fail("BAMF_MORPHOLOGY_FRONTIER_DIGEST_DRIFT")
    return receipt


def _source_tables(root: Path) -> dict[str, tuple[dict[str, str], ...]]:
    receipt = _frontier_receipt(root)
    tables = {}
    for name, key in _TABLES:
        path = root / name
        if (path.is_symlink() or not path.is_file()
                or type(receipt["inputs"].get(name)) is not str):
            _fail("BAMF_MORPHOLOGY_SOURCE_TABLE_MISSING")
        try:
            payload = path.read_bytes()
        except OSError:
            _fail("BAMF_MORPHOLOGY_SOURCE_TABLE_INVALID")
        if hashlib.sha256(payload).hexdigest() != receipt["inputs"][name]:
            _fail("BAMF_MORPHOLOGY_SOURCE_TABLE_DRIFT")
        try:
            rows = tuple(csv.DictReader(payload.decode("utf-8").splitlines()))
        except (ValueError, UnicodeError, csv.Error):
            _fail("BAMF_MORPHOLOGY_SOURCE_TABLE_INVALID")
        keys = tuple(row.get(key) for row in rows)
        if (not rows or any(type(value) is not str or not value for value in keys)
                or len(set(keys)) != len(keys)):
            _fail("BAMF_MORPHOLOGY_SOURCE_TABLE_INVALID")
        tables[name] = rows
    return tables


@dataclass(frozen=True)
class MorphologySourceLaw:
    semantic_release: str
    source_bundle_id: str
    composition_id: str
    component_ids: tuple[str, ...]
    component_forms: tuple[str, ...]
    surface_form: str
    source_id: str
    source_table_id: str
    source_line: str
    source_row_sha256: str
    component_rows_sha256: str
    atomic_rows_sha256: str
    law_sha256: str
    schema: str = MORPHOLOGY_SOURCE_SCHEMA
    status: str = MORPHOLOGY_SOURCE_STATUS

    def __post_init__(self) -> None:
        if (type(self.schema) is not str
                or self.schema != MORPHOLOGY_SOURCE_SCHEMA
                or type(self.status) is not str
                or self.status != MORPHOLOGY_SOURCE_STATUS
                or any(type(item) is not str or not item for item in (
                    self.composition_id, self.surface_form,
                    self.source_id, self.source_table_id, self.source_line))
                or type(self.component_ids) is not tuple
                or type(self.component_forms) is not tuple
                or len(self.component_ids) != len(self.component_forms)
                or len(self.component_ids) < 2
                or any(type(item) is not str or not item
                       for item in self.component_ids + self.component_forms)
                or any(type(item) is not str or len(item) != 64
                       or any(ch not in "0123456789abcdef" for ch in item)
                       for item in (
                           self.semantic_release, self.source_bundle_id,
                           self.source_row_sha256, self.component_rows_sha256,
                           self.atomic_rows_sha256, self.law_sha256))
                or "".join(self.component_forms) != self.surface_form):
            _fail("BAMF_MORPHOLOGY_LAW_INVALID")


def resolve_morphology_source_law(
    selection: AtlasArtifactSelection, source_bundle: str | Path,
    composition_id: str,
) -> MorphologySourceLaw:
    """Reconcile one literal source law; never mint A13 or Factory admission."""
    if (type(selection) is not AtlasArtifactSelection
            or type(composition_id) is not str or not composition_id):
        _fail("BAMF_MORPHOLOGY_INPUT_INVALID")
    snapshot = load_pinned_atlas_snapshot(selection)
    bundle_id, payloads = _verify_bundle(Path(source_bundle))
    if bundle_id != snapshot.source_bundle_id:
        _fail("BAMF_MORPHOLOGY_SOURCE_BUNDLE_DRIFT")
    try:
        source_rows = json.loads(payloads["source-rows.json"])
    except (ValueError, UnicodeError):
        _fail("BAMF_MORPHOLOGY_SOURCE_ROWS_INVALID")
    source_keys = {(row["table"], row["key"]) for row in source_rows}
    if ("morpheme_compositions", composition_id) not in source_keys:
        _fail("BAMF_MORPHOLOGY_SOURCE_ROW_UNPINNED")
    tables = _source_tables(_CSV_ROOT)
    candidates = tuple(
        row for row in tables["morpheme_compositions.csv"]
        if row["composition_id"] == composition_id)
    if len(candidates) != 1:
        _fail("BAMF_MORPHOLOGY_SOURCE_ROW_MISSING")
    row = candidates[0]
    parts = tuple(sorted(
        (part for part in tables["composition_components.csv"]
         if part["composition_id"] == composition_id),
        key=lambda part: _ordinal(part["position_in_form"])))
    atoms = {item["atomic_id"]: item
             for item in tables["morphemes_atomic.csv"]}
    sources = {item["source_id"]: item
               for item in tables["sources/source_manifest.csv"]}
    source_tables = {item["table_id"]: item
                     for item in tables["source_tables.csv"]}
    declared_source = sources.get(row["primary_source_id"])
    declared_table = source_tables.get(row["primary_table_id"])
    if (row["evidence_status"] != "official_source_join"
            or row["condition"] or row["derivation"] != "source_join"
            or not row["primary_source_id"] or not row["primary_table_id"]
            or not row["primary_source_line"].isascii()
            or not row["primary_source_line"].isdecimal()
            or not row["primary_source_url"].startswith("https://www.ithkuil.net/")
            or declared_source is None or declared_table is None
            or declared_source["final_url"] != row["primary_source_url"]
            or declared_table["source_id"] != row["primary_source_id"]
            or declared_table["source_url"] != row["primary_source_url"]
            or declared_table["source_line"] != row["primary_source_line"]
            or len(parts) < 2 or _ordinal(row["component_count"]) != len(parts)
            or tuple(_ordinal(item["position_in_form"]) for item in parts)
               != tuple(range(1, len(parts) + 1))
            or any(item["condition"] or not item["atomic_id"]
                   or item["atomic_id"] not in atoms for item in parts)):
        _fail("BAMF_MORPHOLOGY_SOURCE_LAW_HELD")
    component_ids = tuple(item["atomic_id"] for item in parts)
    atom_rows = tuple(atoms[item] for item in component_ids)
    if (any(("morphemes_atomic", item) not in source_keys
            for item in component_ids)
            or any(atom["evidence_status"] != "official_source_observed"
                   for atom in atom_rows)
            or any(atom["allomorph_condition"] for atom in atom_rows)):
        _fail("BAMF_MORPHOLOGY_SOURCE_LAW_HELD")
    forms = tuple(atom["surface_form_normalized"] for atom in atom_rows)
    if (not all(forms) or "".join(forms) != row["surface_form_normalized"]
            or row["surface_form_raw"] != row["surface_form_normalized"]):
        _fail("BAMF_MORPHOLOGY_SOURCE_LAW_HELD")
    payload = {
        "schema": MORPHOLOGY_SOURCE_SCHEMA,
        "semantic_release": snapshot.release_sha256,
        "source_bundle_id": bundle_id,
        "composition_id": composition_id,
        "source_row": row,
        "components": parts,
        "atoms": atom_rows,
    }
    return MorphologySourceLaw(
        snapshot.release_sha256, bundle_id, composition_id,
        component_ids, forms, row["surface_form_normalized"],
        row["primary_source_id"], row["primary_table_id"],
        row["primary_source_line"], _digest(row), _digest(parts),
        _digest(atom_rows), _digest(payload))


def assert_morphology_source_law_current(
    law: MorphologySourceLaw, selection: AtlasArtifactSelection,
    source_bundle: str | Path,
) -> None:
    """Re-derive source evidence at the consumer; no transferable attestation."""
    if type(law) is not MorphologySourceLaw:
        _fail("BAMF_MORPHOLOGY_LAW_INVALID")
    MorphologySourceLaw.__post_init__(law)
    expected = resolve_morphology_source_law(
        selection, source_bundle, law.composition_id)
    if _canonical(asdict(law)) != _canonical(asdict(expected)):
        _fail("BAMF_MORPHOLOGY_LAW_SOURCE_DRIFT")
