"""Pinned Atlas artifact-selection contracts."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path

from ..atlas_projection import HEX64, _canonical_bytes, _fail

ATLAS_SELECTION_SCHEMA = "bilqis.atlas-artifact-selection/v1"
ATLAS_IDENTITY_SCHEMA = "bilqis.atlas-artifact-identity/v1"
ATLAS_SOURCE_PIN_REGISTRY_SCHEMA = "bilqis.atlas-source-pin-registry/v1"
ATLAS_SOURCE_PIN_REGISTRY_SHA256 = (
    "842b66ad7b19ddb333610668410820b3f5d703fa1e452d014755c2c5cc308cee")
ATLAS_ARTIFACT_ROOT_ENV = "BILQIS_ATLAS_ARTIFACT_ROOT"


def _validate_identity_fields(
        bundle_id, release_sha256, source_bundle_id, *,
        reason="ATLAS_SOURCE_IDENTITY_INVALID") -> None:
    if any(type(value) is not str or not HEX64.fullmatch(value)
           for value in (bundle_id, release_sha256, source_bundle_id)):
        _fail(reason)


@dataclass(frozen=True)
class AtlasArtifactIdentity:
    """Portable A01 source identity with no host-local storage location."""

    bundle_id: str
    release_sha256: str
    source_bundle_id: str
    schema: str = ATLAS_IDENTITY_SCHEMA

    def __post_init__(self) -> None:
        if type(self.schema) is not str or self.schema != ATLAS_IDENTITY_SCHEMA:
            _fail("ATLAS_SOURCE_IDENTITY_INVALID")
        _validate_identity_fields(
            self.bundle_id, self.release_sha256, self.source_bundle_id)


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
                or type(self.path) is not str or not self.path):
            _fail("ATLAS_SOURCE_SELECTION_INVALID")
        _validate_identity_fields(
            self.bundle_id, self.release_sha256, self.source_bundle_id,
            reason="ATLAS_SOURCE_SELECTION_INVALID")

    @property
    def identity(self) -> AtlasArtifactIdentity:
        return AtlasArtifactIdentity(
            self.bundle_id, self.release_sha256, self.source_bundle_id)


def _validate_selection_exact(selection: AtlasArtifactSelection) -> None:
    """A frozen dataclass is not a trust boundary: recheck its live fields."""
    if type(selection) is not AtlasArtifactSelection:
        _fail("ATLAS_SOURCE_SELECTION_INVALID")
    AtlasArtifactSelection.__post_init__(selection)


def _validate_source_identity(source) -> None:
    if type(source) is AtlasArtifactSelection:
        _validate_selection_exact(source)
    elif type(source) is AtlasArtifactIdentity:
        source.__post_init__()
    else:
        _fail("ATLAS_SOURCE_IDENTITY_INVALID")


def _require_registered_source_pin(source) -> None:
    """Source admission is repository-owned, never a caller-minted bundle ID."""
    _validate_source_identity(source)
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
            getattr(source, name), entry[name])
            for name in ("bundle_id", "release_sha256", "source_bundle_id"))
            for entry in entries):
        _fail("ATLAS_SOURCE_PIN_NOT_REGISTERED")


def resolve_atlas_artifact_selection(
        identity: AtlasArtifactIdentity) -> AtlasArtifactSelection:
    """Map portable content identity to this machine's content-addressed root."""
    if type(identity) is not AtlasArtifactIdentity:
        _fail("ATLAS_SOURCE_IDENTITY_INVALID")
    identity.__post_init__()
    root = os.environ.get(ATLAS_ARTIFACT_ROOT_ENV)
    if not root:
        current = (os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
                   or os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"))
        if not current:
            _fail("ATLAS_ARTIFACT_ROOT_MISSING")
        root = str(Path(current).parent)
    return AtlasArtifactSelection(
        str(Path(root) / identity.bundle_id),
        identity.bundle_id, identity.release_sha256, identity.source_bundle_id)
