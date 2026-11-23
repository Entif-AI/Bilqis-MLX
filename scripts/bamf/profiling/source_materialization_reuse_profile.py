#!/usr/bin/env python3
"""Profile #1537 selected-source cold/warm handoff on a disposable BAMF run.

This witness executes planning and teacher selection only. It performs no neural
optimizer update and publishes no accepted successor. The run must be a
disposable copy because planning may materialize derived projections.
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

from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.runtime.bamf_operator.session_parts.session_support import _execution_context
from bilqis_mlx.runtime.factory_retention_owner import (
    bind_current_retention_protection_plan,
)
from bilqis_mlx.runtime.foundation_teacher_owner import (
    select_foundation_priority_visit,
)
from bilqis_mlx.runtime.accepted_priority_visit import accepted_priority_school
from bilqis_mlx.runtime.priority_planning_owner import PriorityPlanningCache
from bilqis_mlx.runtime.priority_source_materialization_cache import (
    priority_source_materialization_identity,
)


SCHEMA = "bilqis.bamf.source-materialization-reuse-profile/v1"
STAGE_FIELDS = (
    "source_materialization_cache_lookup_wall_seconds",
    "source_materialization_wait_wall_seconds",
    "source_materialization_factory_source_wall_seconds",
    "source_materialization_model_source_wall_seconds",
    "source_materialization_b11_binding_wall_seconds",
    "source_materialization_motif_planning_wall_seconds",
    "source_materialization_owner_build_wall_seconds",
    "source_materialization_registration_currentness_wall_seconds",
    "source_currentness_qualification_wall_seconds",
    "source_materialization_total_wall_seconds",
)


def _tested_revision() -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=ROOT, check=True,
        capture_output=True, text=True)
    return result.stdout.strip()


def _one(root: Path, cache: PriorityPlanningCache) -> dict:
    started = perf_counter()
    parent, context, atlas_path, _feature_path = _execution_context(root)
    program = schedule_program_from_executable_release(context.release)
    accepted_host = context._accepted_runtime_host
    host_cache = accepted_host._accepted_cache
    bind_current_retention_protection_plan(context, parent, host_cache)
    school = accepted_priority_school(
        parent, program,
        candidate_identity_sha256=host_cache._candidate_identity_sha256)
    selection = select_foundation_priority_visit(
        root, context, atlas_path, program=program, school=school,
        planning_cache=cache)
    if selection.status != "TEACHER_SELECTED" or selection.offer is None:
        raise ValueError("ISSUE1537_PROFILE_REQUIRES_TEACHER_SELECTED")
    materialized = selection.offer._materialized.get("value")
    if materialized is None:
        raise ValueError("ISSUE1537_PROFILE_MATERIALIZATION_MISSING")
    observation = dict(
        getattr(materialized, "_performance_observation", {}) or {})
    return {
        "capability_id": selection.offer.capability_id,
        "source_identity": priority_source_materialization_identity(selection.offer),
        "selection_total_seconds": max(0.0, perf_counter() - started),
        "selected_source_materialization_seconds": float(
            selection.source_materialization_wall_seconds or 0.0),
        "cache_hit": bool(observation.get("source_materialization_cache_hit", 0)),
        "stages": {
            name: float(observation.get(name, 0.0) or 0.0)
            for name in STAGE_FIELDS
        },
        "source_preparation_counts": {
            "provider_draws": context._source_preparation_metrics.provider_draws,
            "source_context_builds": context._source_preparation_metrics.source_context_builds,
            "compiled_source_builds": context._source_preparation_metrics.compiled_source_builds,
        },
        "atlas_reload_count": int(
            selection.offer._planning_generation._authenticated_features.atlas_reload_count),
        "cache": cache.source_materialization_cache.metrics(),
    }


def profile(run_dir: Path, repeats: int, max_warm_seconds: float) -> dict:
    root = run_dir.expanduser().resolve()
    if not (root / ".issue1537-disposable-profile").is_file():
        raise ValueError("ISSUE1537_DISPOSABLE_PROFILE_MARKER_REQUIRED")
    cache = PriorityPlanningCache(root)
    samples = tuple(_one(root, cache) for _ in range(repeats))
    cold, warm = samples[0], samples[1:]
    stable_identity = all(
        sample["source_identity"] == cold["source_identity"] for sample in warm)
    warm_seconds = tuple(
        sample["selected_source_materialization_seconds"] for sample in warm)
    gate = bool(
        warm and stable_identity
        and all(sample["cache_hit"] for sample in warm)
        and max(warm_seconds) <= max_warm_seconds)
    return {
        "schema": SCHEMA,
        "tested_revision": _tested_revision(),
        "repeats": repeats,
        "max_warm_seconds": max_warm_seconds,
        "stable_identity": stable_identity,
        "warm_seconds": warm_seconds,
        "samples": samples,
        "gate_passed": gate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-warm-seconds", type=float, default=2.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 2 or args.max_warm_seconds <= 0:
        parser.error("--repeats must be >=2 and --max-warm-seconds must be positive")
    try:
        result = profile(args.run_dir, args.repeats, args.max_warm_seconds)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    payload = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
