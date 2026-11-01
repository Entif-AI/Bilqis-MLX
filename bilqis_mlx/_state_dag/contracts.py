"""Shared state-DAG identities, hashing, durable writes, and object storage."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from enum import Enum
import tempfile

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH, data_plane

HEAD_SCHEMA = "bilqis.state-head/v1"
NODE_SCHEMA = "bilqis.state-node/v1"
INLINE_FIELD_LIMIT_BYTES = 32 * 1024
EXPOSURE_SHARD_PREFIX_LENGTH = 2
TEACHER_MISS_SHARD_PREFIX_LENGTH = 2
_FIELD_CACHE: dict[str, dict[str, tuple[object, dict]]] = dict()

class StateDagError(str, Enum):
    DESTINATION_COLLISION = "STATE_DAG_DESTINATION_COLLISION"
    OBJECT_DIGEST_INVALID = "STATE_DAG_OBJECT_DIGEST_INVALID"
    TEACHER_MISS_INVALID = "STATE_DAG_TEACHER_MISS_INVALID"
    TEACHER_MISS_CAPABILITY_INVALID = "STATE_DAG_TEACHER_MISS_CAPABILITY_INVALID"
    TEACHER_MISS_SHARD_DRIFT = "STATE_DAG_TEACHER_MISS_SHARD_DRIFT"
    TEACHER_MISS_PREFIX_DRIFT = "STATE_DAG_TEACHER_MISS_PREFIX_DRIFT"
    TEACHER_MISS_COUNT_DRIFT = "STATE_DAG_TEACHER_MISS_COUNT_DRIFT"
    TEACHER_CONTEXTS_INVALID = "STATE_DAG_TEACHER_CONTEXTS_INVALID"
    TEACHER_CONTEXT_COUNT_DRIFT = "STATE_DAG_TEACHER_CONTEXT_COUNT_DRIFT"
    EXPOSURE_ID_INVALID = "STATE_DAG_EXPOSURE_ID_INVALID"
    EXPOSURE_SHARD_DRIFT = "STATE_DAG_EXPOSURE_SHARD_DRIFT"
    EXPOSURE_COUNT_DRIFT = "STATE_DAG_EXPOSURE_COUNT_DRIFT"
    OBJECT_LIST_COUNT_DRIFT = "STATE_DAG_OBJECT_LIST_COUNT_DRIFT"
    FIELD_KIND_UNKNOWN = "STATE_DAG_FIELD_KIND_UNKNOWN"
    GENERATION_INVALID = "STATE_DAG_GENERATION_INVALID"
    NODE_POINTER_DRIFT = "STATE_DAG_NODE_POINTER_DRIFT"
    RECEIPT_DIGEST_DRIFT = "STATE_DAG_RECEIPT_DIGEST_DRIFT"
    CURRENT_STATE_MISSING = "STATE_DAG_CURRENT_STATE_MISSING"
    GENERATION_NOT_FOUND = "STATE_DAG_GENERATION_NOT_FOUND"
    LEGACY_ARCHIVE_SHA_DRIFT = "STATE_DAG_LEGACY_ARCHIVE_SHA_DRIFT"
    GENERATION_DRIFT = "STATE_DAG_GENERATION_DRIFT"
    MIGRATION_READBACK_DRIFT = "STATE_DAG_MIGRATION_READBACK_DRIFT"
    IMMUTABLE_GENERATION_COLLISION = "STATE_DAG_IMMUTABLE_GENERATION_COLLISION"
    LATEST_POINTER_NOT_DURABLE = "STATE_DAG_LATEST_POINTER_NOT_DURABLE"
    GENERATION_POINTER_DRIFT = "STATE_DAG_GENERATION_POINTER_DRIFT"
    HISTORY_MIGRATION_BUDGET_INVALID = "STATE_DAG_HISTORY_MIGRATION_BUDGET_INVALID"
    HISTORY_NORMALIZATION_DRIFT = "STATE_DAG_HISTORY_NORMALIZATION_DRIFT"
    HISTORY_READBACK_DRIFT = "STATE_DAG_HISTORY_READBACK_DRIFT"
    HISTORY_STALE_ARTIFACT_UNSAFE = "STATE_DAG_HISTORY_STALE_ARTIFACT_UNSAFE"
    OPERATOR_LOCK_UNSAFE = "STATE_DAG_OPERATOR_LOCK_UNSAFE"
    HUMAN_TRAINING_ACTIVE = "STATE_DAG_MIGRATION_HUMAN_TRAINING_ACTIVE"

def _error(code: StateDagError, detail=None) -> str:
    return code.value if detail is None else code.value + ":" + str(detail)

def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _durable(path: Path, data: bytes, *, replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or (not replace and path.read_bytes() != data):
            raise ValueError(_error(StateDagError.DESTINATION_COLLISION, path))
        if not replace:
            return
    fd, tmp = tempfile.mkstemp(prefix=".state-dag-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def _put_object(run_dir: Path, value) -> str:
    raw = _canonical(value)
    digest = _sha(raw)
    data_plane().put_object(digest, raw)
    return digest

def _get_object(run_dir: Path, digest: str):
    if not isinstance(digest, str) or len(digest) != SHA256_HEX_LENGTH:
        raise ValueError(StateDagError.OBJECT_DIGEST_INVALID.value)
    raw = data_plane().get_object(digest)
    return json.loads(raw)
