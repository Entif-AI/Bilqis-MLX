"""Sharded teacher-miss, exposure, and epoch-history encoding."""
from __future__ import annotations

import json
from pathlib import Path

from .contracts import (
    EXPOSURE_SHARD_PREFIX_LENGTH, TEACHER_MISS_SHARD_PREFIX_LENGTH,
    StateDagError, _canonical, _get_object, _put_object,
)

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

def _teacher_miss_subshards(rows: list) -> dict[str, dict[str, list]]:
    result: dict[str, dict[str, list]] = {}
    for capability, members in _teacher_miss_shards(rows).items():
        prefixes: dict[str, list] = {}
        for row in members:
            identity = row["id"]
            if len(identity) < TEACHER_MISS_SHARD_PREFIX_LENGTH:
                raise ValueError(StateDagError.TEACHER_MISS_INVALID.value)
            prefixes.setdefault(
                identity[:TEACHER_MISS_SHARD_PREFIX_LENGTH], []).append(row)
        result[capability] = prefixes
    return result

def _encode_teacher_misses(run_dir: Path, rows: list, *, prior_spec=None,
                           prior_rows=None) -> tuple[dict, list]:
    shards = _teacher_miss_subshards(rows)
    prior_shards = _teacher_miss_subshards(prior_rows or [])
    prior_encoded = (prior_spec.get("shards", {})
                     if isinstance(prior_spec, dict) and
                     prior_spec.get("kind") == "teacher-misses/v2" else {})
    encoded = {}
    normalized = []
    for capability, prefixes in sorted(shards.items()):
        encoded[capability] = {}
        for prefix, members in sorted(prefixes.items()):
            if (prior_shards.get(capability, {}).get(prefix) == members and
                    prefix in prior_encoded.get(capability, {})):
                encoded[capability][prefix] = prior_encoded[capability][prefix]
                normalized.extend(prior_shards[capability][prefix])
                continue
            canonical_members = json.loads(_canonical(members))
            encoded[capability][prefix] = _put_object(run_dir, canonical_members)
            normalized.extend(canonical_members)
    normalized.sort(key=lambda row: (row["capability"], row["id"]))
    return ({"kind": "teacher-misses/v2", "count": len(normalized),
             "shards": encoded}, normalized)

def _decode_teacher_misses(run_dir: Path, spec: dict) -> list:
    rows = []
    if spec.get("kind") == "teacher-misses/v1":
        for capability, digest in sorted(spec["shards"].items()):
            members = _get_object(run_dir, digest)
            if any(row.get("capability") != capability for row in members):
                raise ValueError(StateDagError.TEACHER_MISS_SHARD_DRIFT.value)
            rows.extend(members)
    else:
        for capability, prefixes in sorted(spec["shards"].items()):
            for prefix, digest in sorted(prefixes.items()):
                members = _get_object(run_dir, digest)
                if any(row.get("capability") != capability for row in members):
                    raise ValueError(StateDagError.TEACHER_MISS_SHARD_DRIFT.value)
                if any(not row.get("id", "").startswith(prefix) for row in members):
                    raise ValueError(StateDagError.TEACHER_MISS_PREFIX_DRIFT.value)
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

