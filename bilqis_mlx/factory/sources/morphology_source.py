"""Read source-attested morphology rows without granting lesson authority.

The A01 bundle certifies source-row *identity*, not the contents of
research CSVs. The Ithkuil source owner's extraction-frontier receipt
separately binds the exact CSV bytes. Both must agree before a row
can be offered to a later A13-governed constructive lesson adapter.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.atlas_projection import _verify_bundle
from bilqis_mlx.semantics.atlas_snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.residue_source import composition_law_witness


MORPHOLOGY_SOURCE_SCHEMA = "bilqis.morphology-source-law-proposal/v1"
MORPHOLOGY_SOURCE_STATUS = "SOURCE_ROW_EVIDENCE_NOT_ADMITTED"
_CSV_ROOT = Path(__file__).resolve().parents[3] / "lib/ithkuil/_data/csv"


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


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
    source_owner: str
    source_loci: tuple[str, ...]
    source_row_sha256: str
    component_rows_sha256: str
    atomic_rows_sha256: str
    source_projection_sha256: str
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
                    self.source_id, self.source_table_id, self.source_line,
                    self.source_owner))
                or type(self.component_ids) is not tuple
                or type(self.component_forms) is not tuple
                or type(self.source_loci) is not tuple
                or not self.source_loci
                or len(self.component_ids) != len(self.component_forms)
                or len(self.component_ids) < 2
                or any(type(item) is not str or not item
                       for item in (
                           self.component_ids + self.component_forms
                           + self.source_loci))
                or any(type(item) is not str or len(item) != 64
                       or any(ch not in "0123456789abcdef" for ch in item)
                       for item in (
                           self.semantic_release, self.source_bundle_id,
                           self.source_row_sha256, self.component_rows_sha256,
                           self.atomic_rows_sha256,
                           self.source_projection_sha256, self.law_sha256))
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
        coverage = json.loads(payloads["coverage.json"])
    except (ValueError, UnicodeError, KeyError):
        _fail("BAMF_MORPHOLOGY_SOURCE_ROWS_INVALID")
    source_keys = {(row["table"], row["key"]) for row in source_rows}
    if ("morpheme_compositions", composition_id) not in source_keys:
        _fail("BAMF_MORPHOLOGY_SOURCE_ROW_UNPINNED")
    try:
        witness = composition_law_witness(_CSV_ROOT, composition_id)
    except ProfileError:
        _fail("BAMF_MORPHOLOGY_SOURCE_LAW_HELD")
    if any(("morphemes_atomic", item) not in source_keys
           for item in witness.component_ids):
        _fail("BAMF_MORPHOLOGY_SOURCE_LAW_HELD")
    try:
        residue_rows = coverage["domains"]["residue"]["rows"]
    except (KeyError, TypeError):
        _fail("BAMF_MORPHOLOGY_SOURCE_ROWS_INVALID")
    owner_rows = tuple(
        row for row in residue_rows
        if row.get("table") == "morpheme_compositions"
        and row.get("key") == composition_id)
    if (len(owner_rows) != 1
            or owner_rows[0].get("status") != "EMITTED"
            or owner_rows[0].get("owner") != witness.owner):
        _fail("BAMF_MORPHOLOGY_SOURCE_OWNER_DRIFT")
    payload = {
        "schema": MORPHOLOGY_SOURCE_SCHEMA,
        "semantic_release": snapshot.release_sha256,
        "source_bundle_id": bundle_id,
        "source_owner_row": owner_rows[0],
        "source_witness": asdict(witness),
    }
    return MorphologySourceLaw(
        snapshot.release_sha256, bundle_id, composition_id,
        witness.component_ids, witness.component_forms, witness.surface_form,
        witness.source_id, witness.source_table_id, witness.source_line,
        witness.owner, witness.source_loci,
        witness.composition_row_sha256, witness.component_rows_sha256,
        witness.atomic_rows_sha256, witness.projection_sha256,
        _digest(payload))


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
