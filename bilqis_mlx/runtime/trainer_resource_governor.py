"""External memory containment for Bilqis trainer processes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from .memory_safety import (
    TRAINER_MEMORY_CEILING_ENV, TrainerMemoryPolicy, process_memory_snapshot,
)


GOVERNOR_NAME = "Deh Guhbohnayhituh"
GOVERNOR_MODEL = "CR-8s"
GOVERNOR_ENV = "BILQIS_TRAINER_RESOURCE_GOVERNOR"
SCHEMA = "bilqis.trainer-resource-governor.deh-guhbohnayhituh-cr8s/v1"
MAX_UNAVAILABLE_FOOTPRINT_SAMPLES = 3


@dataclass(frozen=True)
class GovernorResult:
    status: str
    returncode: int | None
    guard_reason: str | None
    max_physical_footprint_bytes: int
    sample_count: int
    warning_emitted: bool
    policy: dict

    def to_dict(self) -> dict:
        return {"schema": SCHEMA, "governor": GOVERNOR_NAME, "model": GOVERNOR_MODEL,
                **asdict(self)}


def governor_active() -> bool:
    return os.environ.get(GOVERNOR_ENV) == GOVERNOR_MODEL


def _physical_footprint_bytes(pid: int) -> int | None:
    sample = process_memory_snapshot(pid)
    return None if sample is None else sample.physical_footprint_bytes


def supervise_running_process(
        process, *, policy: TrainerMemoryPolicy,
        footprint_bytes=_physical_footprint_bytes, sleep=time.sleep,
        kill_process_group=os.killpg, on_sample=None) -> GovernorResult:
    maximum = 0
    count = 0
    warned = False
    unavailable = 0
    while True:
        code = process.poll()
        if code is not None:
            return GovernorResult(
                "EXITED", code, None, maximum, count, warned, policy.to_dict())
        footprint = footprint_bytes(process.pid)
        if footprint is None:
            unavailable += 1
            if unavailable >= MAX_UNAVAILABLE_FOOTPRINT_SAMPLES:
                try:
                    kill_process_group(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                code = process.wait()
                return GovernorResult(
                    "RESOURCE_GOVERNOR_UNAVAILABLE", code,
                    "process physical footprint measurement unavailable",
                    maximum, count, warned, policy.to_dict())
        else:
            unavailable = 0
            footprint = int(footprint)
            count += 1
            maximum = max(maximum, footprint)
            warned = warned or footprint >= policy.warning_bytes
            if on_sample is not None:
                on_sample(footprint, maximum, count, warned)
            if footprint >= policy.trip_bytes:
                try:
                    kill_process_group(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                code = process.wait()
                return GovernorResult(
                    "RESOURCE_ENVELOPE_EXCEEDED", code,
                    "process physical footprint ceiling", maximum, count, warned,
                    policy.to_dict())
        sleep(policy.sample_interval_seconds)


def _write_receipt(path: Path, result: GovernorResult, command) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**result.to_dict(), "command": list(command)}
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def run_governed_command(
        command, *, policy: TrainerMemoryPolicy, cwd=None, env=None,
        receipt_path: Path | None = None, stdout=None, stderr=None) -> GovernorResult:
    environment = dict(os.environ if env is None else env)
    environment[GOVERNOR_ENV] = GOVERNOR_MODEL
    process = subprocess.Popen(
        list(command), cwd=cwd, env=environment, stdout=stdout, stderr=stderr,
        start_new_session=True)
    try:
        result = supervise_running_process(process, policy=policy)
    except KeyboardInterrupt:
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        result = GovernorResult(
            "INTERRUPTED", process.wait(), "operator interrupt", 0, 0, False,
            policy.to_dict())
    if receipt_path is not None:
        _write_receipt(Path(receipt_path), result, command)
    return result


def run_governed_train(raw_argv, *, run_dir: Path, ceiling_gib: float) -> int:
    policy = TrainerMemoryPolicy.from_environment(ceiling_gib)
    run_dir = Path(run_dir).expanduser()
    receipt = run_dir.parent / f".{run_dir.name}.trainer-resource-governor.json"
    command = [sys.executable, "-B", "-m", "bilqis_mlx.cli", *raw_argv]
    environment = dict(os.environ)
    environment[TRAINER_MEMORY_CEILING_ENV] = str(ceiling_gib)
    result = run_governed_command(
        command, policy=policy, env=environment, receipt_path=receipt)
    if result.status in {"RESOURCE_ENVELOPE_EXCEEDED", "RESOURCE_GOVERNOR_UNAVAILABLE"}:
        print(
            f"TRAINER RESOURCE GUARD TRIPPED: {GOVERNOR_NAME} ({GOVERNOR_MODEL}) "
            f"stopped the trainer ({result.guard_reason}). Receipt: {receipt}",
            file=sys.stderr,
        )
        return 128 + signal.SIGKILL
    return int(result.returncode or 0)


__all__ = (
    "GOVERNOR_ENV", "GOVERNOR_MODEL", "GOVERNOR_NAME", "GovernorResult",
    "governor_active", "run_governed_command", "run_governed_train",
    "supervise_running_process",
)
