"""CPU-only sensitivity of saved AdamW displacements to actual retained moments."""
import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
import resource
import time

import numpy as np
from safetensors import safe_open

from scripts.bamf.profiling.issue1645.dynamics.authentic_dynamics import custody
from scripts.bamf.profiling.issue1645.reservation import CAPABILITIES, require
from scripts.bamf.profiling.issue1645.dynamics.artifacts import (
    add_legacy_arguments, admit_reference, reference_basis,
)


def sensitivities(first, second, gradient, count, hp):
    """Analytic FP64 directions; only the observed native displacement is exact."""
    b1, b2 = hp["betas"]
    lr, eps = hp["learning_rate"], hp["eps"]
    m = b1 * first + (1 - b1) * gradient
    old_v = b2 * second
    new_v = (1 - b2) * gradient**2
    v = old_v + new_v
    c1 = 1 / (1 - b1**count)
    c2 = 1 / np.sqrt(1 - b2**count)
    fraction = np.divide(old_v, v, out=np.zeros_like(v), where=v > 0)
    vectors = {
        "analytic_native": -lr * c1 * m / (np.sqrt(v) * c2 + eps),
        "uncorrected": -lr * m / (np.sqrt(v) + eps),
        "no_second_history": -lr * c1 * m / (np.sqrt(new_v) * c2 + eps),
        "uniform_denominator": -lr * c1 * m,
    }
    return vectors, fraction[v > 0], c1, c2


def active_array(source, key, selected, rowwise):
    array = source.get_tensor(key)
    return np.asarray(array[selected] if rowwise else array, dtype=np.float64)


def finish_dots(target, result, dots, norms):
    norms = {key: math.sqrt(value) for key, value in norms.items()}
    for protected, row in dots.items():
        observed = result["interference"][f"{target}->{protected}"]["all"]["native_delta_dot"]
        require(math.isclose(row["observed_adaptive"] + row["decay"], observed,
                             rel_tol=1e-9, abs_tol=1e-12), "saved matrix binding mismatch")
        for key in ("no_second_history", "uniform_denominator"):
            row[key + "_matched_norm"] = (
                row[key] * norms["observed_adaptive"] / norms[key] + row["decay"]
                if norms[key] else (row["decay"] if not norms["observed_adaptive"] else None))
        for key in ("analytic_native", "uncorrected"):
            row[key + "_with_decay"] = row[key] + row["decay"]
    return norms


def analyze_target(target, update, parent, probes, receipt, result):
    hp = receipt["hyperparameters"]
    keys = ("analytic_native", "uncorrected", "no_second_history", "uniform_denominator",
            "observed_adaptive", "rounding_residual", "decay")
    dots = {protected: dict.fromkeys(keys, 0.) for protected in probes}
    norms = dict.fromkeys(keys, 0.)
    n = selected_clocks = 0
    old_sum = old_majority = old_dominant = 0.
    bias_min = [math.inf, math.inf]
    bias_max = [0., 0.]
    max_error = 0.
    for name, leaf in receipt["leaves"].items():
        mask = update.get_tensor("mask/" + name)
        require(int(mask.sum()) == leaf["selected_clocks"], "mask custody mismatch")
        if not mask.any():
            continue
        rowwise = mask.ndim != 0
        selected = np.flatnonzero(mask) if rowwise else None
        prefix = "p" + name.encode().hex()
        g = active_array(update, "clipped/" + name, selected, rowwise)
        m = active_array(parent, prefix + "_m", selected, rowwise)
        v = active_array(parent, prefix + "_v", selected, rowwise)
        count = active_array(parent, prefix + "_count", selected, rowwise) + 1
        selected_clocks += count.size
        if rowwise:
            count = count.reshape((-1,) + (1,) * (g.ndim - 1))
        vectors, fraction, c1, c2 = sensitivities(m, v, g, count, hp)
        n += fraction.size
        old_sum += float(fraction.sum())
        old_majority += int(np.count_nonzero(fraction >= .5))
        old_dominant += int(np.count_nonzero(fraction >= .9))
        for i, factor in enumerate((c1, c2)):
            bias_min[i] = min(bias_min[i], float(factor.min()))
            bias_max[i] = max(bias_max[i], float(factor.max()))
        delta = active_array(update, "delta/" + name, selected, rowwise)
        decay = active_array(update, "decay/" + name, selected, rowwise)
        vectors["observed_adaptive"] = delta - decay
        error = vectors["analytic_native"] - vectors["observed_adaptive"]
        max_error = max(max_error, float(np.max(np.abs(error))))
        vectors["rounding_residual"] = error
        vectors["decay"] = decay
        for key, value in vectors.items():
            flat = value.reshape(-1)
            require(np.isfinite(flat).all(), "nonfinite direction")
            norms[key] += float(flat @ flat)
        for protected, probe in probes.items():
            p = active_array(probe, name, selected, rowwise).reshape(-1)
            for key, value in vectors.items():
                dots[protected][key] += float(p @ value.reshape(-1))
    norms = finish_dots(target, result, dots, norms)
    return {
        "active_clocks": selected_clocks, "nonzero_second_coordinates": n,
        "retained_second_fraction_mean": old_sum / n if n else None,
        "retained_second_majority_fraction": old_majority / n if n else None,
        "retained_second_at_least_90pct_fraction": old_dominant / n if n else None,
        "bias_factors_min": bias_min if selected_clocks else None,
        "bias_factors_max": bias_max if selected_clocks else None,
        "adaptive_l2": norms, "analytic_max_absolute_difference": max_error,
        "protected_dots": dots,
    }


def analyze(evidence, expected_result, legacy_index=None, legacy_digest=None):
    started = time.monotonic()
    cpu = time.process_time()
    result, guard = admit_reference(evidence, expected_result, legacy_index, legacy_digest)
    run = evidence / "run"
    require(custody(run) == result["source_custody"], "source custody mismatch")
    manifest = run / "bamf-bundles" / result["manifest_sha256"] / "manifest.json"
    guard.admit(manifest, result["manifest_sha256"])
    tensor = json.loads(manifest.read_text())["tensors"]
    digest = tensor["object_sha256"]
    path = evidence / "data-plane.sqlite3.objects" / digest[:2] / (digest + ".safetensors")
    require(tensor["sha256"] == digest, "tensor custody mismatch")
    guard.admit(path, digest)
    receipts = result["capabilities"]
    metrics = {}
    with ExitStack() as stack:
        def opened(path):
            return stack.enter_context(safe_open(str(path), framework="numpy"))
        parent = opened(path)
        basis = {bytes.fromhex(key[1:-7]).decode(): tuple(parent.get_slice(key).get_shape())
                 for key in parent.keys() if key.startswith("p") and key.endswith("_weight")}
        require(basis == reference_basis(result), "saved basis differs from accepted tensor")
        probes = {cap: opened(evidence / cap / "protected.safetensors") for cap in CAPABILITIES}
        updates = {cap: opened(evidence / cap / "update.safetensors") for cap in CAPABILITIES}
        for target, update in updates.items():
            metrics[target] = analyze_target(
                target, update, parent, probes, receipts[target], result)
    guard.require_current()
    require(custody(run) == result["source_custody"], "source changed")
    return {"schema": "bilqis.research.moment-sensitivity/v1",
            "source_result_sha256": expected_result, "source_artifact_index_sha256": legacy_digest,
            "parent_tensor_sha256": digest,
            "manifest_sha256": result["manifest_sha256"], "targets": metrics,
            "scope": "first-order analytic sensitivities, no optimizer mutation or treatment",
            "wall_seconds": time.monotonic() - started, "cpu_seconds": time.process_time() - cpu,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--result-sha256", required=True)
    add_legacy_arguments(parser)
    args = parser.parse_args()
    result = analyze(args.evidence.absolute(), args.result_sha256,
                     args.legacy_artifact_index, args.legacy_artifact_index_sha256)
    with args.destination.open("x") as output:
        json.dump(result, output, indent=2, allow_nan=False)


if __name__ == "__main__":
    main()
