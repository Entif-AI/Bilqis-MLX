"""Versioned MLX FP32 + AdamW snapshot codec, initially qualified on fixtures.

The external native checkpoint remains immutable. Tensor identifiers in the
safetensors file are opaque ordinal keys so historic dot-delimited parameter
names cannot be confused with MLX's tree paths. The manifest preserves exact
name/order and optimizer hyperparameters not stored inside MLX AdamW.state.

A directory is created exclusively; no checkpoint overwrite or auto-pruning.
This does not itself authorize neural updates to any real Bilqis student.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from .backup import digest_file
from .disk import assert_headroom

SCHEMA = "bilqis.mlx.fp32-adamw-bundle/v1"


def _json_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _validate_name_list(names: list[str]) -> None:
    if (not names or any(not isinstance(name, str) or not name or
                         name.startswith(".") or "\x00" in name for name in names)
            or len(names) != len(set(names))):
        raise ValueError("MLX_BUNDLE_INVALID_PARAMETER_IDENTITY")


def _fp32_array(mx, item, *, what: str):
    if not isinstance(item, mx.array) or item.dtype != mx.float32:
        raise ValueError("MLX_BUNDLE_NOT_FP32_" + what)
    return item


def save_new_bundle(destination: Path, parameters: Mapping[str, object], optimizer,
                    *, source_digest: str, reserve_gib: float = 100.0) -> dict:
    """Store an optimizer-bearing snapshot in an exclusive new directory.

    For now used by disposable fixtures only. The caller may not substitute
    this for full-history AdamW equivalence without independent comparison.
    """
    import mlx.core as mx
    names = list(parameters)
    _validate_name_list(names)
    if (len(source_digest) != 64 or
            any(x not in "0123456789abcdef" for x in source_digest)):
        raise ValueError("MLX_BUNDLE_SOURCE_DIGEST_MISSING")
    if not optimizer.bias_correction:
        raise ValueError("MLX_BUNDLE_REQUIRES_BIAS_CORRECTED_ADAMW")
    state = optimizer.state
    if set(state) != {"step", "learning_rate", *names}:
        raise ValueError("MLX_BUNDLE_OPTIMIZER_STATE_NOT_COMPLETE")
    if not (0 < len(names) <= 4096):
        raise ValueError("MLX_BUNDLE_TOO_MANY_PARAMETERS")
    arrays = {}
    expected_bytes = 0
    for i, name in enumerate(names):
        param = _fp32_array(mx, parameters[name], what="PARAMETER")
        cell = state[name]
        if set(cell) != {"m", "v"}:
            raise ValueError("MLX_BUNDLE_MISSING_ADAMW_MOMENTS")
        for field, arr in (("weight", param), ("m", cell["m"]), ("v", cell["v"])):
            arr = _fp32_array(mx, arr, what="MOMENT")
            if arr.shape != param.shape:
                raise ValueError("MLX_BUNDLE_PARAM_MOMENT_SHAPE_DRIFT")
            key = f"p{i:04d}_{field}"
            arrays[key] = arr
            expected_bytes += arr.size * arr.itemsize
    arrays["adamw_global_step"] = state["step"]
    arrays["adamw_learning_rate"] = state["learning_rate"]
    if arrays["adamw_global_step"].dtype != mx.uint64:
        raise ValueError("MLX_BUNDLE_OPTIMIZER_STEP_DTYPE_DRIFT")
    if arrays["adamw_learning_rate"].dtype != mx.float32:
        raise ValueError("MLX_BUNDLE_LEARNING_RATE_DTYPE_DRIFT")
    mx.eval(arrays)
    manifest = {
        "schema": SCHEMA,
        "source_digest": source_digest,
        "parameter_names": names,
        "name_order_sha256": _json_hash(names),
        "optimizer": {"algorithm": "AdamW", "betas": list(optimizer.betas),
                      "eps": optimizer.eps, "weight_decay": optimizer.weight_decay,
                      "bias_correction": optimizer.bias_correction},
        "optimizer_step": int(state["step"].item()),
        "tensor_count": len(arrays),
        "uncompressed_parameter_and_moment_bytes": expected_bytes,
    }
    destination = Path(destination)
    assert_headroom(destination, required_bytes=expected_bytes*2+65536, reserve_gib=reserve_gib)
    destination.mkdir(parents=True, exist_ok=False)
    data_path = destination / "model-and-own-adamw.safetensors"
    mx.save_safetensors(str(data_path), arrays)
    manifest["safetensors_sha256"] = digest_file(data_path)
    (destination / "manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    # Verify bytes and every restored identity in the same call.
    restored_parameters, restored_optimizer, restored_manifest = load_bundle(destination)
    if list(restored_parameters) != names or restored_manifest != manifest:
        raise ValueError("MLX_BUNDLE_POSTWRITE_READBACK_DRIFT")
    mx.eval(restored_parameters, restored_optimizer.state)
    return manifest


def load_bundle(destination: Path):
    """Read and verify complete optimizer + weights; never implicitly train."""
    import mlx.core as mx
    import mlx.optimizers as optim
    destination = Path(destination)
    manifest = json.loads((destination/"manifest.json").read_text())
    if manifest.get("schema") != SCHEMA:
        raise ValueError("MLX_BUNDLE_SCHEMA_DRIFT")
    names = manifest.get("parameter_names")
    if not isinstance(names,list):
        raise ValueError("MLX_BUNDLE_NAMES_MISSING")
    _validate_name_list(names)
    if _json_hash(names) != manifest["name_order_sha256"]:
        raise ValueError("MLX_BUNDLE_PARAMETER_ORDER_DRIFT")
    blob = destination / "model-and-own-adamw.safetensors"
    if digest_file(blob) != manifest["safetensors_sha256"]:
        raise ValueError("MLX_BUNDLE_TENSOR_FILE_CORRUPTED")
    arrays = mx.load(str(blob))
    expected = {f"p{i:04d}_{part}" for i in range(len(names))
                for part in ("weight","m","v")}
    expected.update(("adamw_global_step","adamw_learning_rate"))
    if set(arrays) != expected or manifest["tensor_count"] != len(arrays):
        raise ValueError("MLX_BUNDLE_MISSING_OR_EXTRA_TENSORS")
    params = {}
    state = {"step":arrays["adamw_global_step"],
             "learning_rate":arrays["adamw_learning_rate"]}
    for i,name in enumerate(names):
        key=f"p{i:04d}"
        weight=_fp32_array(mx,arrays[key+"_weight"],what="WEIGHT")
        m=_fp32_array(mx,arrays[key+"_m"],what="MOMENT")
        v=_fp32_array(mx,arrays[key+"_v"],what="MOMENT")
        if weight.shape != m.shape or weight.shape != v.shape:
            raise ValueError("MLX_BUNDLE_RESTORED_MOMENT_SHAPE_DRIFT")
        params[name]=weight
        state[name]={"m":m,"v":v}
    if (state["step"].dtype != mx.uint64 or
            int(state["step"].item()) != manifest["optimizer_step"]):
        raise ValueError("MLX_BUNDLE_RESTORED_OPTIMIZER_STEP_DRIFT")
    hp=manifest["optimizer"]
    if hp.get("algorithm") != "AdamW" or hp.get("bias_correction") is not True:
        raise ValueError("MLX_BUNDLE_UNSUPPORTED_OPTIMIZER_CONFIG")
    restored=optim.AdamW(learning_rate=float(state["learning_rate"].item()),
                         betas=hp["betas"], eps=hp["eps"],
                         weight_decay=hp["weight_decay"],bias_correction=True)
    restored.state=state
    mx.eval(params, restored.state)
    return params,restored,manifest
