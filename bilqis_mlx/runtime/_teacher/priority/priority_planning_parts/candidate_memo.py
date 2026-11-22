"""Restart-durable, non-authoritative A08 curriculum candidate memo."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.skos_curriculum.serialization import (
    _strict_source_bytes,
    curriculum_candidate_from_bytes,
)


_MEMO_DIR = "bamf-planning-derived/a08-candidate"
_MEMO_SCHEMA = "bilqis.bamf.a08-candidate-memo/v1"
_COMPILER_REVISION = "bilqis.bamf.a08-candidate-compiler/v1"


def _adapter_identity(source_adapters) -> tuple[tuple[str, ...], str]:
    adapter_ids = tuple(sorted(item.family_id for item in source_adapters))
    adapter_sha256 = hashlib.sha256(_strict_source_bytes(source_adapters)).hexdigest()
    return adapter_ids, adapter_sha256


def _memo_identity(selection, source_adapters) -> dict:
    adapter_ids, adapter_sha256 = _adapter_identity(source_adapters)
    return {
        "schema": _MEMO_SCHEMA,
        "compiler_revision": _COMPILER_REVISION,
        "atlas_bundle_id": selection.bundle_id,
        "semantic_release": selection.release_sha256,
        "source_bundle_id": selection.source_bundle_id,
        "source_adapter_ids": list(adapter_ids),
        "source_adapters_sha256": adapter_sha256,
    }


def _memo_key(identity: dict) -> str:
    raw = json.dumps(
        identity, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _memo_path(run_dir: Path, identity: dict) -> Path:
    root = Path(run_dir) / _MEMO_DIR
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        return root / "invalid"
    return root / f"{_memo_key(identity)}.json"


def load_candidate_memo(run_dir, selection, source_adapters):
    """Return an exact derived candidate memo, or None on any cache defect."""
    identity = _memo_identity(selection, source_adapters)
    source_adapter_ids, _adapter_sha256 = _adapter_identity(source_adapters)
    path = _memo_path(Path(run_dir), identity)
    if path.is_symlink() or not path.is_file():
        return None
    try:
        record = json.loads(path.read_bytes())
        if (not isinstance(record, dict)
                or set(record) != {"identity", "candidate_sha256", "candidate"}
                or record["identity"] != identity
                or not isinstance(record["candidate"], dict)):
            return None
        candidate_raw = _strict_json_bytes(record["candidate"])
        if hashlib.sha256(candidate_raw).hexdigest() != record["candidate_sha256"]:
            return None
        candidate = curriculum_candidate_from_bytes(candidate_raw)
    except (
        BilqisError, OSError, UnicodeDecodeError, json.JSONDecodeError,
        ValueError, TypeError,
    ):
        return None
    if (candidate.semantic_release != selection.release_sha256
            or candidate.atlas_bundle_id != selection.bundle_id
            or candidate.census.source_bundle_id != selection.source_bundle_id
            or candidate.source_adapter_ids != source_adapter_ids):
        return None
    return candidate


def persist_candidate_memo(run_dir, selection, source_adapters, candidate) -> None:
    """Publish one immutable derived memo; never overwrite conflicting bytes."""
    identity = _memo_identity(selection, source_adapters)
    raw = _strict_source_bytes(candidate)
    record = {
        "identity": identity,
        "candidate_sha256": hashlib.sha256(raw).hexdigest(),
        "candidate": json.loads(raw),
    }
    payload = _strict_json_bytes(record)
    path = _memo_path(Path(run_dir), identity)
    if path.name == "invalid":
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        return
    if path.exists():
        if path.is_file() and path.read_bytes() == payload:
            return
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".a08-candidate-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _strict_json_bytes(value) -> bytes:
    return (json.dumps(
        value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")


__all__ = ("load_candidate_memo", "persist_candidate_memo")
