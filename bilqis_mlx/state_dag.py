"""Content-addressed immutable DAG for School50 resumable state.

The live head and per-generation files are tiny pointers. Logical receipt fields
are immutable Merkle objects, so unchanged state is shared across generations.
Legacy monolithic JSON remains readable for migration and old evidence.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from bilqis_mlx.data_plane import data_plane

from ._state_dag.contracts import (
    HEAD_SCHEMA, NODE_SCHEMA, INLINE_FIELD_LIMIT_BYTES, EXPOSURE_SHARD_PREFIX_LENGTH,
    TEACHER_MISS_SHARD_PREFIX_LENGTH, StateDagError, _FIELD_CACHE, _canonical,
    _sha, _durable, _put_object, _get_object,
)
from ._state_dag.fields import _decode_field, _encode_field
from ._state_dag.nodes import _current_parent, _read_pointer, _write_node

def _load_pointer_fields(run_dir: Path, pointer: dict, keys=None) -> dict:
    digest = pointer.get("node_sha256")
    raw = data_plane().get_node(digest)
    node = json.loads(raw)
    if (node.get("schema") != NODE_SCHEMA or
            node.get("generation") != pointer.get("generation")):
        raise ValueError(StateDagError.NODE_POINTER_DRIFT.value)
    if (_sha(_canonical(node["fields"])) != node.get("receipt_sha256") or
            node.get("receipt_sha256") != pointer.get("receipt_sha256")):
        raise ValueError(StateDagError.RECEIPT_DIGEST_DRIFT.value)
    fields = node["fields"]
    selected = fields if keys is None else {
        key: fields[key] for key in keys if key in fields}
    receipt = {key: _decode_field(run_dir, spec)
               for key, spec in selected.items()}
    if keys is None:
        _FIELD_CACHE[str(run_dir.resolve())] = {
            key: (receipt[key], spec) for key, spec in fields.items()}
    return receipt

def _load_pointer(run_dir: Path, pointer: dict) -> dict:
    return _load_pointer_fields(run_dir, pointer)

def read_current(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    path = run_dir / "state.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError(StateDagError.CURRENT_STATE_MISSING.value)
    value = json.loads(path.read_text(encoding="utf-8"))
    return _load_pointer(run_dir, value) if value.get("schema") == HEAD_SCHEMA else value

def read_current_fields(run_dir: Path, keys) -> dict:
    """Read only selected logical fields from the current state head."""
    run_dir = Path(run_dir)
    path = run_dir / "state.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError(StateDagError.CURRENT_STATE_MISSING.value)
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") == HEAD_SCHEMA:
        return _load_pointer_fields(run_dir, value, tuple(keys))
    return {key: value[key] for key in keys if key in value}

def _legacy_or_pointer(path: Path):
    if path.is_symlink() or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def read_generation(run_dir: Path, generation: int) -> dict:
    if type(generation) is not int or generation < 0:
        raise ValueError(StateDagError.GENERATION_INVALID.value)
    root = Path(run_dir) / "states"
    path = root / f"{generation:07d}.json"
    value = _legacy_or_pointer(path)
    if value is None:
        zipped = root / f"{generation:07d}.json.gz"
        proof = root / f"{generation:07d}.json.sha256"
        if zipped.is_symlink() or proof.is_symlink() or not zipped.is_file() or not proof.is_file():
            raise ValueError(StateDagError.GENERATION_NOT_FOUND.value)
        with gzip.open(zipped, "rb") as stream:
            raw = stream.read()
        if _sha(raw) != proof.read_text(encoding="ascii").strip():
            raise ValueError(StateDagError.LEGACY_ARCHIVE_SHA_DRIFT.value)
        value = json.loads(raw)
    receipt = (_load_pointer(Path(run_dir), value)
               if value.get("schema") == HEAD_SCHEMA else value)
    if receipt.get("generation") != generation:
        raise ValueError(StateDagError.GENERATION_DRIFT.value)
    return receipt

def read_generation_fields(run_dir: Path, generation: int, keys) -> dict:
    """Read selected fields from one immutable generation without full rehydration."""
    if type(generation) is not int or generation < 0:
        raise ValueError(StateDagError.GENERATION_INVALID.value)
    root = Path(run_dir) / "states"
    path = root / f"{generation:07d}.json"
    value = _legacy_or_pointer(path)
    if value is None:
        zipped = root / f"{generation:07d}.json.gz"
        proof = root / f"{generation:07d}.json.sha256"
        if zipped.is_symlink() or proof.is_symlink() or not zipped.is_file() or not proof.is_file():
            raise ValueError(StateDagError.GENERATION_NOT_FOUND.value)
        with gzip.open(zipped, "rb") as stream:
            raw = stream.read()
        if _sha(raw) != proof.read_text(encoding="ascii").strip():
            raise ValueError(StateDagError.LEGACY_ARCHIVE_SHA_DRIFT.value)
        value = json.loads(raw)
    if value.get("generation") != generation:
        raise ValueError(StateDagError.GENERATION_DRIFT.value)
    if value.get("schema") == HEAD_SCHEMA:
        return _load_pointer_fields(Path(run_dir), value, tuple(keys))
    return {key: value[key] for key in keys if key in value}

from ._state_dag.persistence import (
    _replay_immutable_generation, _verified_persisted_receipt, head_summary,
    migrate_current_head, persist,
)
from ._state_dag.history import migrate_history, main

if __name__ == "__main__":
    raise SystemExit(main())
