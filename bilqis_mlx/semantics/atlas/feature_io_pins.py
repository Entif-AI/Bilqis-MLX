"""Repository-owned A06 feature artifact selection over pinned A01/A03 authority."""
from __future__ import annotations

import hmac
import json
from pathlib import Path

from .snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from .feature_io_contracts import _SHA, _canonical, _digest, _invalid
from .feature_io_storage import load_feature_manifest


SOURCE_PIN_REGISTRY_SCHEMA = "bilqis.atlas-feature-source-pins/v1"
SOURCE_PIN_REGISTRY_SHA256 = (
    "931e55956f58e42dafa28c543cfb7dd567fc864912825918449d1c99c9c70317")
SOURCE_PIN_STATUS = "A06_SOURCE_ATTESTED_NOT_NEURAL_ADMITTED"


def _a03_pin_set_digest(snapshot) -> str:
    from ..released_frame_schemas import _source_pins

    entries = tuple(sorted(({
        "family": entry["family"],
        "schema_manifest_sha256": entry["schema_manifest_sha256"],
        "schema_map_sha256": entry["schema_map_sha256"],
    } for entry in _source_pins()
        if entry["semantic_release"] == snapshot.release_sha256
        and entry["atlas_bundle_id"] == snapshot.bundle_id
        and entry["source_bundle_id"] == snapshot.source_bundle_id),
        key=lambda entry: entry["family"]))
    if (not entries
            or len({entry["family"] for entry in entries}) != len(entries)):
        _invalid("BAMF_FEATURE_A03_PIN_SET_INVALID")
    return _digest(_canonical(entries))


def _feature_source_pins() -> tuple[dict, ...]:
    path = Path(__file__).resolve().parents[1] / "atlas_feature_source_pins_v1.json"
    if path.is_symlink() or not path.is_file():
        _invalid("BAMF_FEATURE_SOURCE_PIN_REGISTRY_MISSING")
    try:
        payload = path.read_bytes()
        registry = json.loads(payload)
    except (OSError, ValueError, UnicodeError):
        _invalid("BAMF_FEATURE_SOURCE_PIN_REGISTRY_INVALID")
    if (not hmac.compare_digest(_digest(payload), SOURCE_PIN_REGISTRY_SHA256)
            or not isinstance(registry, dict)
            or set(registry) != {"schema", "entries"}
            or registry["schema"] != SOURCE_PIN_REGISTRY_SCHEMA
            or payload != _canonical(registry)
            or not isinstance(registry["entries"], list)
            or not registry["entries"]):
        _invalid("BAMF_FEATURE_SOURCE_PIN_REGISTRY_INVALID")
    required = {
        "semantic_release", "atlas_bundle_id", "source_bundle_id",
        "a03_pin_set_sha256", "feature_bundle_id", "feature_digest",
        "predecessor_digest", "source_receipt", "status"}
    for entry in registry["entries"]:
        predecessor = entry.get("predecessor_digest") if isinstance(entry, dict) else None
        if (not isinstance(entry, dict) or set(entry) != required
                or any(not isinstance(entry[name], str) or not _SHA.fullmatch(entry[name])
                       for name in (
                           "semantic_release", "atlas_bundle_id", "source_bundle_id",
                           "a03_pin_set_sha256", "feature_bundle_id", "feature_digest"))
                or (predecessor is not None
                    and (not isinstance(predecessor, str) or not _SHA.fullmatch(predecessor)))
                or entry["source_receipt"] != "docs/evidence/bamf/A06.2/receipt.md"
                or entry["status"] != SOURCE_PIN_STATUS):
            _invalid("BAMF_FEATURE_SOURCE_PIN_REGISTRY_INVALID")
    entries = tuple(registry["entries"])
    if len({(
            entry["semantic_release"], entry["atlas_bundle_id"],
            entry["source_bundle_id"], entry["a03_pin_set_sha256"])
            for entry in entries}) != len(entries):
        _invalid("BAMF_FEATURE_SOURCE_PIN_REGISTRY_INVALID")
    return entries


def load_source_pinned_feature_manifest(
    bundle_dir: str | Path, *, atlas_selection: AtlasArtifactSelection,
):
    """Load the one A06 artifact selected by repository A01+A03 pins.

    ``bundle_dir`` is only a locator.  The accepted artifact identity comes from
    the hash-pinned A06 registry and its exact A01/A03 authority binding.
    """
    if type(atlas_selection) is not AtlasArtifactSelection:
        _invalid("BAMF_FEATURE_SOURCE_SELECTION_INVALID")
    snapshot = load_pinned_atlas_snapshot(atlas_selection)
    a03_digest = _a03_pin_set_digest(snapshot)
    matches = tuple(entry for entry in _feature_source_pins()
                    if entry["semantic_release"] == snapshot.release_sha256
                    and entry["atlas_bundle_id"] == snapshot.bundle_id
                    and entry["source_bundle_id"] == snapshot.source_bundle_id
                    and entry["a03_pin_set_sha256"] == a03_digest)
    if len(matches) != 1:
        _invalid("BAMF_FEATURE_SOURCE_PIN_NOT_REGISTERED")
    pin = matches[0]
    if pin["predecessor_digest"] is not None:
        _invalid("BAMF_FEATURE_PREDECESSOR_AUTHORITY_REQUIRED")
    return load_feature_manifest(
        bundle_dir,
        expected_bundle_id=pin["feature_bundle_id"],
        expected_feature_digest=pin["feature_digest"],
        expected_semantic_release=snapshot.release_sha256,
        expected_source_bundle_id=snapshot.source_bundle_id,
        expected_atlas_bundle_id=snapshot.bundle_id,
        predecessor=None,
    )
