"""Atlas projection persistence ownership; canonical algorithms preserved."""
from __future__ import annotations
from pathlib import Path
import json
import os
import shutil
import tempfile
from .artifacts import _artifact_payloads
from .common import ATLAS_MANIFEST_SCHEMA, _fail
from .releases import AtlasArtifactReceipt, AtlasRelease


def _verify_persisted(target: Path, payloads: dict[str, bytes], manifest_payload: bytes) -> None:
    expected = set(payloads) | {"manifest.json"}
    if target.is_symlink() or not target.is_dir():
        _fail("ATLAS_ARTIFACT_TARGET_INVALID")
    if {path.name for path in target.iterdir()} != expected:
        _fail("ATLAS_ARTIFACT_FILESET_DRIFT")
    for name, payload in {**payloads, "manifest.json": manifest_payload}.items():
        path = target / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
            _fail("ATLAS_ARTIFACT_CONTENT_DRIFT:" + name)

def _sync_directory(path: Path, *, reason: str) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        _fail(reason + ":" + type(error).__name__)

def persist_atlas_release(release: AtlasRelease, output_root: str | Path) -> AtlasArtifactReceipt:
    """Persist one immutable content-addressed semantic release without a database."""
    payloads, manifest_payload, bundle_id = _artifact_payloads(release)
    root = Path(output_root)
    if root.exists() and root.is_symlink():
        _fail("ATLAS_ARTIFACT_ROOT_SYMLINK")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    target = root / bundle_id
    if target.exists():
        _verify_persisted(target, payloads, manifest_payload)
    else:
        temp = Path(tempfile.mkdtemp(prefix=".atlas-", dir=root))
        try:
            for name, payload in {**payloads, "manifest.json": manifest_payload}.items():
                path = temp / name
                with path.open("xb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            _sync_directory(temp, reason="ATLAS_ARTIFACT_STAGING_SYNC_FAILED")
            try:
                os.rename(temp, target)
            except OSError:
                if not target.exists():
                    raise
                _verify_persisted(target, payloads, manifest_payload)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    _verify_persisted(target, payloads, manifest_payload)
    _sync_directory(root, reason="ATLAS_ARTIFACT_PARENT_SYNC_FAILED")
    manifest = json.loads(manifest_payload)
    return AtlasArtifactReceipt(
        schema=ATLAS_MANIFEST_SCHEMA,
        bundle_id=bundle_id,
        path=str(target),
        release_sha256=release.digest,
        file_sha256=tuple(sorted(
            (name, item["sha256"]) for name, item in manifest["files"].items())),
    )
