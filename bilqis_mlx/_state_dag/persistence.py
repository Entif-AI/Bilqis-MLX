"""Generation persistence and immutable retry semantics."""
from __future__ import annotations

from pathlib import Path
import json

from bilqis_mlx.data_plane import data_plane
from .contracts import HEAD_SCHEMA, StateDagError, _FIELD_CACHE, _canonical, _durable
from .nodes import _read_pointer, _write_node

def _facade():
    import bilqis_mlx.state_dag as facade
    return facade

def _load_pointer(*args, **kwargs):
    return _facade()._load_pointer(*args, **kwargs)

def _load_pointer_fields(*args, **kwargs):
    return _facade()._load_pointer_fields(*args, **kwargs)

def read_current(*args, **kwargs):
    return _facade().read_current(*args, **kwargs)

def read_generation(*args, **kwargs):
    return _facade().read_generation(*args, **kwargs)

def migrate_current_head(run_dir: Path, receipt: dict | None = None) -> dict:
    """Replace only the mutable latest pointer; immutable old generation stays intact."""
    run_dir = Path(run_dir)
    existing = _read_pointer(run_dir / "state.json")
    if existing is not None:
        return _load_pointer(run_dir, existing)
    current = read_current(run_dir) if receipt is None else receipt
    with data_plane().transaction():
        pointer, fields, normalized = _write_node(run_dir, current, parent=None)
    _FIELD_CACHE[str(run_dir.resolve())] = {
        key: (normalized[key], spec) for key, spec in fields.items()}
    _durable(run_dir / "state.json", _canonical(pointer), replace=True)
    if _read_pointer(run_dir / "state.json") != pointer:
        raise ValueError(StateDagError.MIGRATION_READBACK_DRIFT.value)
    return normalized

def _verified_persisted_receipt(run_dir: Path, pointer: dict,
                                receipt: dict) -> tuple[dict, dict, dict]:
    """Decode a durable node without caching a candidate that might be rejected."""
    node = json.loads(data_plane().get_node(pointer["node_sha256"]))
    fields = node.get("fields")
    if not isinstance(fields, dict):
        raise ValueError(StateDagError.NODE_POINTER_DRIFT.value)
    stored = _load_pointer_fields(run_dir, pointer, tuple(fields))
    if _canonical(stored) != _canonical(receipt):
        raise ValueError(StateDagError.IMMUTABLE_GENERATION_COLLISION.value)
    return node, fields, stored

def _replay_immutable_generation(run_dir: Path, receipt: dict,
                                 generation_path: Path) -> dict | None:
    """Reuse an identical durable generation without reparenting its Merkle node."""
    pointer = _read_pointer(generation_path)
    if pointer is None:
        return None
    generation = receipt["generation"]
    current = _read_pointer(run_dir / "state.json")
    if pointer.get("generation") != generation:
        raise ValueError(StateDagError.IMMUTABLE_GENERATION_COLLISION.value)
    # A genuine retry may retain the current head or restore its immediate
    # orphan successor. An older generation must never rewind a newer head.
    if current is not None and (current != pointer and
                                current["generation"] >= generation):
        raise ValueError(StateDagError.IMMUTABLE_GENERATION_COLLISION.value)
    node, fields, stored = _verified_persisted_receipt(run_dir, pointer, receipt)
    if current != pointer:
        if current is None:
            legacy = read_current(run_dir)
            legacy_generation = legacy.get("generation")
            if (type(legacy_generation) is not int or
                    generation not in (legacy_generation, legacy_generation + 1) or
                    _canonical(read_generation(run_dir, legacy_generation)) != _canonical(legacy)):
                raise ValueError(StateDagError.IMMUTABLE_GENERATION_COLLISION.value)
            previous = _read_pointer(run_dir / "states" / f"{legacy_generation:07d}.json")
            if (generation != legacy_generation and
                    node.get("parent_sha256") not in
                    (None, previous["node_sha256"] if previous else None)):
                raise ValueError(StateDagError.IMMUTABLE_GENERATION_COLLISION.value)
        elif (current["generation"] + 1 != generation or
              node.get("parent_sha256") != current["node_sha256"]):
            raise ValueError(StateDagError.IMMUTABLE_GENERATION_COLLISION.value)
        _durable(run_dir / "state.json", _canonical(pointer), replace=True)
        if _read_pointer(run_dir / "state.json") != pointer:
            raise ValueError(StateDagError.LATEST_POINTER_NOT_DURABLE.value)
    _FIELD_CACHE[str(run_dir.resolve())] = {
        key: (stored[key], spec) for key, spec in fields.items()}
    return stored

def persist(run_dir: Path, receipt: dict) -> dict:
    """Persist a new generation or reuse identical current/immutable evidence."""
    run_dir = Path(run_dir)
    generation = receipt.get("generation")
    if type(generation) is not int or generation < 0:
        raise ValueError(StateDagError.GENERATION_INVALID.value)
    generation_path = run_dir / "states" / f"{generation:07d}.json"
    if generation_path.exists() or generation_path.is_symlink():
        previous = _replay_immutable_generation(run_dir, receipt, generation_path)
        if previous is not None:
            return previous
        if generation_path.is_symlink():
            raise ValueError(StateDagError.IMMUTABLE_GENERATION_COLLISION.value)
    current = _read_pointer(run_dir / "state.json")
    if current is not None and current["generation"] >= generation:
        if current["generation"] != generation:
            raise ValueError(StateDagError.IMMUTABLE_GENERATION_COLLISION.value)
        # A legacy head can already have a committed node before its immutable
        # generation pointer is materialized. Reuse that node, not itself as parent.
        _, fields, stored = _verified_persisted_receipt(run_dir, current, receipt)
        if generation_path.exists():
            if _canonical(read_generation(run_dir, generation)) != _canonical(stored):
                raise ValueError(StateDagError.IMMUTABLE_GENERATION_COLLISION.value)
        else:
            _durable(generation_path, _canonical(current))
            if _read_pointer(generation_path) != current:
                raise ValueError(StateDagError.GENERATION_POINTER_DRIFT.value)
        _FIELD_CACHE[str(run_dir.resolve())] = {
            key: (stored[key], spec) for key, spec in fields.items()}
        return stored
    parent = current["node_sha256"] if current is not None else None
    with data_plane().transaction():
        pointer, fields, normalized = _write_node(run_dir, receipt, parent=parent)
    pointer_raw = _canonical(pointer)
    if generation_path.exists() or generation_path.is_symlink():
        existing_pointer = _read_pointer(generation_path)
        if existing_pointer is not None:
            if existing_pointer != pointer:
                raise ValueError(StateDagError.IMMUTABLE_GENERATION_COLLISION.value)
        elif read_generation(run_dir, generation) != normalized:
            raise ValueError(StateDagError.IMMUTABLE_GENERATION_COLLISION.value)
    else:
        _durable(generation_path, pointer_raw)
    _durable(run_dir / "state.json", pointer_raw, replace=True)
    if _read_pointer(run_dir / "state.json") != pointer:
        raise ValueError(StateDagError.LATEST_POINTER_NOT_DURABLE.value)
    if _read_pointer(generation_path) not in (None, pointer):
        raise ValueError(StateDagError.GENERATION_POINTER_DRIFT.value)
    _FIELD_CACHE[str(run_dir.resolve())] = {
        key: (normalized[key], spec) for key, spec in fields.items()}
    return normalized

def head_summary(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    pointer = _read_pointer(run_dir / "state.json")
    if pointer is None:
        receipt = read_current(run_dir)
        return {"mode": "LEGACY_MONOLITH", "generation": receipt["generation"],
                "head_bytes": (run_dir / "state.json").stat().st_size}
    return {"mode": "MERKLE_DAG", **pointer,
            "head_bytes": (run_dir / "state.json").stat().st_size}

