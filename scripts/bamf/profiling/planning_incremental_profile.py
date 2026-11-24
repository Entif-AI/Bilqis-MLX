#!/usr/bin/env python3
"""Profile the #1536 production A09 planning owner on a disposable BAMF run.

This witness performs no neural optimizer updates and does not publish an
accepted successor. Planning may materialize derived planning projections in
the supplied run, so the run MUST be a disposable copy rather than the human
production lineage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bilqis_mlx.runtime.bamf_operator.session_parts.session_support import _execution_context
from bilqis_mlx.runtime.lawful_teaching_frontier import (
    _issue_lawful_teaching_frontier_from_epoch,
)
from bilqis_mlx.runtime.priority_planning_owner import (
    PriorityPlanningCache,
    build_priority_planning_epoch,
    priority_planning_from_epoch,
)
from bilqis_mlx.runtime.priority_source_offer import (
    _require_planning_generation,
    bind_priority_planning_generation,
)


SCHEMA = "bilqis.bamf.planning-incremental-profile/v1"


def _tested_revision() -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=ROOT, check=True,
        capture_output=True, text=True)
    return result.stdout.strip()


def _span(callable_):
    started = perf_counter()
    value = callable_()
    return value, max(0.0, perf_counter() - started)


def _one(root, parent, context, atlas_path, cache):
    generation, bind_seconds = _span(
        lambda: bind_priority_planning_generation(context, parent, atlas_path))
    (accepted_cache, authenticated), require_seconds = _span(
        lambda: _require_planning_generation(generation, context, parent))
    epoch, epoch_seconds = _span(lambda: build_priority_planning_epoch(
        root, context, atlas_path,
        authenticated_features=authenticated,
        planning_cache=cache))
    planning, ranking_seconds = _span(
        lambda: priority_planning_from_epoch(epoch, planning_cache=cache))
    frontier, frontier_seconds = _span(
        lambda: _issue_lawful_teaching_frontier_from_epoch(
            epoch, context, parent, generation, planning_cache=cache))
    spans = {
        "bind_generation_seconds": bind_seconds,
        "require_generation_seconds": require_seconds,
        "build_epoch_seconds": epoch_seconds,
        "rank_projection_seconds": ranking_seconds,
        "seal_lawful_frontier_seconds": frontier_seconds,
    }
    spans["planning_owner_seconds"] = sum(spans.values())
    return {
        "spans": spans,
        "cache": cache.metrics(),
        "accepted_generation": accepted_cache.generation,
        "accepted_manifest_sha256": accepted_cache.accepted_manifest_sha256,
        "selected_semantic_id": (
            planning.selection.selected_semantic_id
            if planning.selection is not None else None),
        "lawful_frontier_sha256": frontier.frontier_sha256,
    }


def _disposable_root(run_dir: Path) -> Path:
    root = run_dir.expanduser().resolve()
    if not (root / ".issue1536-disposable-profile").is_file():
        raise ValueError("ISSUE1536_DISPOSABLE_PROFILE_MARKER_REQUIRED")
    return root


def profile(run_dir: Path, repeats: int, max_warm_seconds: float, *, run_label: str) -> dict:
    root = _disposable_root(run_dir)
    parent, context, atlas_path, _feature_path = _execution_context(root)
    cache = PriorityPlanningCache(root)
    samples = [_one(root, parent, context, atlas_path, cache)
               for _ in range(repeats)]
    cold = samples[0]
    warm = samples[1:]
    stable_selection = all(
        sample["selected_semantic_id"] == cold["selected_semantic_id"]
        and sample["lawful_frontier_sha256"] == cold["lawful_frontier_sha256"]
        for sample in warm)
    warm_seconds = [sample["spans"]["planning_owner_seconds"] for sample in warm]
    gate = bool(warm and stable_selection and max(warm_seconds) <= max_warm_seconds)
    return {
        "schema": SCHEMA,
        "tested_revision": _tested_revision(),
        "run_label": run_label,
        "repeats": repeats,
        "cache_invalidation": {
            "static": "factory/source/Atlas authority identity",
            "snapshot": "accepted generation manifest + admission receipt",
            "closure": "snapshot + accepted checkpoint/optimizer step + mastered projection",
            "ranking": "release + snapshot + closure + requested keys + accepted credit",
        },
        "samples": samples,
        "stable_selection": stable_selection,
        "max_warm_seconds": max_warm_seconds,
        "warm_seconds": warm_seconds,
        "gate_passed": gate,
    }


def prepare(argv, probes):
    """Shared checked-launch and direct CLI preparation; no planning work yet."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-warm-seconds", type=float, default=10.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-label", default="disposable-production-shaped-run")
    args = parser.parse_args(argv)
    if args.repeats < 2 or args.max_warm_seconds <= 0:
        parser.error("--repeats must be >=2 and --max-warm-seconds must be positive")
    try:
        root = _disposable_root(args.run_dir)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return lambda: _run_profile(args, root)


def _run_profile(args, root):
    result = profile(root, args.repeats, args.max_warm_seconds, run_label=args.run_label)
    payload = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["gate_passed"] else 1


def main() -> int:
    return prepare(sys.argv[1:], None)()


if __name__ == "__main__":
    raise SystemExit(main())
