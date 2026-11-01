"""Teacher-specific state-DAG field encoding."""
from __future__ import annotations

import json
from pathlib import Path

from .contracts import INLINE_FIELD_LIMIT_BYTES, StateDagError, _canonical, _get_object, _put_object

def _encode_generic_value(run_dir: Path, value) -> tuple[dict, object]:
    normalized = json.loads(_canonical(value))
    raw = _canonical(normalized)
    if len(raw) <= INLINE_FIELD_LIMIT_BYTES:
        return {"kind": "inline/v1", "value": normalized}, normalized
    return ({"kind": "object/v1", "sha256": _put_object(run_dir, normalized)},
            normalized)

def _encode_teacher_contexts(run_dir: Path, contexts: dict, *, prior_spec=None,
                             prior_contexts=None) -> tuple[dict, dict]:
    if not isinstance(contexts, dict):
        raise ValueError(StateDagError.TEACHER_CONTEXTS_INVALID.value)
    prior_contexts = prior_contexts if isinstance(prior_contexts, dict) else {}
    prior_items = (prior_spec.get("items", {})
                   if isinstance(prior_spec, dict) and
                   prior_spec.get("kind") == "teacher-context-map/v1" else {})
    items = {}
    normalized = {}
    for identity, context in sorted(contexts.items()):
        if not isinstance(identity, str):
            raise ValueError(StateDagError.TEACHER_CONTEXTS_INVALID.value)
        if identity in prior_items and prior_contexts.get(identity) == context:
            items[identity] = prior_items[identity]
            normalized[identity] = prior_contexts[identity]
            continue
        canonical_context = json.loads(_canonical(context))
        items[identity] = _put_object(run_dir, canonical_context)
        normalized[identity] = canonical_context
    return ({"kind": "teacher-context-map/v1", "count": len(normalized),
             "items": items}, normalized)

def _decode_teacher_contexts(run_dir: Path, spec: dict) -> dict:
    result = {identity: _get_object(run_dir, digest)
              for identity, digest in sorted(spec["items"].items())}
    if len(result) != spec["count"]:
        raise ValueError(StateDagError.TEACHER_CONTEXT_COUNT_DRIFT.value)
    return result

def _encode_teacher(run_dir: Path, teacher: dict, *, prior_spec=None,
                    prior_teacher=None) -> tuple[dict, dict]:
    prior_teacher = prior_teacher if isinstance(prior_teacher, dict) else {}
    prior_fields = (prior_spec.get("fields", {})
                    if isinstance(prior_spec, dict) and
                    prior_spec.get("kind") == "teacher/v2" else {})
    fields = {}
    normalized = {}
    for key, value in sorted(teacher.items()):
        previous = prior_teacher.get(key)
        previous_spec = prior_fields.get(key)
        if previous_spec is not None and previous == value:
            fields[key] = previous_spec
            normalized[key] = previous
            continue
        if key == "causal_experiment" and isinstance(value, dict):
            causal_fields = {}
            causal_normalized = {}
            prior_causal = previous if isinstance(previous, dict) else {}
            prior_causal_fields = (
                previous_spec.get("fields", {})
                if isinstance(previous_spec, dict) and
                previous_spec.get("kind") == "teacher-causal-experiment/v1" else {})
            for causal_key, causal_value in sorted(value.items()):
                old_value = prior_causal.get(causal_key)
                old_spec = prior_causal_fields.get(causal_key)
                if old_spec is not None and old_value == causal_value:
                    causal_fields[causal_key] = old_spec
                    causal_normalized[causal_key] = old_value
                elif causal_key == "contexts":
                    causal_fields[causal_key], causal_normalized[causal_key] = (
                        _encode_teacher_contexts(
                            run_dir, causal_value, prior_spec=old_spec,
                            prior_contexts=old_value))
                else:
                    causal_fields[causal_key], causal_normalized[causal_key] = (
                        _encode_generic_value(run_dir, causal_value))
            fields[key] = {"kind": "teacher-causal-experiment/v1",
                           "fields": causal_fields}
            normalized[key] = causal_normalized
            continue
        fields[key], normalized[key] = _encode_generic_value(run_dir, value)
    return {"kind": "teacher/v2", "fields": fields}, normalized

def _decode_teacher(run_dir: Path, spec: dict) -> dict:
    result = {}
    for key, field in sorted(spec["fields"].items()):
        if field.get("kind") == "teacher-causal-experiment/v1":
            causal = {}
            for causal_key, causal_field in sorted(field["fields"].items()):
                if causal_field.get("kind") == "teacher-context-map/v1":
                    causal[causal_key] = _decode_teacher_contexts(
                        run_dir, causal_field)
                else:
                    causal[causal_key] = _decode_field(run_dir, causal_field)
            result[key] = causal
        else:
            result[key] = _decode_field(run_dir, field)
    return result
