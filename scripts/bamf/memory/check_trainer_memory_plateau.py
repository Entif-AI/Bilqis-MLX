#!/usr/bin/env python3
"""Fail when bounded trainer telemetry shows retained-memory ratcheting."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bilqis_mlx.runtime.memory_safety import (
    MIB, MemoryPlateauPolicy, MemoryPlateauSample, assess_memory_plateau,
)


def _samples(payload: dict) -> tuple[MemoryPlateauSample, ...]:
    visits = payload.get("visits")
    if not isinstance(visits, list):
        raise ValueError("trainer observation visits missing")
    candidates = []
    for visit in reversed(visits):
        steps = visit.get("candidate_steps") if isinstance(visit, dict) else None
        if isinstance(steps, list):
            usable = [step for step in steps if isinstance(step, dict)
                      and type(step.get("physical_footprint_bytes")) is int]
            if usable:
                candidates = usable
                break
    if not candidates:
        raise ValueError("trainer observation has no candidate-step memory samples")
    return tuple(MemoryPlateauSample(
        ordinal=int(step.get("candidate_step", index)),
        physical_footprint_bytes=step["physical_footprint_bytes"],
        python_heap_bytes=step.get("python_heap_bytes"),
        mlx_active_bytes=step.get("mlx_active_bytes"),
        mlx_cache_bytes=step.get("mlx_cache_bytes"),
        mlx_peak_bytes=step.get("mlx_peak_bytes"),
        live_mlx_bytes=step.get("live_mlx_bytes"),
    ) for index, step in enumerate(candidates, start=1))


def check_observation(
        path: Path, *, warmup_samples=2, min_samples=6,
        max_net_growth_mib=512, max_slope_mib=128):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    result = assess_memory_plateau(
        _samples(payload),
        MemoryPlateauPolicy(
            warmup_samples=warmup_samples,
            min_samples=min_samples,
            max_net_growth_bytes=max_net_growth_mib * MIB,
            max_slope_bytes_per_sample=max_slope_mib * MIB,
        ),
    )
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observation", type=Path)
    parser.add_argument("--warmup-samples", type=int, default=2)
    parser.add_argument("--min-samples", type=int, default=6)
    parser.add_argument("--max-net-growth-mib", type=int, default=512)
    parser.add_argument("--max-slope-mib", type=int, default=128)
    args = parser.parse_args(argv)
    result = check_observation(
        args.observation,
        warmup_samples=args.warmup_samples,
        min_samples=args.min_samples,
        max_net_growth_mib=args.max_net_growth_mib,
        max_slope_mib=args.max_slope_mib,
    )
    print(json.dumps({
        "schema": "bilqis.trainer-memory-plateau/v1",
        "plateau": result.plateau,
        "sample_count": result.sample_count,
        "net_growth_bytes": result.net_growth_bytes,
        "slope_bytes_per_sample": result.slope_bytes_per_sample,
        "reasons": result.reasons,
        "last_unattributed_mlx_bytes": result.last_unattributed_mlx_bytes,
    }, indent=2, sort_keys=True))
    return 0 if result.plateau else 1


if __name__ == "__main__":
    raise SystemExit(main())
