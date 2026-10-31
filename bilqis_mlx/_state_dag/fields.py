"""Logical field dispatcher for state-DAG receipts."""
from __future__ import annotations

from pathlib import Path

from .contracts import INLINE_FIELD_LIMIT_BYTES, StateDagError, _canonical, _put_object, _get_object, _error
from .field_collections import (
    _decode_epoch_history, _decode_exposures, _decode_teacher_misses,
    _encode_epoch_history, _encode_exposures, _encode_teacher_misses,
)
from .teacher_fields import _decode_teacher, _encode_teacher

def _encode_field(run_dir: Path, key: str, value):
    if key == "teacher_misses" and isinstance(value, list):
        return _encode_teacher_misses(run_dir, value)[0]
    if key == "teacher_miss_exposures" and isinstance(value, dict):
        return _encode_exposures(run_dir, value)[0]
    if key == "championship_epoch_history" and isinstance(value, list):
        return _encode_epoch_history(run_dir, value)[0]
    if key == "teacher" and isinstance(value, dict):
        return _encode_teacher(run_dir, value)[0]
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
    if kind in ("teacher-misses/v1", "teacher-misses/v2"):
        return _decode_teacher_misses(run_dir, spec)
    if kind == "teacher-miss-exposures/v1":
        return _decode_exposures(run_dir, spec)
    if kind == "object-list/v1":
        return _decode_epoch_history(run_dir, spec)
    if kind == "teacher/v2":
        return _decode_teacher(run_dir, spec)
    raise ValueError(_error(StateDagError.FIELD_KIND_UNKNOWN, kind))


# Bind the original late field-dispatch seam after both modules initialize.
from . import teacher_fields as _teacher_fields
_teacher_fields._decode_field = _decode_field
