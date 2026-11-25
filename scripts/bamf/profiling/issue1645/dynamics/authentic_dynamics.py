"""Read-only Grade A loss/optimizer probes on a disposable authenticated run.

This command never enters the trainer, retention admission or publication loop.
Its balanced source draws are diagnostic, not an independent exam or a replay
of historical delivery. Every counterfactual starts from the same parent.
"""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import sqlite3
import subprocess
import time
from types import SimpleNamespace

from scripts.bamf.profiling.issue1645.reservation import CAPABILITIES, require


def file_digest(path):
    with path.open("rb") as stream:
        return sha256_stream(stream)


def sha256_stream(stream):
    from hashlib import file_digest as hash_file
    return hash_file(stream, "sha256").hexdigest()


def custody(run):
    return {name: file_digest(run / name)
            for name in ("bamf-state.json", "events.jsonl")}


def reject_symlinks(root):
    require(not root.is_symlink(), "symbolic link in diagnostic custody")
    if root.is_dir():
        for base, dirs, files in os.walk(root, followlinks=False):
            require(not any((Path(base) / name).is_symlink()
                            for name in (*dirs, *files)),
                    "symbolic link in diagnostic custody")


def isolated_copy(source, plane, destination):
    require(not destination.exists(), "destination must be new")
    require(not destination.is_relative_to(source), "destination inside source")
    require(not source.is_relative_to(destination), "source inside destination")
    companions = tuple(Path(str(plane) + suffix) for suffix in (".objects", ".archive"))
    for original in (source, plane, *companions):
        require(not destination.is_relative_to(original)
                and not original.is_relative_to(destination),
                "overlapping diagnostic custody")
        reject_symlinks(original)
    before = custody(source)
    destination.mkdir(parents=True)
    run = destination / "run"
    subprocess.run(["cp", "-cR", str(source), str(run)], check=True)
    target = destination / "data-plane.sqlite3"
    with sqlite3.connect(plane.as_uri() + "?mode=ro", uri=True) as origin:
        with sqlite3.connect(target) as copy:
            origin.backup(copy)
    for suffix in (".objects", ".archive"):
        companion = Path(str(plane) + suffix)
        if companion.exists():
            subprocess.run(["cp", "-cR", str(companion), str(target) + suffix],
                           check=True)
    require(custody(run) == before == custody(source), "custody changed during copy")
    os.environ["BILQIS_DATA_PLANE"] = str(target)
    return run, before


def probe_seed(manifest, capability, label):
    return int.from_bytes(sha256(
        f"issue1645-dynamics-v1|{manifest}|{capability}|{label}".encode()
    ).digest()[:8], "big")


def compiled_source_probe(parent, context, capability, seed, each):
    """Prepare the exact source-owned diagnostic rows, without a visit."""

    from bilqis_mlx.runtime.learning_first_source import prepare_learning_first_source_rows
    from bilqis_mlx.runtime.factory_training_source import (
        _prepare_learning_first_model_sources, _bind_learning_first_rows,
    )

    rows, authority = context.draw_bound_rows(seed=seed, capability=capability, each=each)
    authenticated = context._accepted_feature_context
    source_rows = prepare_learning_first_source_rows(
        context, authenticated, rows, source_seed=seed, source_each=each)
    inputs = _prepare_learning_first_model_sources(authenticated, source_rows)
    # The binder only needs the prepared prefix and optional visit provenance.
    # No synthetic C03 visit, training authority or publication capability.
    training = SimpleNamespace(rows=tuple(
        SimpleNamespace(model_input=item, provenance=SimpleNamespace(visit=None))
        for item in inputs))
    compiled = _bind_learning_first_rows(
        context, parent, authenticated, training, source_rows, None,
        source_seed=seed, source_each=each)
    return compiled, authority


def source_gradient(parent, context, cache, capability, seed, each):
    """Use B11's actual scalar correctness path, without invented visit authority."""
    import mlx.core as mx
    from bilqis_mlx.runtime.candidate.step_authority import bind_learning_first_step_authority
    from bilqis_mlx.runtime.factory_candidate_microbatch import execute_factory_training_row

    compiled, authority = compiled_source_probe(parent, context, capability, seed, each)
    authenticated = context._accepted_feature_context
    generation = bind_learning_first_step_authority(cache, parent, None, context)
    parameters = parent.retained_state.optimizer.parameters
    total, executions, losses = None, [], []
    for row in compiled:
        gradient, _, _ = execute_factory_training_row(
            parameters, row, context, authenticated.snapshot, generation, None)
        losses.append(float(gradient.loss_total.item()))
        executions.append(gradient.execution)
        if total is None:
            total = dict(gradient.gradients)
        else:
            total = {name: value + gradient.gradients[name]
                     for name, value in total.items()}
        mx.eval(*total.values())
    gradients = {name: value / each for name, value in total.items()}
    mx.eval(*gradients.values())
    return gradients, tuple(executions), {
        "kind": "balanced source diagnostic, not an issued visit or exam",
        "source_seed": seed, "each": each, "source_content_sha256": authority.content_sha256,
        "source_family_id": authority.source_family_id, "episode_ids": authority.episode_ids,
        "losses": losses, "mean_loss": sum(losses) / each,
    }


def optimizer_inputs(parent, cache, executions):
    from bilqis_mlx.learning._atlas_candidate.transaction import _begin_learning_first_candidate
    from bilqis_mlx.learning._atlas_candidate.step import _learning_first_optimizer_inputs
    from bilqis_mlx.runtime.bamf_bundle.admission import derive_participation_inputs

    candidate = _begin_learning_first_candidate(
        parent.retained_state, cache._candidate_identity_sha256)
    group, _ = derive_participation_inputs(parent)
    return _learning_first_optimizer_inputs(
        candidate, executions, group, parent.topology, parent.extents)


def run_probes(parent, context, cache, destination, manifest, capabilities, each, lr):
    from dataclasses import replace
    import mlx.core as mx
    from scripts.bamf.profiling.issue1645.dynamics.displacement_analysis import write_update

    receipts = {}
    hp = replace(parent.optimizer_hyperparameters, learning_rate=lr)
    for capability in capabilities:
        started = time.monotonic()
        mx.reset_peak_memory()
        gradients, executions, evidence = source_gradient(
            parent, context, cache, capability, probe_seed(manifest, capability, "target"), each)
        mask, decay, authority = optimizer_inputs(parent, cache, executions)
        del executions
        receipt = write_update(destination / capability, parent.retained_state.optimizer,
                               gradients, mask, decay, authority, hp, max_norm=1.)
        del gradients, mask
        # Separate protected probe seed, fixed before seeing scores.
        protected, executions, protection = source_gradient(
            parent, context, cache, capability, probe_seed(manifest, capability, "protected"), each)
        mx.save_safetensors(str(destination / capability / "protected.safetensors"), protected)
        del protected, executions
        receipt.update({"target": evidence, "protected": protection,
                        "hyperparameters": asdict(hp),
                        "wall_seconds": time.monotonic() - started,
                        "mlx_peak_bytes": mx.get_peak_memory(),
                        "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
        receipts[capability] = receipt
        (destination / capability / "receipt.json").write_text(json.dumps(receipt, indent=2))
        print(json.dumps({"capability": capability, "receipt": receipt}), flush=True)
        mx.clear_cache()
    return receipts


def analyze(source, plane, destination, capabilities, each, lr, memory_gib):
    started = time.monotonic()
    run, before = isolated_copy(source, plane, destination)
    # Import runtime only AFTER assigning the disposable data plane.
    import mlx.core as mx
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
    from bilqis_mlx.runtime.bamf_operator.session_parts.session_support import _execution_context
    from scripts.bamf.profiling.issue1645.dynamics.displacement_analysis import interference_matrix
    mx.set_memory_limit(memory_gib * 1024**3)
    mx.set_cache_limit(0)
    manifest = json.loads((run / "bamf-state.json").read_text())["manifest_sha256"]
    try:
        with evidence_mode(strict=False):
            parent, context, _, _ = _execution_context(run)
            cache = context._accepted_runtime_host._accepted_cache
            receipts = run_probes(parent, context, cache, destination, manifest,
                                  capabilities, each, lr)
        result = {
            "scope": "one-step numerical counterfactuals, no learner publication",
            "manifest_sha256": manifest, "source_custody": before,
            "capabilities": receipts, "interference": interference_matrix(destination, capabilities),
            "independent_learning_gain": None,
            "wall_seconds": time.monotonic() - started,
            "memory_limit_bytes": memory_gib * 1024**3,
        }
        (destination / "result.json").write_text(json.dumps(result, indent=2))
        return result
    finally:
        require(custody(run) == before == custody(source), "accepted custody changed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("plane", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--each", type=int, choices=(2, 4, 6, 12, 32), default=6)
    parser.add_argument("--capability", choices=CAPABILITIES, action="append")
    parser.add_argument("--lr", type=float, default=0.00013)
    parser.add_argument("--memory-gib", type=int, choices=(12, 16), default=12)
    args = parser.parse_args()
    analyze(args.run.resolve(), args.plane.resolve(), args.destination.resolve(),
            tuple(args.capability or CAPABILITIES), args.each, args.lr, args.memory_gib)


if __name__ == "__main__":
    main()
