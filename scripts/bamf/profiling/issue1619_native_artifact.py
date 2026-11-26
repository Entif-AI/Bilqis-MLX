"""Disposable B13 projection reuse across real AdamW rollback and custody."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.data_plane import DataPlane, close_data_planes
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import (
    continue_generation, retained_digest,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    NAME, candidate, parent_state, publish_candidate, rejected_state, shape_patch,
)
from scripts.bamf.profiling.issue1619_cache_economics import (
    TRIALS, digest, encode, read, timed, write,
)

MODULE = "scripts.bamf.profiling.issue1619_native_artifact"
COUNT = 4096
MEMORY_LIMIT = 2 * 1024**3


def load(run):
    with shape_patch():
        return load_bamf_generation(run / "bamf-state.json")


def identity(run, student, revision):
    pointer = json.loads((run / "bamf-state.json").read_bytes())
    parameter = student.retained_state.optimizer.parameters[NAME]
    return {
        "kind": "detached-identity-gather/fp32/v1",
        "branch_revision": revision, "generation": student.generation,
        "manifest": pointer["manifest_sha256"],
        "state_revision": retained_digest(student.retained_state),
        "parameter": NAME, "parameter_revision": digest(np.asarray(parameter).tobytes()),
        "source": student.correction_frontier,
        "semantic_abi": student.semantic_abi, "compiler": student.compiler_features,
        "geometry": {"parameter_shape": list(parameter.shape), "dtype": "float32",
                     "output_shape": [COUNT, 2]},
        "scope": "disposable-fixed-panel",
        "indices": digest(np.arange(COUNT, dtype=np.int32).__mod__(2).tobytes()),
    }


def compute(state, indices):
    result = mx.take(state.optimizer.parameters[NAME], indices, axis=0)
    mx.eval(result)
    return result


def serialize(value):
    return {"fp32": base64.b64encode(np.asarray(value, dtype=np.float32).tobytes()).decode()}


def restore(plane, dependency):
    record = read(plane, dependency)
    if record is None:
        return None
    raw = base64.b64decode(record["fp32"], validate=True)
    expected_shape = dependency["geometry"]["output_shape"]
    if len(raw) != int(np.prod(expected_shape)) * 4:
        raise ValueError("invalid FP32 payload geometry")
    value = mx.array(np.frombuffer(raw, dtype=np.float32).reshape(expected_shape))
    mx.eval(value)
    return value


def assert_exact(value, expected):
    if value is None or not np.array_equal(np.asarray(value), np.asarray(expected)):
        raise AssertionError("native artifact mismatch")


def cold(run, path, revision):
    student = load(run)
    dependency, bind_ns = timed(lambda: identity(run, student, revision))
    plane, open_ns = timed(lambda: DataPlane(path))
    try:
        value, read_ns = timed(lambda: restore(plane, dependency))
        if value is None:
            return {"hit": False, "binding_ns": bind_ns, "open_ns": open_ns,
                    "read_ns": read_ns}
        expected = compute(student.retained_state, mx.arange(COUNT) % 2)
        assert_exact(value, expected)
        return {"hit": True, "binding_ns": bind_ns, "open_ns": open_ns,
                "read_ns": read_ns, "payload_sha256": digest(np.asarray(value).tobytes())}
    finally:
        plane.close()


def cold_process(run, path, revision):
    result, elapsed = timed(lambda: subprocess.check_output(
        [sys.executable, "-B", "-m", MODULE, str(run), str(path), revision],
        text=True, timeout=120))
    return {**json.loads(result), "process_wall_ns": elapsed}


def measure_native_arms(plane, dep, parent, indices, reference):
    recompute, memory, durable = [], [], []
    memory_cache = {digest(encode(dep)): reference}
    for _ in range(TRIALS):
        value, elapsed = timed(lambda: compute(parent, indices))
        assert_exact(value, reference)
        recompute.append(elapsed)
        value, elapsed = timed(lambda: memory_cache.get(digest(encode(dep))))
        assert_exact(value, reference)
        memory.append(elapsed)
    payload, transfer_ns = timed(lambda: serialize(reference))
    _, write_ns = timed(lambda: write(plane, dep, payload))
    for _ in range(TRIALS):
        value, elapsed = timed(lambda: restore(plane, dep))
        assert_exact(value, reference)
        durable.append(elapsed)
    return recompute, memory, durable, transfer_ns, write_ns


def verify_native_lifecycle(plane, run, path, revision, student, dep, indices, reference):
    parent = student.retained_state
    rejected, reject_ns = timed(lambda: rejected_state(parent, student.extents))
    if rejected is not parent or retained_digest(rejected) != dep["state_revision"]:
        raise AssertionError("rollback changed parent")
    if identity(run, load(run), revision) != dep:
        raise AssertionError("rollback changed accepted identity")
    assert_exact(restore(plane, dep), reference)

    invalidations = {}
    for field in ("branch_revision", "manifest", "state_revision",
                  "parameter_revision", "source", "semantic_abi",
                  "compiler", "geometry", "scope", "indices"):
        changed = {**dep, field: "invalidated"}
        result, elapsed = timed(lambda: restore(plane, changed))
        if result is not None:
            raise AssertionError(field)
        invalidations[field] = elapsed
    before = cold_process(run, path, revision)
    if not before["hit"] or before["payload_sha256"] != digest(np.asarray(reference).tobytes()):
        raise AssertionError("cold B13 restoration mismatch")
    with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
        update = continue_generation(run)
    successor = load(run)
    after_dep, after_bind_ns = timed(lambda: identity(run, successor, revision))
    if after_dep["generation"] != dep["generation"] + 1:
        raise AssertionError("accepted successor missing")
    if after_dep["parameter_revision"] == dep["parameter_revision"]:
        raise AssertionError("fixture did not change dependent parameter")
    if restore(plane, after_dep) is not None:
        raise AssertionError("changed parent cache hit")
    changed_value = compute(successor.retained_state, indices)
    if np.array_equal(np.asarray(changed_value), np.asarray(reference)):
        raise AssertionError("fixture did not change numerical output")
    after = cold_process(run, path, revision)
    if after["hit"]:
        raise AssertionError("cold successor used old artifact")
    return reject_ns, invalidations, before, update, after_dep, after_bind_ns, after


def native_economics(root, revision):
    mx.set_memory_limit(MEMORY_LIMIT)
    mx.set_cache_limit(0)
    mx.reset_peak_memory()
    run = root / "run"
    path = root / "projection.sqlite3"
    with patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(root / "custody.sqlite3")}):
        try:
            with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
                publish_candidate(run, candidate(parent_state()))
            student = load(run)
            parent = student.retained_state
            dep, bind_ns = timed(lambda: identity(run, student, revision))
            indices = mx.arange(COUNT) % 2
            mx.eval(indices)
            reference = compute(parent, indices)
            plane = DataPlane(path)
            try:
                recompute, memory, durable, transfer_ns, write_ns = measure_native_arms(
                    plane, dep, parent, indices, reference)
                (reject_ns, invalidations, before, update, after_dep,
                 after_bind_ns, after) = verify_native_lifecycle(
                    plane, run, path, revision, student, dep, indices, reference)
                stats = plane.stats()
            finally:
                plane.close()
        finally:
            close_data_planes()
    return {
        "scope": "native MLX gather of disposable B13 identity tensor; not a training graph",
        "device": str(mx.default_device()), "trials": TRIALS, "rows": COUNT,
        "parent_identity": dep, "successor_identity": after_dep,
        "binding_ns": bind_ns, "successor_binding_ns": after_bind_ns,
        "recompute_ns": recompute, "memory_ns": memory, "durable_ns": durable,
        "memory_hits": TRIALS, "durable_hits": TRIALS,
        "transfer_and_encode_ns": transfer_ns, "write_ns": write_ns,
        "memory_saved_ns_after_population": sum(recompute) - sum(memory) - recompute[0],
        "durable_saved_ns_after_population": (
            sum(recompute) - sum(durable) - recompute[0] - transfer_ns - write_ns),
        "raw_tensor_bytes": COUNT * 2 * 4, "plane_stats": stats,
        "rollback_retained_parent": True, "rollback_ns": reject_ns,
        "invalidations_ns": invalidations, "changed_parent_miss": True,
        "cold_parent": before, "cold_successor": after,
        "peak_mlx_bytes": mx.get_peak_memory(), "memory_limit_bytes": MEMORY_LIMIT,
        "optimizer_step_before": update["optimizer_step"],
        "optimizer_step_after": update["successor_optimizer_step"],
        "probe_loss_before": update["probe_loss_before"],
        "probe_loss_after": update["probe_loss_after"],
        "native_teacher_trials_per_hour": None,
        "fixed_independent_competence_change_per_hour": None,
        "training_graph_reuse": "not measured or authorized by detached artifact evidence",
    }


if __name__ == "__main__":
    mx.set_memory_limit(MEMORY_LIMIT)
    mx.set_cache_limit(0)
    print(json.dumps(cold(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])))
