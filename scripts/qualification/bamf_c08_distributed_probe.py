"""Disposable C08.4 local collective probe; never touches learner/canonical state."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mlx.core as mx

from bilqis_mlx.runtime.distributed_step import (
    DistributedStepManifest, ReductionPolicy, WorkerIdentity, partition_logical_batch,
)

ROWS = tuple(f"row:{index}" for index in range(7))
GENERATION = "generation:" + "a" * 64
SOURCE_RELEASE = "b" * 64
TOPOLOGY = "c" * 64


def main() -> None:
    group = mx.distributed.init(strict=True, backend="ring")
    size = group.size()
    rank = group.rank()
    workers = tuple(WorkerIdentity(
        rank=index, worker_id=f"local-probe:{index}",
        device_family="LOCAL_SAME_HOST_PROBE", memory_bytes=1,
        measured_compute_gflops=0.0, memory_bandwidth_gbps=0.0,
        interconnect="loopback-ring",
    ) for index in range(size))
    manifest = DistributedStepManifest.create(
        retained_generation=GENERATION, curriculum_release=SOURCE_RELEASE,
        logical_batch_row_ids=ROWS, partition_seed=73, workers=workers,
        mlx_version="local-installed", backend="ring", numeric_precision="fp32",
        reduction_policy=ReductionPolicy.WEIGHTED_MEAN_FP32,
        topology_digest=TOPOLOGY,
    )
    partitions = partition_logical_batch(manifest)
    local_rows = partitions[rank]
    local_sum = sum(float(row.split(":", 1)[1]) + 1.0 for row in local_rows)
    pair = mx.array([local_sum, float(len(local_rows))], dtype=mx.float32)
    reduced = mx.distributed.all_sum(pair, group=group)
    mx.eval(reduced)
    global_mean = float(reduced[0].item() / reduced[1].item())
    expected = sum(range(1, len(ROWS) + 1)) / len(ROWS)
    if abs(global_mean - expected) > 1e-6:
        raise RuntimeError("BAMF_C08_DISTRIBUTED_LOCAL_PROBE_REDUCTION_DRIFT")
    print(json.dumps({
        "rank": rank,
        "world_size": size,
        "manifest_digest": manifest.execution_digest,
        "rows": local_rows,
        "global_mean_fp32": global_mean,
        "expected_mean": expected,
        "probe_scope": "SAME_HOST_DISPOSABLE_NOT_HETEROGENEOUS_ACCEPTANCE",
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
