"""Compare a directly compiled group value/gradient transform with stock."""
import statistics
import time

import mlx.core as mx

from scripts.bamf.profiling.issue1616.backbone import STOCK


def standalone_backward(check, params, hidden, kwargs):
    traces = {"stock": 0, "compiled": 0}
    scope = kwargs["scope_ids"]
    valid = kwargs["valid"]
    fixed = {k: v for k, v in kwargs.items()
             if k not in ("scope_ids", "valid")}

    def make(mode):
        def objective(weights, activation, scope_ids, mask, cotangent):
            traces[mode] += 1
            result = STOCK(activation, weights, scope_ids=scope_ids,
                           valid=mask, **fixed)
            return mx.sum(result.hidden * cotangent)
        grad = mx.value_and_grad(objective, argnums=(0, 1))
        return mx.compile(grad) if mode == "compiled" else grad

    cases = []
    for i in range(4):
        weights = {k: v + .0001 * i for k, v in params.items()}
        activation = hidden + .01 * i
        ids = scope if not i % 2 else scope.at[0, -1].add(1)
        mask = valid if not i % 2 else valid & ~((mx.arange(valid.shape[0])[:, None] == 1) & (mx.arange(valid.shape[1])[None, :] == valid.shape[1] - 1))
        cotangent = mx.full(hidden.shape, .0001 * (i + 1))
        mx.eval(weights, activation, ids, mask, cotangent)
        cases.append((weights, activation, ids, mask, cotangent))
    outputs, report = {}, {}
    for mode in ("stock", "compiled"):
        fn = make(mode)
        mx.clear_cache()
        mx.reset_peak_memory()
        samples, results = [], []
        for args in cases:
            mx.synchronize()
            start = time.perf_counter()
            result = fn(*args)
            mx.eval(result)
            mx.synchronize()
            samples.append(time.perf_counter() - start)
            results.append(result)
        outputs[mode] = results
        report[mode] = {
            "cold_seconds": samples[0], "warm_seconds": samples[1:],
            "warm_median_seconds": statistics.median(samples[1:]),
            "peak_bytes": mx.get_peak_memory(), "python_graph_traces": traces[mode],
        }
    for stock, compiled in zip(outputs["stock"], outputs["compiled"], strict=True):
        a, (ga, ha) = stock
        b, (gb, hb) = compiled
        check.check("standalone_vjp_loss", a, b)
        check.check("standalone_vjp_hidden", ha, hb)
        for name in params:
            check.check("standalone_vjp_parameter", ga[name], gb[name])
    assert traces == {"stock": len(cases), "compiled": 1}, traces
    return report
