"""Exact numerical digests for historical AdamW migration authority."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Mapping

import numpy as np

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.optimizer_count_geometry import declared_update_count_shape


UINT64_MAX = int(np.iinfo(np.uint64).max)


def invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def is_sha256(value):
    return (isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


def parameter_order_tuple(parameter_order, model_weights) -> tuple[str, ...]:
    try:
        names = tuple(parameter_order)
    except TypeError:
        invalid()
    if (not isinstance(model_weights, Mapping) or not names
            or any(type(name) is not str or not name for name in names)
            or len(names) != len(set(names)) or set(names) != set(model_weights)):
        invalid()
    return names


def historical_model_state_digest(model_weights, *, parameter_order) -> str:
    """Digest exact ordered native FP32 weights without serializing authority."""
    names = parameter_order_tuple(parameter_order, model_weights)
    digest = hashlib.sha256()
    for name in names:
        value = model_weights[name]
        try:
            array = np.ascontiguousarray(value.detach().cpu().numpy())
        except (AttributeError, TypeError, ValueError):
            invalid()
        if str(value.dtype) != "torch.float32" or array.dtype != np.float32:
            invalid()
        digest.update(json.dumps(
            [name, list(array.shape), str(array.dtype)],
            separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        digest.update(b"\0")
        digest.update(array.tobytes(order="C"))
        digest.update(b"\0")
    return digest.hexdigest()


def historical_optimizer_state_digest(
        optimizer_state, model_weights, *, parameter_order) -> str:
    """Digest native AdamW configuration, moments and exact integral steps."""
    names = parameter_order_tuple(parameter_order, model_weights)
    if (not isinstance(optimizer_state, Mapping)
            or set(optimizer_state) != {"state", "param_groups"}
            or not isinstance(optimizer_state["state"], Mapping)
            or type(optimizer_state["param_groups"]) is not list
            or len(optimizer_state["param_groups"]) != 1):
        invalid()
    group = optimizer_state["param_groups"][0]
    if not isinstance(group, Mapping):
        invalid()
    param_ids = group.get("params")
    if (type(param_ids) is not list or len(param_ids) != len(names)
            or len(param_ids) != len(set(param_ids))
            or set(optimizer_state["state"]) != set(param_ids)):
        invalid()
    config = {name: value for name, value in group.items() if name != "params"}
    digest = hashlib.sha256()
    try:
        digest.update(json.dumps(
            config, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError):
        invalid()
    digest.update(b"\0")
    for pid, name in zip(param_ids, names):
        cell = optimizer_state["state"][pid]
        if not isinstance(cell, Mapping) or set(cell) != {"step", "exp_avg", "exp_avg_sq"}:
            invalid()
        try:
            step_array = np.asarray(cell["step"].detach().cpu().numpy())
            step_value = float(step_array.item())
            first = np.ascontiguousarray(cell["exp_avg"].detach().cpu().numpy())
            second = np.ascontiguousarray(cell["exp_avg_sq"].detach().cpu().numpy())
        except (AttributeError, TypeError, ValueError, OverflowError):
            invalid()
        if (step_array.shape != () or not math.isfinite(step_value)
                or step_value < 0 or step_value > UINT64_MAX
                or step_value != math.floor(step_value)):
            invalid()
        weight = model_weights[name]
        if (tuple(first.shape) != tuple(weight.shape)
                or tuple(second.shape) != tuple(weight.shape)
                or first.dtype != np.float32 or second.dtype != np.float32):
            invalid()
        digest.update(json.dumps(
            [name, int(step_value), str(step_array.dtype), list(step_array.shape),
             list(first.shape)], separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8"))
        digest.update(b"\0")
        for array in (step_array, first, second):
            digest.update(array.tobytes(order="C"))
            digest.update(b"\0")
    return digest.hexdigest()


def historical_count_geometry_digest(declared) -> str:
    """Bind authority to exact B01 parameter and count geometry."""
    try:
        items = tuple(declared)
        record = [{
            "name": item.name,
            "parameter_shape": list(item.shape),
            "count_shape": list(declared_update_count_shape(item)),
        } for item in items]
    except (AttributeError, TypeError, ValueError):
        invalid()
    if not items or len({item["name"] for item in record}) != len(record):
        invalid()
    wire = json.dumps(
        record, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(wire).hexdigest()


def checkpoint_digest(path) -> str:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        invalid()
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        invalid()
    return digest.hexdigest()
