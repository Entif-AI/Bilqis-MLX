"""Filesystem publication and verified readback for AtlasFeatures/v2 artifacts."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
import shutil
import tempfile

from ..atlas_features import AtlasFeatures
from .feature_io_contracts import (
    ARTIFACT_SCHEMA, FeatureArtifactReceipt, _FILES, _SHA,
    _canonical, _digest, _invalid, _reject_nonfinite,
)
from .feature_io_validation import _parse_features, _validate_features

def _sync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        _invalid("BAMF_FEATURE_ARTIFACT_SYNC_FAILED")


def _read_bundle(
    bundle_dir: str | Path, predecessor: AtlasFeatures | None,
) -> tuple[AtlasFeatures, str]:
    root = Path(bundle_dir)
    if (root.is_symlink() or not root.is_dir()
            or not _SHA.fullmatch(root.name)):
        _invalid("BAMF_FEATURE_ARTIFACT_PATH_INVALID")
    try:
        members = tuple(root.iterdir())
    except OSError:
        _invalid("BAMF_FEATURE_ARTIFACT_PATH_INVALID")
    if ({item.name for item in members} != _FILES
            or any(item.is_symlink() or not item.is_file()
                   for item in members)):
        _invalid("BAMF_FEATURE_ARTIFACT_FILESET_INVALID")
    try:
        manifest_payload = (root / "manifest.json").read_bytes()
        manifest = json.loads(
            manifest_payload, parse_constant=_reject_nonfinite)
        feature_payload = (root / "features.json").read_bytes()
    except (OSError, ValueError, UnicodeError):
        _invalid("BAMF_FEATURE_ARTIFACT_READ_INVALID")
    if not isinstance(manifest, dict):
        _invalid("BAMF_FEATURE_ARTIFACT_MANIFEST_INVALID")
    if manifest.get("schema") != ARTIFACT_SCHEMA:
        _invalid("BAMF_FEATURE_ARTIFACT_MANIFEST_INVALID")
    if (_canonical(manifest) != manifest_payload
            or _digest(manifest_payload) != root.name):
        _invalid("BAMF_FEATURE_ARTIFACT_MANIFEST_INVALID")
    if set(manifest) != {
            "schema", "feature_digest", "semantic_release",
            "source_bundle_id", "atlas_bundle_id",
            "predecessor_digest", "files"}:
        _invalid("BAMF_FEATURE_ARTIFACT_MANIFEST_INVALID")
    files = manifest["files"]
    if not isinstance(files, dict) or set(files) != {"features.json"}:
        _invalid("BAMF_FEATURE_ARTIFACT_MANIFEST_INVALID")
    descriptor = files["features.json"]
    if not isinstance(descriptor, dict) or set(descriptor) != {'sha256', 'bytes'}:
        _invalid('BAMF_FEATURE_ARTIFACT_FILE_DIGEST_INVALID')
    if (not isinstance(descriptor['sha256'], str)
            or not _SHA.fullmatch(descriptor['sha256'])
            or type(descriptor['bytes']) is not int
            or descriptor['bytes'] < 0
            or len(feature_payload) != descriptor['bytes']
            or _digest(feature_payload) != descriptor['sha256']):
        _invalid('BAMF_FEATURE_ARTIFACT_FILE_DIGEST_INVALID')
    features = _parse_features(feature_payload, predecessor)
    if (features.digest != manifest['feature_digest']
            or any(getattr(features, field) != manifest[field]
                   for field in ('semantic_release', 'source_bundle_id',
                                 'atlas_bundle_id', 'predecessor_digest'))):
        _invalid('BAMF_FEATURE_ARTIFACT_PROVENANCE_INVALID')
    return features, root.name


def persist_feature_manifest(
    features: AtlasFeatures, output_root: str | Path,
    *, predecessor: AtlasFeatures | None = None,
) -> FeatureArtifactReceipt:
    """Publish a local immutable feature artifact; retry verifies existing bytes."""
    _validate_features(features, predecessor)
    feature_payload = _canonical(asdict(features))
    manifest = {
        'schema': ARTIFACT_SCHEMA,
        'feature_digest': features.digest,
        'semantic_release': features.semantic_release,
        'source_bundle_id': features.source_bundle_id,
        'atlas_bundle_id': features.atlas_bundle_id,
        'predecessor_digest': features.predecessor_digest,
        'files': {'features.json': {
            'sha256': _digest(feature_payload),
            'bytes': len(feature_payload),
        }},
    }
    manifest_payload = _canonical(manifest)
    bundle_id = _digest(manifest_payload)
    root = Path(output_root)
    if root.is_symlink():
        _invalid('BAMF_FEATURE_ARTIFACT_ROOT_SYMLINK')
    try:
        root.mkdir(parents=True, exist_ok=True)
        root = root.resolve()
    except OSError:
        _invalid('BAMF_FEATURE_ARTIFACT_ROOT_INVALID')
    target = root / bundle_id
    if target.is_symlink():
        _invalid('BAMF_FEATURE_ARTIFACT_TARGET_SYMLINK')
    if not target.exists():
        try:
            temp = Path(tempfile.mkdtemp(prefix='.features-', dir=root))
        except OSError:
            _invalid('BAMF_FEATURE_ARTIFACT_PUBLISH_FAILED')
        try:
            for name, payload in (
                ('features.json', feature_payload),
                ('manifest.json', manifest_payload),
            ):
                with (temp / name).open('xb') as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            _sync_directory(temp)
            try:
                os.rename(temp, target)
            except OSError:
                if not target.exists():
                    _invalid('BAMF_FEATURE_ARTIFACT_PUBLISH_FAILED')
        except OSError:
            _invalid('BAMF_FEATURE_ARTIFACT_PUBLISH_FAILED')
        finally:
            try:
                if temp.exists():
                    shutil.rmtree(temp)
            except OSError:
                _invalid('BAMF_FEATURE_ARTIFACT_CLEANUP_FAILED')
    stored, stored_id = _read_bundle(target, predecessor)
    if stored_id != bundle_id or stored != features:
        _invalid('BAMF_FEATURE_ARTIFACT_EXISTING_DRIFT')
    _sync_directory(root)
    return FeatureArtifactReceipt(
        bundle_id, str(target), features.digest,
        features.semantic_release, features.predecessor_digest)


def load_feature_manifest(
    bundle_dir: str | Path,
    *,
    expected_bundle_id: str | None = None,
    expected_feature_digest: str | None = None,
    expected_semantic_release: str | None = None,
    expected_source_bundle_id: str | None = None,
    expected_atlas_bundle_id: str | None = None,
    predecessor: AtlasFeatures | None = None,
) -> AtlasFeatures:
    """Verify once from local disk, then use features_for without I/O."""
    features, bundle_id = _read_bundle(bundle_dir, predecessor)
    pins = (
        (bundle_id, expected_bundle_id),
        (features.digest, expected_feature_digest),
        (features.semantic_release, expected_semantic_release),
        (features.source_bundle_id, expected_source_bundle_id),
        (features.atlas_bundle_id, expected_atlas_bundle_id),
    )
    if any(expected is not None and actual != expected
           for actual, expected in pins):
        _invalid('BAMF_FEATURE_ARTIFACT_PIN_MISMATCH')
    return features
