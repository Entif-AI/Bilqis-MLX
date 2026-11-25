"""CPU-only counterfactuals on authenticated optimizer leaves; never train."""
import argparse
import json
from pathlib import Path

import mlx.core as mx
import numpy as np
from safetensors import safe_open

from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, bamf_storage_key, expected_bamf_shapes,
)
from bilqis_mlx.runtime.optimizer_step import adamw_leaf_update
from scripts.bamf.profiling.issue1645.frozen_geometry import bind
from scripts.bamf.profiling.issue1645.reservation import require

OUTPUT_LEAVES = ("readout.control", "readout.control_bias", "readout.output")
PROBE_MAGNITUDES = (0.0, 1e-6, 1e-3)
EPSILON_CANDIDATES = (1e-5, 1e-4)


def read_leaf(source, name, rows=None):
    def read(part):
        key = bamf_storage_key(name, "weight")
        key = key[:-len("weight")] + "count" if part == "count" else bamf_storage_key(name, part)
        return source.get_tensor(key) if rows is None else source.get_slice(key)[:rows]
    return tuple(read(part) for part in ("weight", "m", "v", "count"))


def probe(leaf, hp, *, eps, decay, magnitude, mask):
    weight, first, second, count = leaf
    gradient = np.full_like(weight, magnitude)
    gradient.reshape(-1)[1::2] *= -1
    updated, m, v, clock = adamw_leaf_update(
        mx.array(weight), mx.array(first), mx.array(second),
        mx.array(count, dtype=mx.uint64), mx.array(gradient), mx.array(mask),
        learning_rate=hp["learning_rate"], betas=tuple(hp["betas"]),
        eps=eps, weight_decay=hp["weight_decay"] if decay else 0.)
    mx.eval(updated, m, v, clock)
    delta = np.asarray(updated).astype(np.float64) - weight
    require(np.isfinite(delta).all(), "nonfinite displacement")
    require(np.array_equal(np.asarray(clock), count + mask), "count drift")
    if np.ndim(mask):
        for actual, old in ((updated, weight), (m, first), (v, second)):
            require(np.array_equal(np.asarray(actual)[~mask], old[~mask]), "frozen row drift")
    return {"epsilon": eps, "probe_gradient_magnitude": magnitude,
            "displacement_l2": float(np.linalg.norm(delta)),
            "max_abs_displacement": float(np.max(np.abs(delta))),
            "probe_dot_displacement": float(np.vdot(gradient, delta)),
            "clock_increments": int(np.sum(mask))}


def analyze(run, tensor_file, prepared):
    mx.set_default_device(mx.cpu)
    pointer = (run / "bamf-state.json").read_bytes()
    manifest, features, reservation, digest = bind(run, tensor_file, prepared)
    topology = ModelTopologySpecV2.from_record(manifest["topology"])
    extents = GenerationExtents.from_record(manifest["extents"])
    ledger = {spec.name: spec for spec in expected_bamf_shapes(topology, extents)}
    hp = manifest["optimizer"]["hyperparameters"]
    catalog_size = len(features["factory_semantic_catalog"]["tokens"])
    require(extents.semantic_bank_count == 1, "unsupported multi-bank scope")
    results = {}
    with safe_open(str(tensor_file), framework="numpy") as source:
        for name in (*OUTPUT_LEAVES, "identity.bank.0"):
            tied = name == "identity.bank.0"
            leaf = read_leaf(source, name, catalog_size if tied else None)
            mask = np.arange(catalog_size) % 2 == 0 if tied else np.array(True)
            epsilons = (hp["eps"],) if tied else (hp["eps"], *EPSILON_CANDIDATES)
            results[name] = {
                "weight_decay_enabled": ledger[name].decay,
                "scope": "tied active ABI rows" if tied else "readout leaf",
                "samples": [probe(leaf, hp, eps=eps, decay=ledger[name].decay,
                                  magnitude=magnitude, mask=mask)
                            for magnitude in PROBE_MAGNITUDES for eps in epsilons],
            }
    require(pointer == (run / "bamf-state.json").read_bytes(), "accepted pointer changed")
    return {"manifest_sha256": prepared["manifest_sha256"], "tensor_sha256": digest,
            "reservation_sha256": reservation["reservation_sha256"],
            "optimizer_step": manifest["optimizer"]["step"], "hyperparameters": hp,
            "scope": "actual frozen weights/moments/counts; synthetic gradient and mask",
            "actual_loss_gradient": None, "actual_route_participation": None,
            "learning_gain": None, "leaves": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("tensor_file", type=Path)
    parser.add_argument("prepared", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.run, args.tensor_file,
                             json.loads(args.prepared.read_text())), indent=2))


if __name__ == "__main__":
    main()
