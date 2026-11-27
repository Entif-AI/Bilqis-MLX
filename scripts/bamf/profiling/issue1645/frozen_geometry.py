"""Read authenticated retained numerical state without loading a learner.

Only raw source ABI bank vectors and explicitly named readout parameters are
materialized. This is not a contextual activation trace or independent exam.
"""
import argparse
import hashlib
from itertools import combinations
import json
from pathlib import Path

import numpy as np
from safetensors import safe_open

from bilqis_mlx.control_plane.native_custody import authenticated_history, _read_bound_json
from bilqis_mlx.runtime.model_topology_v2 import bamf_storage_key
from scripts.bamf.profiling.issue1645.reservation import CAPABILITIES, prepare, require


def hash_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bind(run, tensor_file, prepared):
    reservation = prepare(prepared)
    generation = authenticated_history(run)[-1]
    manifest = generation.manifest
    require(generation.manifest_sha256 == prepared["manifest_sha256"],
            "accepted generation mismatch")
    bundle = run / "bamf-bundles" / generation.manifest_sha256
    features = _read_bound_json(bundle, manifest["sidecars"]["compiler_features"],
                                reason="RESEARCH_COMPILER_FEATURE_DRIFT")
    require(features["factory_release_sha256"] == prepared["release_sha256"]
            and features["factory_semantic_graph_sha256"] == prepared["semantic_graph_sha256"],
            "source release mismatch")
    digest = hash_file(tensor_file)
    require(digest == manifest["tensors"]["sha256"], "numerical custody mismatch")
    return manifest, features, reservation, digest


def _cosine(left, right):
    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    return float(left @ right / denominator) if denominator else None


def _rank(vectors):
    centered = vectors - vectors.mean(axis=0)
    return int(np.linalg.matrix_rank(centered))


def _linear_probe(vectors, gold, groups):
    """Closed-form diagnostic, using one whole source family as each test fold."""
    def fit(train, test):
        x = np.column_stack((vectors[train], np.ones(len(train))))
        z = np.column_stack((vectors[test], np.ones(len(test))))
        labels = gold[train]
        # A leave-family-out fold need not have balanced class counts. Give
        # each label equal aggregate weight instead of leaking that imbalance
        # into a majority-class intercept.
        sample_weights = np.sqrt(
            len(train) / (2 * np.array([np.count_nonzero(labels == label)
                                        for label in labels])))
        weighted = x * sample_weights[:, None]
        # Small dual solve, independent of the neural learner and optimizer.
        weights = np.linalg.solve(weighted @ weighted.T + np.eye(len(train)) * 1e-3,
                                  labels * sample_weights)
        return z @ weighted.T @ weights > 0

    all_rows = np.arange(len(gold))
    in_sample = int(np.count_nonzero(fit(all_rows, all_rows) == (gold > 0)))
    correct, tested = 0, 0
    for group in sorted(set(groups)):
        test = np.flatnonzero(groups == group)
        train = np.flatnonzero(groups != group)
        if len(set(gold[train])) != 2:
            continue
        correct += int(np.count_nonzero(fit(train, test) == (gold[test] > 0)))
        tested += len(test)
    return {"in_sample_correct": in_sample, "in_sample_total": len(gold),
            "family_held_out_correct": correct, "family_held_out_total": tested,
            "scope": "class-balanced raw-bank mean-vector ridge probe; not learner generalization"}


def summarize(bank, rows, catalog_size):
    require(bank.ndim == 2 and catalog_size <= bank.shape[0], "bank geometry mismatch")
    by_cap = {}
    centers, coordinates = {}, {}
    for cap in CAPABILITIES:
        selected = [entry["row"] for entry in rows if entry["row"]["capability"] == cap]
        tokens = [row["tokens"] for row in selected]
        require(all(ids and all(type(i) is int and 0 <= i < catalog_size for i in ids)
                    for ids in tokens), "source ABI coordinate outside catalog")
        ids = set(i for seq in tokens for i in seq)
        vectors = np.array([bank[seq].mean(axis=0) for seq in tokens], dtype=np.float64)
        require(np.all(np.isfinite(vectors)), "nonfinite retained vectors")
        labels = np.array([1 if row["gold"] == "TRUE" else -1 for row in selected])
        groups = np.array([row["source_family_id"] for row in selected])
        centers[cap], coordinates[cap] = vectors.mean(axis=0), ids
        by_cap[cap] = {"rows": len(selected), "distinct_abi_coordinates": len(ids),
                       "centered_rank": _rank(vectors),
                       "positive_negative_center_cosine": _cosine(
                           vectors[labels > 0].mean(axis=0), vectors[labels < 0].mean(axis=0)),
                       "linear_probe": _linear_probe(vectors, labels, groups)}
    pairs = [{"left": left, "right": right,
              "shared_abi_coordinates": len(coordinates[left] & coordinates[right]),
              "raw_bank_mean_cosine": _cosine(centers[left], centers[right])}
             for left, right in combinations(CAPABILITIES, 2)]
    return {"capabilities": by_cap, "pairs": pairs,
            "contextual_activations": None, "architectural_attainability": None,
            "independent_learner_generalization": None}


def analyze(run, tensor_file, prepared):
    pointer = (run / "bamf-state.json").read_bytes()
    manifest, features, reservation, digest = bind(run, tensor_file, prepared)
    require(manifest["extents"]["semantic_bank_count"] == 1,
            "this bounded diagnostic supports one semantic bank")
    catalog = features["factory_semantic_catalog"]["tokens"]
    with safe_open(str(tensor_file), framework="numpy") as source:
        bank = source.get_slice(bamf_storage_key("identity.bank.0", "weight"))
        vectors = bank[:len(catalog)]
    result = summarize(vectors, prepared["prospective"]["rows"], len(catalog))
    require(pointer == (run / "bamf-state.json").read_bytes(), "accepted pointer changed")
    return {**result, "manifest_sha256": prepared["manifest_sha256"],
            "tensor_sha256": digest,
            "reservation_sha256": reservation["reservation_sha256"],
            "optimizer_step": manifest["optimizer"]["step"],
            "scope": "authenticated raw source ABI vectors, no learner execution"}


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
