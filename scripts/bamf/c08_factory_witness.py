"""Run the C08 preflight before the expensive real-Factory witness."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = ROOT / "scripts/bamf/c08_factory_preflight.py"
WITNESS = (
    "bilqis_mlx/runtime/tests/batch/factory/test_factory_training_execution.py::"
    "FactoryTrainingExecutionTests::"
    "test_production_step_accumulates_split_real_rows_into_one_optimizer_step"
)
RSS_LIMIT_KIB = 40 * 1024 * 1024
WALL_LIMIT_SECONDS = 1800


def _rss_kib(pid: int) -> int:
    completed = subprocess.run(
        ("ps", "-o", "rss=", "-p", str(pid)),
        check=False,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    return int(value) if value else 0


def _stop(process: subprocess.Popen, code: int, reason: str) -> int:
    print(reason, flush=True)
    process.terminate()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    return code


def main() -> int:
    preflight = subprocess.run(
        (sys.executable, "-B", str(PREFLIGHT)),
        cwd=ROOT,
        check=False,
        env=os.environ.copy(),
    )
    if preflight.returncode:
        return preflight.returncode

    print("C08_REAL_MLX_START", flush=True)
    process = subprocess.Popen(
        (sys.executable, "-m", "pytest", "-q", WITNESS),
        cwd=ROOT,
        env=os.environ.copy(),
    )
    started = time.monotonic()
    peak = 0
    while process.poll() is None:
        rss = _rss_kib(process.pid)
        peak = max(peak, rss)
        if rss > RSS_LIMIT_KIB:
            return _stop(
                process,
                137,
                f"RSS_GUARD_KILL pid={process.pid} rss_kib={rss} "
                f"limit_kib={RSS_LIMIT_KIB}",
            )
        elapsed = time.monotonic() - started
        if elapsed >= WALL_LIMIT_SECONDS:
            return _stop(
                process,
                124,
                f"TIME_GUARD_KILL pid={process.pid} elapsed={int(elapsed)}",
            )
        time.sleep(0.25)

    code = process.returncode
    print(
        "GUARD=NONE "
        f"PEAK_RSS_KB={peak} PEAK_RSS_GIB={peak / 1024 / 1024:.3f}",
        flush=True,
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
