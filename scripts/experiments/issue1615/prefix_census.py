#!/usr/bin/env python3
"""Issue #1615: measure per-delivery compiled causal-prefix reuse, without MLX training."""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def count_positions(rows):
    """Count logical occurrences and unique cumulative prefix nodes.

    No reuse across different task scopes or independently sampled deliveries.
    Keys include position kind and source index. Earlier keys represent the
    full causal history, not merely the immediately preceding atom.
    """
    nodes = set()
    lengths = Counter()
    total = 0
    for scope, positions in rows:
        prefix = (scope,)
        lengths[len(positions)] += 1
        for position in positions:
            prefix += (position,)
            nodes.add(prefix)
            total += 1
    return {
        "rows": sum(lengths.values()),
        "length_histogram": dict(sorted(lengths.items())),
        "positions": total,
        "unique_prefix_positions": len(nodes),
        "repeated_positions": total - len(nodes),
        "repeated_fraction": (total - len(nodes)) / total if total else 0.0,
        "padded_positions": sum(lengths.values()) * max(lengths, default=0),
    }


def atom_abi(snapshot, source, source_index):
    token_index = source.row["tokens"][source_index]
    entry = snapshot.abi(token_index)
    if entry.symbol != source.source_graph["tokens"][token_index]:
        semantic_id = source.source_graph["nodes"][token_index].get("semantic_id")
        entry = snapshot.abi_for_semantic(semantic_id)
    return entry.index


def position_keys(snapshot, source, model_source, row_index):
    """Stop conservative reuse at the first packed closure.

    Packed frame embeddings may depend on member/role/schema/child inputs.
    Treating these as equivalent merely from surface tokens is not justified.
    The optimistic bound erases closure contents, not their placement.
    """
    conservative, optimistic, exact = [], [], []
    for position in model_source.prefix.positions:
        if position.kind.value == "ATOM":
            key = ("ATOM", position.source_index,
                   atom_abi(snapshot, source, position.source_index))
            conservative.append(key)
            optimistic.append(key)
        elif position.kind.value == "CLOSURE":
            key = ("CLOSURE", position.source_index)
            conservative.append((*key, row_index))
            optimistic.append(key)
        else:
            raise ValueError(f"Unexpected compiled position: {position.kind}")
        exact.append(position.cache_identity)
    return conservative, optimistic, exact


def self_test():
    rows = [
        ("A", [("ATOM", 0, 1), ("ATOM", 1, 2)]),
        ("A", [("ATOM", 0, 1), ("ATOM", 1, 3), ("ATOM", 2, 4)]),
        ("B", [("ATOM", 0, 1)]),
        ("A", [("ATOM", 0, 1), ("ATOM", 1, 2)]),
    ]
    result = count_positions(rows)
    assert result["positions"] == 8 and result["unique_prefix_positions"] == 5
    assert result["repeated_positions"] == 3
    assert result["padded_positions"] == 12
    assert count_positions([])["positions"] == 0
    print("PREFIX_CENSUS_SELF_TEST_PASS", flush=True)


def compile_sources(authenticated, sources):
    from bilqis_mlx.errors import BilqisError
    from bilqis_mlx.runtime.factory_training_source import (
        _prepare_learning_first_model_sources,
    )
    compiled = []
    held = Counter()
    for source in sources:
        try:
            model, = _prepare_learning_first_model_sources(authenticated, (source,))
        except BilqisError as error:
            if error.context.get("reason") != "BAMF_PREFIX_SCHEMA_NOT_RELEASED":
                raise
            from bilqis_mlx.semantics.frame_schema import FrameInstance
            declared = {(schema.schema_id, schema.revision)
                        for schema in source.config.schemas}
            def walk(tree):
                yield tree.root
                for child in tree.children:
                    yield from walk(child)
            missing = sorted({
                (frame.frame_schema_id, frame.frame_schema_revision)
                for tree in source.ast.frames for frame in walk(tree)
                if isinstance(frame, FrameInstance)
                and (frame.frame_schema_id, frame.frame_schema_revision) not in declared})
            held[str(missing)] += 1
            continue
        compiled.append((source, model))
    return compiled, held


def position_metrics(snapshot, compiled):
    groups = {key: [] for key in ("conservative", "optimistic", "exact")}
    for index, (source, model) in enumerate(compiled):
        for name, keys in zip(groups, position_keys(snapshot, source, model, index)):
            groups[name].append((source.config.task.scope, keys))
    metrics = {name: count_positions(values) for name, values in groups.items()}
    return metrics


def census(each, seeds, limit, capability_prefix):
    from bilqis_mlx.bootstrap_assets import (
        ATLAS_BUNDLE_ID, ATLAS_RELEASE_SHA256, ATLAS_ROOT,
        ATLAS_SOURCE_BUNDLE_ID, SOURCE_RUN,
    )
    from bilqis_mlx.factory.live_answers import live_answer_registry
    from bilqis_mlx.factory.teaching import describe_delivered_teaching
    from bilqis_mlx.presentation.operator_cli.bamf_lifecycle_inputs import source_foundation
    from bilqis_mlx.runtime.factory_training_preparation import prepare_learning_first_source_rows
    from bilqis_mlx.runtime.source_execution import SourceExecutionContext
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
    from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import (
        canonical_feature_schema,
    )
    from bilqis_mlx.semantics.atlas.snapshot import (
        AtlasArtifactSelection, load_pinned_atlas_snapshot, reuse_pinned_atlas_snapshot,
    )
    from bilqis_mlx.semantics.atlas_features import build_feature_manifest
    from bilqis_mlx.source_adapters.school import live_source_registry

    _, release, graph = source_foundation(SOURCE_RUN)
    selection = AtlasArtifactSelection(
        str(ATLAS_ROOT / ATLAS_BUNDLE_ID), ATLAS_BUNDLE_ID,
        ATLAS_RELEASE_SHA256, ATLAS_SOURCE_BUNDLE_ID)
    snapshot = load_pinned_atlas_snapshot(selection)
    with reuse_pinned_atlas_snapshot(selection, snapshot), evidence_mode(strict=False):
        schema = canonical_feature_schema(selection)
        features = build_feature_manifest(snapshot, schema)
        context = SourceExecutionContext(
            release, graph, ROOT / "vendor/legacy-v16",
            live_source_registry(), live_answer_registry())
        authenticated = SimpleNamespace(
            selection=selection, snapshot=snapshot, features=features, schema=schema)
        capabilities = sorted(cap for cap in release.execution_plan.capability_map
                              if cap.startswith(capability_prefix))
        if limit:
            capabilities = capabilities[:limit]
        print(json.dumps({"event": "census_start", "atlas": ATLAS_BUNDLE_ID,
                          "release": release.release_sha256,
                          "capabilities": capabilities, "each": each, "seeds": seeds}),
              flush=True)
        totals = Counter()
        for capability in capabilities:
            for seed in seeds:
                started = time.monotonic()
                rows = tuple(context.draw_rows(
                    seed=seed, capability=capability, each=each))
                execution = release.execution_plan.capability_map[capability]
                delivery = describe_delivered_teaching(
                    release, capability, execution.teaching_option_ids[0], rows)
                sources = prepare_learning_first_source_rows(
                    context, authenticated, rows, source_seed=seed, source_each=each)
                compiled, held = compile_sources(authenticated, sources)
                metrics = position_metrics(snapshot, compiled)
                for name, counts in metrics.items():
                    totals[f"{name}_repeated_positions"] += counts["repeated_positions"]
                totals["positions"] += metrics["conservative"]["positions"]
                totals["rows"] += len(compiled)
                totals["held_rows"] += sum(held.values())
                totals["deliveries"] += 1
                print(json.dumps({
                    "event": "delivery", "capability": capability, "seed": seed,
                    "delivery_digest": delivery.specimen_content_sha256,
                    "distinct_row_ids": len({row["id"] for row in rows}),
                    "held_rows": sum(held.values()), "missing_schemas": dict(held),
                    "metrics": metrics, "seconds": time.monotonic() - started,
                }), flush=True)
        print(json.dumps({"event": "census_complete", **totals}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--each", type=int, default=32)
    parser.add_argument("--seeds", nargs="+", type=int, default=[1615, 2615])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--capability-prefix", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        census(args.each, args.seeds, args.limit, args.capability_prefix)


if __name__ == "__main__":
    main()
