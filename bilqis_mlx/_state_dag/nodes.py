"""Merkle node construction and pointer primitives."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.data_plane import data_plane
from .contracts import HEAD_SCHEMA, NODE_SCHEMA, StateDagError, _FIELD_CACHE, _canonical, _sha
from .field_collections import _encode_epoch_history, _encode_exposures, _encode_teacher_misses
from .teacher_fields import _encode_teacher
from .fields import _encode_field

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
        if key == "teacher" and isinstance(value, dict):
            fields[key], normalized[key] = _encode_teacher(
                run_dir, value,
                prior_spec=cached[1] if cached is not None else None,
                prior_teacher=cached[0] if cached is not None else None)
            continue
        if cached is not None and cached[0] == value:
            normalized[key] = cached[0]
            fields[key] = cached[1]
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

