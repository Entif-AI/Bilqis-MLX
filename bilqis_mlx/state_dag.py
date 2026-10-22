"""Content-addressed immutable DAG for School50 resumable state.

The live head and per-generation files are tiny pointers. Logical receipt fields
are immutable Merkle objects, so unchanged state is shared across generations.
Legacy monolithic JSON remains readable for migration and old evidence.
"""
from __future__ import annotations

import gzip
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
_FIELD_CACHE: dict[str, dict[str, tuple[object, dict]]] = dict()
class StateDagError(str, Enum):
    DESTINATION_COLLISION = "STATE_DAG_DESTINATION_COLLISION"
    OBJECT_DIGEST_INVALID = "STATE_DAG_OBJECT_DIGEST_INVALID"
    TEACHER_MISS_INVALID = "STATE_DAG_TEACHER_MISS_INVALID"
    TEACHER_MISS_CAPABILITY_INVALID = "STATE_DAG_TEACHER_MISS_CAPABILITY_INVALID"
    TEACHER_MISS_SHARD_DRIFT = "STATE_DAG_TEACHER_MISS_SHARD_DRIFT"
    TEACHER_MISS_COUNT_DRIFT = "STATE_DAG_TEACHER_MISS_COUNT_DRIFT"
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


def _teacher_miss_shards(rows: list) -> dict[str, list]:
    shards: dict[str, list] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError(StateDagError.TEACHER_MISS_INVALID.value)
        capability = row.get("capability")
        if not isinstance(capability, str) or not capability:
            raise ValueError(StateDagError.TEACHER_MISS_CAPABILITY_INVALID.value)
        shards.setdefault(capability, []).append(row)
    for capability in shards:
        shards[capability] = sorted(shards[capability], key=lambda row: row["id"])
    return shards


def _encode_teacher_misses(run_dir: Path, rows: list, *, prior_spec=None,
                           prior_rows=None) -> tuple[dict, list]:
    shards = _teacher_miss_shards(rows)
    prior_shards = _teacher_miss_shards(prior_rows or [])
    encoded = {}
    normalized = []
    for capability, members in sorted(shards.items()):
        if (isinstance(prior_spec, dict) and
                prior_spec.get("kind") == "teacher-misses/v1" and
                capability in prior_spec.get("shards", {}) and
                prior_shards.get(capability) == members):
            encoded[capability] = prior_spec["shards"][capability]
            normalized.extend(prior_shards[capability])
            continue
        canonical_members = json.loads(_canonical(members))
        encoded[capability] = _put_object(run_dir, canonical_members)
        normalized.extend(canonical_members)
    normalized.sort(key=lambda row: (row["capability"], row["id"]))
    return ({"kind": "teacher-misses/v1", "count": len(normalized),
             "shards": encoded}, normalized)


def _decode_teacher_misses(run_dir: Path, spec: dict) -> list:
    rows = []
    for capability, digest in sorted(spec["shards"].items()):
        members = _get_object(run_dir, digest)
        if any(row.get("capability") != capability for row in members):
            raise ValueError(StateDagError.TEACHER_MISS_SHARD_DRIFT.value)
        rows.extend(members)
    rows.sort(key=lambda row: (row["capability"], row["id"]))
    if len(rows) != spec["count"]:
        raise ValueError(StateDagError.TEACHER_MISS_COUNT_DRIFT.value)
    return rows


def _exposure_shards(exposures: dict) -> dict[str, dict]:
    shards: dict[str, dict] = {}
    for identity, count in exposures.items():
        if (not isinstance(identity, str) or
                len(identity) < EXPOSURE_SHARD_PREFIX_LENGTH):
            raise ValueError(StateDagError.EXPOSURE_ID_INVALID.value)
        shards.setdefault(identity[:EXPOSURE_SHARD_PREFIX_LENGTH], {})[identity] = count
    return shards


def _encode_exposures(run_dir: Path, exposures: dict, *, prior_spec=None,
                      prior_exposures=None) -> tuple[dict, dict]:
    shards = _exposure_shards(exposures)
    prior_shards = _exposure_shards(prior_exposures or {})
    encoded = {}
    normalized = {}
    for prefix, values in sorted(shards.items()):
        if (isinstance(prior_spec, dict) and
                prior_spec.get("kind") == "teacher-miss-exposures/v1" and
                prefix in prior_spec.get("shards", {}) and
                prior_shards.get(prefix) == values):
            encoded[prefix] = prior_spec["shards"][prefix]
            normalized.update(prior_shards[prefix])
            continue
        canonical_values = json.loads(_canonical(values))
        encoded[prefix] = _put_object(run_dir, canonical_values)
        normalized.update(canonical_values)
    return ({"kind": "teacher-miss-exposures/v1", "count": len(normalized),
             "shards": encoded}, normalized)


def _decode_exposures(run_dir: Path, spec: dict) -> dict:
    result = {}
    for prefix, digest in sorted(spec["shards"].items()):
        values = _get_object(run_dir, digest)
        if any(not identity.startswith(prefix) for identity in values):
            raise ValueError(StateDagError.EXPOSURE_SHARD_DRIFT.value)
        result.update(values)
    if len(result) != spec["count"]:
        raise ValueError(StateDagError.EXPOSURE_COUNT_DRIFT.value)
    return result


def _encode_epoch_history(run_dir: Path, history: list, *, prior_spec=None,
                          prior_history=None) -> tuple[dict, list]:
    prior_history = prior_history or []
    prior_items = (prior_spec.get("items", ())
                   if isinstance(prior_spec, dict) and
                   prior_spec.get("kind") == "object-list/v1" else ())
    encoded = []
    normalized = []
    for index, epoch in enumerate(history):
        if (index < len(prior_history) and index < len(prior_items) and
                prior_history[index] == epoch):
            encoded.append(prior_items[index])
            normalized.append(prior_history[index])
            continue
        canonical_epoch = json.loads(_canonical(epoch))
        encoded.append(_put_object(run_dir, canonical_epoch))
        normalized.append(canonical_epoch)
    return ({"kind": "object-list/v1", "count": len(normalized),
             "items": encoded}, normalized)


def _decode_epoch_history(run_dir: Path, spec: dict) -> list:
    result = [_get_object(run_dir, digest) for digest in spec["items"]]
    if len(result) != spec["count"]:
        raise ValueError(StateDagError.OBJECT_LIST_COUNT_DRIFT.value)
    return result


def _encode_field(run_dir: Path, key: str, value):
    if key == "teacher_misses" and isinstance(value, list):
        return _encode_teacher_misses(run_dir, value)[0]
    if key == "teacher_miss_exposures" and isinstance(value, dict):
        return _encode_exposures(run_dir, value)[0]
    if key == "championship_epoch_history" and isinstance(value, list):
        return _encode_epoch_history(run_dir, value)[0]
    raw = _canonical(value)
    if len(raw) <= INLINE_FIELD_LIMIT_BYTES:
        return {"kind": "inline/v1", "value": value}
    return {"kind": "object/v1", "sha256": _put_object(run_dir, value)}


def _decode_field(run_dir: Path, spec: dict):
    kind = spec.get("kind")
    if kind == "inline/v1":
        return spec["value"]
    if kind == "object/v1":
        return _get_object(run_dir, spec["sha256"])
    if kind == "teacher-misses/v1":
        return _decode_teacher_misses(run_dir, spec)
    if kind == "teacher-miss-exposures/v1":
        return _decode_exposures(run_dir, spec)
    if kind == "object-list/v1":
        return _decode_epoch_history(run_dir, spec)
    raise ValueError(_error(StateDagError.FIELD_KIND_UNKNOWN, kind))


def _read_pointer(path: Path) -> dict | None:
    if path.is_symlink() or not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if value.get("schema") == HEAD_SCHEMA else None


def _current_parent(run_dir: Path) -> str | None:
    pointer = _read_pointer(run_dir / "state.json")
    return pointer["node_sha256"] if pointer is not None else None


def _write_node(run_dir: Path, receipt: dict, *, parent: str | None) -> tuple[dict, dict, dict]:
    generation = receipt.get("generation")
    if type(generation) is not int or generation < 0:
        raise ValueError(StateDagError.GENERATION_INVALID.value)
    prior = _FIELD_CACHE.get(str(run_dir.resolve()), {})
    fields = {}
    normalized = {}
    for key, value in sorted(receipt.items()):
        cached = prior.get(key)
        if cached is not None and cached[0] is value:
            normalized[key] = value
            fields[key] = cached[1]
            continue
        if cached is not None and cached[0] == value:
            normalized[key] = cached[0]
            fields[key] = cached[1]
            continue
        if key == "teacher_misses" and isinstance(value, list):
            fields[key], normalized[key] = _encode_teacher_misses(
                run_dir, value,
                prior_spec=cached[1] if cached is not None else None,
                prior_rows=cached[0] if cached is not None else None)
            continue
        if key == "teacher_miss_exposures" and isinstance(value, dict):
            fields[key], normalized[key] = _encode_exposures(
                run_dir, value,
                prior_spec=cached[1] if cached is not None else None,
                prior_exposures=cached[0] if cached is not None else None)
            continue
        if key == "championship_epoch_history" and isinstance(value, list):
            fields[key], normalized[key] = _encode_epoch_history(
                run_dir, value,
                prior_spec=cached[1] if cached is not None else None,
                prior_history=cached[0] if cached is not None else None)
            continue
        canonical_value = json.loads(_canonical(value))
        normalized[key] = canonical_value
        fields[key] = _encode_field(run_dir, key, canonical_value)
    receipt_sha256 = _sha(_canonical(fields))
    node = {
        "schema": NODE_SCHEMA,
        "generation": generation,
        "parent_sha256": parent,
        "receipt_sha256": receipt_sha256,
        "fields": fields,
    }
    raw = _canonical(node)
    digest = _sha(raw)
    data_plane().put_node(digest, raw, generation, parent)
    pointer = {"schema": HEAD_SCHEMA, "generation": generation,
               "node_sha256": digest, "receipt_sha256": receipt_sha256}
    return pointer, fields, normalized


def _load_pointer(run_dir: Path, pointer: dict) -> dict:
    digest = pointer.get("node_sha256")
    raw = data_plane().get_node(digest)
    node = json.loads(raw)
    if (node.get("schema") != NODE_SCHEMA or
            node.get("generation") != pointer.get("generation")):
        raise ValueError(StateDagError.NODE_POINTER_DRIFT.value)
    receipt = {key: _decode_field(run_dir, spec)
               for key, spec in node["fields"].items()}
    _FIELD_CACHE[str(run_dir.resolve())] = {
        key: (receipt[key], spec) for key, spec in node["fields"].items()}
    if (_sha(_canonical(node["fields"])) != node.get("receipt_sha256") or
            node.get("receipt_sha256") != pointer.get("receipt_sha256")):
        raise ValueError(StateDagError.RECEIPT_DIGEST_DRIFT.value)
    return receipt


def read_current(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    path = run_dir / "state.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError(StateDagError.CURRENT_STATE_MISSING.value)
    value = json.loads(path.read_text(encoding="utf-8"))
    return _load_pointer(run_dir, value) if value.get("schema") == HEAD_SCHEMA else value


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


def persist(run_dir: Path, receipt: dict) -> dict:
    """Persist one logical state as an immutable Merkle node plus tiny pointers."""
    run_dir = Path(run_dir)
    parent = _current_parent(run_dir)
    with data_plane().transaction():
        pointer, fields, normalized = _write_node(run_dir, receipt, parent=parent)
    _FIELD_CACHE[str(run_dir.resolve())] = {
        key: (normalized[key], spec) for key, spec in fields.items()}
    generation = normalized["generation"]
    generation_path = run_dir / "states" / f"{generation:07d}.json"
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


def _generation_numbers(run_dir: Path) -> tuple[int, ...]:
    states = Path(run_dir) / "states"
    numbers = set()
    for path in states.iterdir():
        name = path.name
        stem = (name[:-8] if name.endswith(".json.gz") else
                name[:-12] if name.endswith(".json.sha256") else
                name[:-5] if name.endswith(".json") else None)
        if stem is not None and stem.isdecimal():
            numbers.add(int(stem))
    return tuple(sorted(numbers))


def migrate_history(run_dir: Path, *, max_files: int = 0) -> dict:
    """Move legacy full-copy generation receipts into the immutable shared DAG."""
    if type(max_files) is not int or max_files < 0:
        raise ValueError(StateDagError.HISTORY_MIGRATION_BUDGET_INVALID.value)
    run_dir = Path(run_dir)
    current = read_current(run_dir)
    current_generation = current["generation"]
    migrated = reclaimed = 0
    parent = None
    for generation in _generation_numbers(run_dir):
        if generation > current_generation:
            break
        path = run_dir / "states" / f"{generation:07d}.json"
        zipped = run_dir / "states" / f"{generation:07d}.json.gz"
        proof = run_dir / "states" / f"{generation:07d}.json.sha256"
        pointer = _read_pointer(path)
        if pointer is not None:
            parent = pointer["node_sha256"]
            for stale in (zipped, proof):
                if stale.exists() and not stale.is_symlink():
                    reclaimed += stale.stat().st_size
                    stale.unlink()
            continue
        if max_files and migrated >= max_files:
            break
        receipt = read_generation(run_dir, generation)
        old_bytes = sum(
            item.stat().st_size for item in (path, zipped, proof)
            if item.exists() and not item.is_symlink())
        with data_plane().transaction():
            pointer, fields, normalized = _write_node(
                run_dir, receipt, parent=parent)
        if normalized != receipt:
            raise ValueError(StateDagError.HISTORY_NORMALIZATION_DRIFT.value)
        _durable(path, _canonical(pointer), replace=path.exists())
        if read_generation(run_dir, generation) != normalized:
            raise ValueError(StateDagError.HISTORY_READBACK_DRIFT.value)
        if generation == current_generation:
            _durable(run_dir / "state.json", _canonical(pointer), replace=True)
            _FIELD_CACHE[str(run_dir.resolve())] = {
                key: (normalized[key], spec) for key, spec in fields.items()}
        for stale in (zipped, proof):
            if stale.exists():
                if stale.is_symlink() or not stale.is_file():
                    raise ValueError(StateDagError.HISTORY_STALE_ARTIFACT_UNSAFE.value)
                stale.unlink()
        new_bytes = path.stat().st_size
        reclaimed += max(0, old_bytes - new_bytes)
        migrated += 1
        parent = pointer["node_sha256"]
    if migrated:
        directory = os.open(run_dir / "states", os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return {
        "migrated_generations": migrated,
        "estimated_reclaimed_bytes": reclaimed,
        "current_generation": current_generation,
    }


def main(argv=None) -> int:
    """Migrate or inspect the current run's state head without neural mutation."""
    import argparse
    import fcntl
    from .paths import active_run_dir

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("status", "migrate"):
        command = sub.add_parser(name)
        command.add_argument("--run-dir", type=Path, default=active_run_dir())
    history = sub.add_parser("migrate-history")
    history.add_argument("--run-dir", type=Path, default=active_run_dir())
    history.add_argument("--max-files", type=int, default=0,
                         help="0 migrates every legacy generation")
    args = parser.parse_args(argv)
    root = args.run_dir.expanduser().resolve(strict=True)
    if args.action == "status":
        print(json.dumps({**head_summary(root), "data_plane": data_plane().stats()},
                         sort_keys=True))
        return 0

    lock = root / ".grade-a-operator.lock"
    if lock.is_symlink():
        raise ValueError(StateDagError.OPERATOR_LOCK_UNSAFE.value)
    with lock.open("a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(StateDagError.HUMAN_TRAINING_ACTIVE.value) from None
        if args.action == "migrate-history":
            receipt = migrate_current_head(root)
            result = migrate_history(root, max_files=args.max_files)
            print(json.dumps({**result, "generation": receipt["generation"],
                              "data_plane": data_plane().stats()}, sort_keys=True))
        else:
            before = head_summary(root)
            receipt = migrate_current_head(root)
            after = head_summary(root)
            print(json.dumps({
                "mode": "MIGRATED" if before["mode"] != after["mode"] else "ALREADY_MIGRATED",
                "generation": receipt["generation"],
                "before": before,
                "after": after,
                "data_plane": data_plane().stats(),
            }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
