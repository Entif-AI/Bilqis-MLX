"""Run direct group/gradient/native-AdamW comparisons on an isolated M3 GPU."""
from dataclasses import replace
import json
import statistics
import time

import mlx.core as mx
import numpy as np

from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWHyperparameters, AdamWStateTree, _adamw_update,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from scripts.bamf.profiling.issue1616.backbone import (
    CAPACITY, CompiledGroups, STOCK, cache_tensors,
)


from scripts.bamf.profiling.issue1616.backward import standalone_backward


SPEC = ModelTopologySpecV2()
EXTENTS = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
HP = AdamWHyperparameters(.00013, (.9, .95), 1e-8, .01)
RTOL, ATOL = 1e-4, 1e-6


class Comparison:
    def __init__(self):
        self.records = {}

    def check(self, kind, left, right):
        a, b = np.asarray(left), np.asarray(right)
        assert a.shape == b.shape and a.dtype == b.dtype, kind
        record = self.records.setdefault(kind, {
            "tensors": 0, "exact": 0, "max_absolute_error": 0.0,
            "max_tolerance_fraction": 0.0,
        })
        record["tensors"] += 1
        record["exact"] += int(np.array_equal(a, b))
        if a.dtype.kind != "f":
            np.testing.assert_array_equal(a, b, err_msg=kind)
            return
        assert np.isfinite(a).all() and np.isfinite(b).all(), kind
        delta = np.abs(a - b)
        record["max_absolute_error"] = max(
            record["max_absolute_error"], float(delta.max(initial=0)))
        fraction = delta / (ATOL + RTOL * np.abs(a))
        record["max_tolerance_fraction"] = max(
            record["max_tolerance_fraction"], float(fraction.max(initial=0)))
        assert float(fraction.max(initial=0)) <= 1, (
            kind, record["max_tolerance_fraction"], record["max_absolute_error"])


def parameters(rng):
    return {
        item.name: (mx.ones(item.shape, dtype=mx.float32)
                    if item.name.endswith("_norm") else
                    mx.array(rng.normal(0, .01, item.shape).astype(np.float32)))
        for item in expected_bamf_shapes(SPEC, EXTENTS)
        if item.name.startswith("blocks.") and int(item.name.split(".")[1]) < 4
    }


def inputs(rng, length, *, changed=False, starts=False, extent=EXTENTS):
    hidden = mx.array(rng.normal(0, .1, (2, length, SPEC.width)).astype(np.float32))
    scope = np.zeros((2, length), np.int32)
    valid = np.ones((2, length), bool)
    boundaries = np.zeros((2, length), bool)
    if changed:
        hidden = hidden + .2
        scope[0, 2:] = 1
        valid[1, -1] = False
    if starts:
        boundaries[0, 2] = True
    return hidden, dict(
        group_index=1, spec=SPEC, extents=extent, scope_ids=mx.array(scope),
        valid=mx.array(valid), generation=("f" if changed else "d") * 64,
        prefix_digest=("a" if changed else "e") * 64,
        sequence_starts=mx.array(boundaries) if starts else None)


def _objective(run, kwargs):
    def loss(params, hidden):
        return mx.mean(run(hidden, params, **kwargs).hidden ** 2)
    return mx.value_and_grad(loss, argnums=(0, 1))


def measured_gradient(fn, params, hidden):
    mx.synchronize()
    started = time.perf_counter()
    value, grad = fn(params, hidden)
    mx.eval(value, grad)
    mx.synchronize()
    return value, grad, time.perf_counter() - started


def compare_case(check, compiled, params, hidden, kwargs):
    left, right = STOCK(hidden, params, **kwargs), compiled(hidden, params, **kwargs)
    check.check("hidden", left.hidden, right.hidden)
    for a, b in zip(left.attention_caches, right.attention_caches, strict=True):
        assert a.to_record() == b.to_record()
        assert all(x() is y() and x() is not None for x, y in
                   zip(a.parameter_identity, b.parameter_identity, strict=True))
        for x, y in zip(cache_tensors(a), cache_tensors(b), strict=True):
            check.check("cache", x, y)
    left_grad = _objective(STOCK, kwargs)
    right_grad = _objective(compiled, kwargs)
    loss_a, (grad_a, input_a), _ = measured_gradient(left_grad, params, hidden)
    loss_b, (grad_b, input_b), _ = measured_gradient(right_grad, params, hidden)
    check.check("loss", loss_a, loss_b)
    check.check("hidden_gradient", input_a, input_b)
    assert set(grad_a) == set(grad_b) == set(params)
    for name in params:
        check.check("parameter_gradient", grad_a[name], grad_b[name])
    zero = {name: mx.zeros_like(value) for name, value in params.items()}
    counts = {name: mx.array(0, dtype=mx.uint64) for name in params}
    parent = AdamWStateTree(params, zero, zero, counts)
    masks = {name: mx.array(True) for name in params}
    decay = {name: value.ndim == 2 for name, value in params.items()}
    a = _adamw_update(parent, grad_a, masks, HP, decay=decay)
    b = _adamw_update(parent, grad_b, masks, HP, decay=decay)
    for field in ("parameters", "m", "v", "update_counts"):
        for name in params:
            check.check("adamw_" + field, getattr(a, field)[name], getattr(b, field)[name])
    return float(loss_a), float(loss_b)


def check_eviction():
    owner = CompiledGroups("fixture")
    for key in range(1, CAPACITY + 1):
        owner._get(key, lambda: object())
    first = owner.cache[1]
    assert owner._get(1, lambda: None) is first
    owner._get(CAPACITY + 1, lambda: object())
    assert len(owner.cache) == CAPACITY and 1 in owner.cache and 2 not in owner.cache


def check_isolation(check, compiled, params, rng):
    hidden, kwargs = inputs(rng, 4)
    extended = mx.concatenate((hidden, mx.full((2, 1, SPEC.width), 100.0)), axis=1)
    longer = dict(kwargs, scope_ids=mx.zeros((2, 5), dtype=mx.int32),
                  valid=mx.ones((2, 5), dtype=mx.bool_))
    for fn in (STOCK, compiled):
        before = fn(hidden, params, **kwargs).hidden
        after = fn(extended, params, **longer).hidden
        check.check("causal_prefix", before, after[:, :4])
        starts = mx.array([[False, False, True, False]] * 2)
        reset = dict(kwargs, sequence_starts=starts)
        changed = mx.concatenate((hidden[:, :2] + 100, hidden[:, 2:]), axis=1)
        before = fn(hidden, params, **reset).hidden
        after = fn(changed, params, **reset).hidden
        check.check("reset_suffix", before[:, 2:], after[:, 2:])


def benchmark(params, hidden, kwargs):
    results = {}
    for mode, fn in (("stock", STOCK), ("compiled", CompiledGroups("benchmark"))):
        objective = _objective(fn, kwargs)
        mx.eval(params, hidden)
        mx.clear_cache()
        mx.reset_peak_memory()
        samples = [measured_gradient(objective, params, hidden)[2] for _ in range(4)]
        results[mode] = {
            "cold_seconds": samples[0], "warm_seconds": samples[1:],
            "warm_median_seconds": statistics.median(samples[1:]),
            "peak_bytes": mx.get_peak_memory(),
            "compile": fn.stats() if mode == "compiled" else None,
        }
    return results


def main():
    mx.set_default_device(mx.gpu)
    mx.set_memory_limit(8 * 1024**3)
    mx.set_cache_limit(0)
    rng = np.random.default_rng(587)
    params = parameters(rng)
    owner = CompiledGroups("release-a")
    check = Comparison()
    check_eviction()
    cases = (
        (owner, params, inputs(rng, 4)),
        (owner, {name: value + .001 for name, value in params.items()},
         inputs(rng, 4, changed=True)),
        (owner, params, inputs(rng, 5)),
        (owner, params, inputs(rng, 4, starts=True)),
        (owner, params, inputs(rng, 4, extent=replace(EXTENTS, factor_map_digest="f" * 64))),
        (CompiledGroups("release-b"), params, inputs(rng, 4)),
    )
    observations = []
    for ordinal, (compiled, weights, (hidden, kwargs)) in enumerate(cases, 1):
        before = compiled.stats()
        losses = compare_case(check, compiled, weights, hidden, kwargs)
        after = compiled.stats()
        assert after["misses"] - before["misses"] == (0 if ordinal == 2 else 1)
        assert after["hits"] > before["hits"]
        observations.append({"case": ordinal, "losses": losses, "compile": after})
        print("ISSUE1616_CASE " + json.dumps(observations[-1]), flush=True)
    # A Python cache hit is not proof of MLX autodiff trace reuse.
    check_isolation(check, owner, params, rng)
    hidden, kwargs = inputs(rng, 4)
    timing = benchmark(params, hidden, kwargs)
    backward = standalone_backward(check, params, hidden, kwargs)
    print("ISSUE1616_PARITY " + json.dumps({
        "schema": "bilqis.issue1616.direct-parity/v1", "mlx": mx.__version__,
        "tolerance": {"rtol": RTOL, "atol": ATOL},
        "cases": observations, "comparisons": check.records, "timing": timing,
        "standalone_backward": backward,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
