"""Pinned Atlas artifact-selection contracts."""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path

from ..atlas_projection import HEX64, _canonical_bytes, _fail

ATLAS_SELECTION_SCHEMA = "bilqis.atlas-artifact-selection/v1"
ATLAS_SOURCE_PIN_REGISTRY_SCHEMA = "bilqis.atlas-source-pin-registry/v1"
ATLAS_SOURCE_PIN_REGISTRY_SHA256 = (
    "842b66ad7b19ddb333610668410820b3f5d703fa1e452d014755c2c5cc308cee")


@dataclass(frozen=True)
class AtlasArtifactSelection:
    """An A01 artifact locator checked against the repo-owned source pin."""

    path: str
    bundle_id: str
    release_sha256: str
    source_bundle_id: str
    schema: str = ATLAS_SELECTION_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.schema) is not str
                or self.schema != ATLAS_SELECTION_SCHEMA
                or type(self.path) is not str or not self.path
                or any(type(value) is not str or not HEX64.fullmatch(value)
                       for value in (
                           self.bundle_id, self.release_sha256,
                           self.source_bundle_id))):
            _fail("ATLAS_SOURCE_SELECTION_INVALID")


def _validate_selection_exact(selection: AtlasArtifactSelection) -> None:
    """A frozen dataclass is not a trust boundary: recheck its live fields."""
    if type(selection) is not AtlasArtifactSelection:
        _fail("ATLAS_SOURCE_SELECTION_INVALID")
    AtlasArtifactSelection.__post_init__(selection)


def _require_registered_source_pin(selection: AtlasArtifactSelection) -> None:
    """Source admission is repository-owned, never a caller-minted bundle ID."""
    _validate_selection_exact(selection)
    path = Path(__file__).resolve().parents[1] / "atlas_source_pins_v1.json"
    if path.is_symlink() or not path.is_file():
        _fail("ATLAS_SOURCE_PIN_REGISTRY_MISSING")
    try:
        payload = path.read_bytes()
        registry = json.loads(payload)
    except (OSError, ValueError, UnicodeError) as error:
        _fail("ATLAS_SOURCE_PIN_REGISTRY_INVALID:" + type(error).__name__)
    if (hashlib.sha256(payload).hexdigest()
            != ATLAS_SOURCE_PIN_REGISTRY_SHA256
            or not isinstance(registry, dict)
            or set(registry) != {"schema", "entries"}
            or registry["schema"] != ATLAS_SOURCE_PIN_REGISTRY_SCHEMA
            or payload != _canonical_bytes(registry)
            or not isinstance(registry["entries"], list)):
        _fail("ATLAS_SOURCE_PIN_REGISTRY_INVALID")
    expected_keys = {
        "bundle_id", "release_sha256", "source_bundle_id",
        "source_receipt", "status"}
    entries = registry["entries"]
    if (not entries or any(
            not isinstance(entry, dict)
            or set(entry) != expected_keys
            or any(not isinstance(entry[name], str)
                   or not HEX64.fullmatch(entry[name])
                   for name in ("bundle_id", "release_sha256", "source_bundle_id"))
            or entry["status"] != "A01_SOURCE_ATTESTED_NOT_NEURAL_ADMITTED"
            or not isinstance(entry["source_receipt"], str)
            or not entry["source_receipt"].startswith("docs/evidence/bamf/A01.")
            for entry in entries)
            or len({entry["bundle_id"] for entry in entries}) != len(entries)):
        _fail("ATLAS_SOURCE_PIN_REGISTRY_INVALID")
    if not any(all(hmac.compare_digest(
            getattr(selection, name), entry[name])
            for name in ("bundle_id", "release_sha256", "source_bundle_id"))
            for entry in entries):
        _fail("ATLAS_SOURCE_PIN_NOT_REGISTERED")
