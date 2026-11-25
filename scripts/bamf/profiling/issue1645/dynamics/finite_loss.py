"""Forward-only loss changes on the exact previously bound controlled probes.

Reconstruct one proposed native displacement at a time. No admission, learner
publication, optimizer continuation, independent exam or new gradient execution.
"""
import argparse
import json
import math
from pathlib import Path
import resource
import time

from scripts.bamf.profiling.issue1645.dynamics.authentic_dynamics import (
    compiled_source_probe, custody, isolated_copy,
)
from scripts.bamf.profiling.issue1645.reservation import CAPABILITIES, require
from scripts.bamf.profiling.issue1645.dynamics.artifacts import (
    add_legacy_arguments, admit_reference, reference_basis,
)


def probe_rows(parent, context, capability, receipt):
    compiled, authority = compiled_source_probe(
        parent, context, capability, receipt["source_seed"], receipt["each"])
    require(authority.content_sha256 == receipt["source_content_sha256"]
            and authority.source_family_id == receipt["source_family_id"]
            and list(authority.episode_ids) == receipt["episode_ids"],
            "protected source identity drift")
    return compiled


def losses(parent, context, parameters, compiled, binding):
    from bilqis_mlx.learning.atlas_readout import ExecutionMode
    from bilqis_mlx.runtime.factory_candidate_microbatch import (
        _row_execution_inputs,
    )
    from bilqis_mlx.runtime.atlas_model_backend import model_backend
    from bilqis_mlx.runtime.atlas_model_forward import _forward_bamf_impl
    from bilqis_mlx.runtime.atlas_model_training import loss_bearing_bamf

    backend = model_backend(parent.topology)
    snapshot = context._accepted_feature_context.snapshot
    values = []
    for row in compiled:
        bound, _, targets, mask, plan = _row_execution_inputs(
            context, row, snapshot, binding.generation_digest)
        output = _forward_bamf_impl(
            backend, parameters, bound, plan, ExecutionMode.INFERENCE, None,
            refinement_training=True, execution_binding=binding, decoder_trace=False)
        value = float(loss_bearing_bamf(output, targets, mask).loss.total.item())
        require(math.isfinite(value), "nonfinite controlled loss")
        values.append(value)
    return values


def displaced(parent, source, receipt):
    import mlx.core as mx
    from safetensors import safe_open
    from bilqis_mlx.runtime.atlas_optimizer import _adamw_update
    from bilqis_mlx.runtime.atlas_optimizer_contracts import AdamWHyperparameters

    state = parent.retained_state.optimizer
    with safe_open(str(source), framework="numpy") as saved:
        gradients = {name: mx.array(saved.get_tensor("raw/" + name))
                     for name in state.parameters
                     if name not in receipt.get("omitted_frozen_gradient_leaves", ())}
        masks = {name: mx.array(saved.get_tensor("mask/" + name))
                 for name in state.parameters}
        hp = dict(receipt["hyperparameters"])
        hp["betas"] = tuple(hp["betas"])
        leaves = receipt["leaves"]
        authority = {name: (item["whole_parameter"], tuple(item["selected_rows"]))
                     for name, item in leaves.items()}
        result = _adamw_update(
            state, gradients, masks, AdamWHyperparameters(**hp),
            decay={name: item["decay"] for name, item in leaves.items()},
            max_norm=receipt["max_norm"], participation_authority=authority,
            learning_first=True)
        mx.eval(*result.parameters.values())
        error = 0.
        for name, weight in state.parameters.items():
            expected = mx.array(saved.get_tensor("delta/" + name))
            actual = result.parameters[name] - weight
            leaf_error = float(mx.max(mx.abs(actual - expected)).item())
            require(math.isfinite(leaf_error), "nonfinite saved native displacement")
            error = max(error, leaf_error)
        require(error <= 1e-11, "saved native displacement mismatch")
        return result.parameters, error


def analyze(evidence, destination, expected, legacy_index=None, legacy_digest=None):
    started = time.monotonic()
    reference, guard = admit_reference(evidence, expected, legacy_index, legacy_digest)
    source = evidence / "run"
    require(custody(source) == reference["source_custody"], "source custody drift")
    run, before = isolated_copy(source, evidence / "data-plane.sqlite3", destination)
    import mlx.core as mx
    from bilqis_mlx.runtime.backbone_identity import issue_execution_generation_binding
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
    from bilqis_mlx.runtime.bamf_operator.session_parts.session_support import _execution_context

    mx.set_memory_limit(12 * 1024**3)
    mx.set_cache_limit(0)
    rows = {}
    baseline = {}
    pairs = {}
    replay = {}
    try:
        with evidence_mode(strict=False):
            parent, context, _, _ = _execution_context(run)
            parent_parameters = parent.retained_state.optimizer.parameters
            require(reference_basis(reference) == {name: tuple(value.shape) for name, value
                        in parent_parameters.items()}, "saved basis differs from authenticated parent")

            def binding(parameters):
                return issue_execution_generation_binding(
                    parameters, spec=parent.topology, extents=parent.extents)

            parent_binding = binding(parent_parameters)
            for cap in CAPABILITIES:
                receipt = reference["capabilities"][cap]["protected"]
                rows[cap] = probe_rows(parent, context, cap, receipt)
                values = losses(parent, context, parent_parameters, rows[cap], parent_binding)
                require(all(math.isclose(actual, previous, rel_tol=1e-5, abs_tol=1e-6)
                            for actual, previous in zip(values, receipt["losses"], strict=True)),
                        "baseline forward loss disagrees with authenticated gradient loss")
                baseline[cap] = values
            for target in CAPABILITIES:
                target_started = time.monotonic()
                parameters, error = displaced(
                    parent, evidence / target / "update.safetensors",
                    reference["capabilities"][target])
                proposed_binding = binding(parameters)
                for protected, compiled in rows.items():
                    values = losses(parent, context, parameters, compiled, proposed_binding)
                    actual = sum(a - b for a, b in zip(values, baseline[protected], strict=True)) / len(values)
                    key = f"{target}->{protected}"
                    predicted = reference["interference"][key]["all"]["native_delta_dot"]
                    pairs[key] = {
                        "baseline_losses": baseline[protected], "displaced_losses": values,
                        "observed_mean_loss_change": actual, "predicted_mean_loss_change": predicted,
                        "taylor_residual": actual - predicted,
                    }
                replay[target] = {"max_displacement_replay_error": error,
                                  "wall_seconds": time.monotonic() - target_started}
                del parameters, proposed_binding
                mx.clear_cache()
                print(json.dumps({"target": target, **replay[target]}), flush=True)
        guard.require_current()
        result = {
            "scope": "controlled protected source loss, not an independent exam",
            "source_result_sha256": expected, "source_artifact_index_sha256": legacy_digest,
            "source_custody": before,
            "manifest_sha256": reference["manifest_sha256"], "pairs": pairs,
            "native_replay": replay, "learning_gain": None,
            "wall_seconds": time.monotonic() - started,
            "mlx_peak_bytes": mx.get_peak_memory(),
            "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
        (destination / "finite-loss.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    finally:
        guard.require_current()
        require(custody(run) == before == custody(source), "accepted custody changed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--result-sha256", required=True)
    add_legacy_arguments(parser)
    args = parser.parse_args()
    analyze(args.evidence.absolute(), args.destination.resolve(), args.result_sha256,
            args.legacy_artifact_index, args.legacy_artifact_index_sha256)


if __name__ == "__main__":
    main()
