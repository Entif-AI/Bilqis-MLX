"""C08-only MLX rank worker for one coordinator-issued logical step capsule."""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import os
from pathlib import Path
import pickle
import sys

import mlx.core as mx

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bilqis_mlx.runtime.factory_candidate_microbatch import (
    execute_factory_distributed_group,
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    return parser


def _broadcast_rank0_payload(group, payload: bytes) -> bytes:
    rank = group.rank()
    local_size = len(payload) if rank == 0 else 0
    sizes_array = mx.distributed.all_gather(
        mx.array([local_size], dtype=mx.int32), group=group)
    mx.eval(sizes_array)
    sizes = tuple(int(value) for value in sizes_array.tolist())
    if sizes[0] <= 0 or any(size != 0 for size in sizes[1:]):
        raise RuntimeError("C08_DISTRIBUTED_REQUEST_SOURCE_INVALID")
    width = sizes[0]
    local = payload if rank == 0 else b"\0" * width
    gathered = mx.distributed.all_gather(
        mx.array(list(local), dtype=mx.uint8), group=group)
    mx.eval(gathered)
    return bytes(gathered.tolist()[:width])


def _write_response(path: Path, outcome) -> None:
    payload = pickle.dumps(outcome, protocol=5)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    digest = path.with_name("response.sha256")
    with digest.open("w") as stream:
        stream.write(_sha256(payload) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def main() -> int:
    args = _parser().parse_args()
    backend = os.environ.get("BILQIS_C08_BACKEND")
    if not backend:
        raise RuntimeError("C08_DISTRIBUTED_BACKEND_ENV_REQUIRED")
    group = mx.distributed.init(strict=True, backend=backend)
    payload = args.request.read_bytes() if group.rank() == 0 else b""
    payload = _broadcast_rank0_payload(group, payload)
    if _sha256(payload) != args.request_sha256:
        raise RuntimeError("C08_DISTRIBUTED_REQUEST_DIGEST_DRIFT")
    capsule = pickle.loads(payload)
    if not isinstance(capsule, dict):
        raise RuntimeError("C08_DISTRIBUTED_CAPSULE_INVALID")
    if capsule.get("kind") == "collective-probe":
        local = mx.array([float(group.rank() + 1)], dtype=mx.float32)
        summed = mx.distributed.all_sum(local, group=group)
        ranks = mx.distributed.all_gather(
            mx.array([group.rank()], dtype=mx.int32), group=group)
        mx.eval(summed, ranks)
        outcome = {
            "schema": "bilqis.c08.worker-cohort-probe/v1",
            "world_size": group.size(),
            "ranks": tuple(int(item) for item in ranks.tolist()),
            "sum": float(summed.item()),
        }
    elif capsule.get("kind") == "factory-step":
        request = capsule.get("kwargs")
        if not isinstance(request, dict):
            raise RuntimeError("C08_DISTRIBUTED_CAPSULE_INVALID")
        outcome = execute_factory_distributed_group(
            **request, group=group, backend=backend,
            device_family=str(mx.device_info()["device_name"]),
            mlx_version=version("mlx"),
            numeric_precision="fp32")
    else:
        raise RuntimeError("C08_DISTRIBUTED_CAPSULE_KIND_INVALID")
    if group.rank() == 0:
        _write_response(args.response, outcome)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
