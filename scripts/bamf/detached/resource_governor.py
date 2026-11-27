"""Portable trainer memory governor support for detached source snapshots.

Use the production Bilqis implementation when the runtime package is available.
Minimal checked-witness snapshots intentionally may contain only detached tooling,
so this module also carries a stdlib-only fallback with the same policy contract.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
import os
from pathlib import Path
import signal
import sys
import time


try:
    from bilqis_mlx.runtime.memory_safety import (
        DEFAULT_TRAINER_MEMORY_CEILING_GIB,
        GIB,
        MAX_TRAINER_MEMORY_CEILING_GIB,
        MIB,
        TRAINER_MEMORY_CEILING_ENV,
        TrainerMemoryPolicy,
        process_memory_snapshot,
    )
    from bilqis_mlx.runtime.trainer_resource_governor import (
        GOVERNOR_ENV,
        GOVERNOR_MODEL,
        GOVERNOR_NAME,
        supervise_running_process,
    )
except ModuleNotFoundError:
    MIB = 1024 ** 2
    GIB = 1024 ** 3
    DEFAULT_TRAINER_MEMORY_CEILING_GIB = 12.0
    MAX_TRAINER_MEMORY_CEILING_GIB = 16.0
    DEFAULT_WARNING_MARGIN_MIB = 2048
    DEFAULT_TRIP_MARGIN_MIB = 1024
    DEFAULT_SAMPLE_INTERVAL_MS = 20
    TRAINER_MEMORY_CEILING_ENV = "BILQIS_TRAINER_MEMORY_CEILING_GIB"
    GOVERNOR_NAME = "Deh Guhbohnayhituh"
    GOVERNOR_MODEL = "CR-8s"
    GOVERNOR_ENV = "BILQIS_TRAINER_RESOURCE_GOVERNOR"
    MAX_UNAVAILABLE_FOOTPRINT_SAMPLES = 3

    @dataclass(frozen=True)
    class TrainerMemoryPolicy:
        ceiling_bytes: int
        warning_bytes: int
        trip_bytes: int
        sample_interval_seconds: float

        @classmethod
        def from_gib(
                cls, ceiling_gib: float = DEFAULT_TRAINER_MEMORY_CEILING_GIB, *,
                warning_margin_mib: int = DEFAULT_WARNING_MARGIN_MIB,
                trip_margin_mib: int = DEFAULT_TRIP_MARGIN_MIB,
                sample_interval_ms: int = DEFAULT_SAMPLE_INTERVAL_MS):
            ceiling = float(ceiling_gib)
            if not (0 < ceiling <= MAX_TRAINER_MEMORY_CEILING_GIB):
                raise ValueError(
                    f"trainer memory ceiling must be greater than 0 and at most "
                    f"{MAX_TRAINER_MEMORY_CEILING_GIB:g} GiB")
            ceiling_bytes = int(ceiling * GIB)
            warning_bytes = ceiling_bytes - warning_margin_mib * MIB
            trip_bytes = ceiling_bytes - trip_margin_mib * MIB
            if warning_bytes <= 0 or warning_bytes >= trip_bytes:
                raise ValueError("memory margins leave no usable trainer budget")
            if sample_interval_ms <= 0:
                raise ValueError("memory sample interval must be positive")
            return cls(
                ceiling_bytes=ceiling_bytes,
                warning_bytes=warning_bytes,
                trip_bytes=trip_bytes,
                sample_interval_seconds=sample_interval_ms / 1000.0,
            )

        @classmethod
        def from_environment(cls, ceiling_gib: float | None = None):
            raw_ceiling = os.environ.get(TRAINER_MEMORY_CEILING_ENV)
            selected = (
                float(raw_ceiling) if ceiling_gib is None and raw_ceiling is not None
                else DEFAULT_TRAINER_MEMORY_CEILING_GIB if ceiling_gib is None
                else ceiling_gib)
            return cls.from_gib(
                selected,
                warning_margin_mib=int(os.environ.get(
                    "BILQIS_TRAINER_MEMORY_WARNING_MARGIN_MIB",
                    DEFAULT_WARNING_MARGIN_MIB)),
                trip_margin_mib=int(os.environ.get(
                    "BILQIS_TRAINER_MEMORY_TRIP_MARGIN_MIB",
                    DEFAULT_TRIP_MARGIN_MIB)),
                sample_interval_ms=int(os.environ.get(
                    "BILQIS_TRAINER_MEMORY_SAMPLE_MS",
                    DEFAULT_SAMPLE_INTERVAL_MS)),
            )

        def to_dict(self) -> dict:
            return asdict(self)

    @dataclass(frozen=True)
    class _ProcessMemorySnapshot:
        physical_footprint_bytes: int

    class _DarwinRusage(ctypes.Structure):
        _fields_ = [("uuid", ctypes.c_ubyte * 16)] + [
            (name, ctypes.c_uint64) for name in (
                "user", "system", "pkg_idle", "interrupt", "pageins", "wired",
                "resident", "footprint", "start", "exit")]

    _PROC_PID_RUSAGE = None
    if sys.platform == "darwin":
        _libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        _PROC_PID_RUSAGE = _libproc.proc_pid_rusage
        _PROC_PID_RUSAGE.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_void_p)
        _PROC_PID_RUSAGE.restype = ctypes.c_int

    def process_memory_snapshot(pid: int):
        if sys.platform == "darwin":
            value = _DarwinRusage()
            if _PROC_PID_RUSAGE(pid, 0, ctypes.byref(value)) != 0:
                return None
            return _ProcessMemorySnapshot(int(value.footprint))
        status = Path(f"/proc/{pid}/status")
        try:
            rows = status.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        rss_kib = next((
            int(row.split()[1]) for row in rows if row.startswith("VmRSS:")), None)
        return None if rss_kib is None else _ProcessMemorySnapshot(rss_kib * 1024)

    @dataclass(frozen=True)
    class _GovernorResult:
        status: str
        returncode: int | None
        guard_reason: str | None
        max_physical_footprint_bytes: int
        sample_count: int
        warning_emitted: bool
        policy: dict

        def to_dict(self) -> dict:
            return {
                "governor": GOVERNOR_NAME,
                "model": GOVERNOR_MODEL,
                **asdict(self),
            }

    def _footprint(pid: int) -> int | None:
        snapshot = process_memory_snapshot(pid)
        return None if snapshot is None else snapshot.physical_footprint_bytes

    def supervise_running_process(
            process, *, policy: TrainerMemoryPolicy,
            footprint_bytes=_footprint, sleep=time.sleep,
            kill_process_group=os.killpg, on_sample=None):
        maximum = 0
        count = 0
        warned = False
        unavailable = 0
        while True:
            code = process.poll()
            if code is not None:
                return _GovernorResult(
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
                    return _GovernorResult(
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
                    return _GovernorResult(
                        "RESOURCE_ENVELOPE_EXCEEDED", code,
                        "process physical footprint ceiling", maximum, count, warned,
                        policy.to_dict())
            sleep(policy.sample_interval_seconds)


__all__ = (
    "DEFAULT_TRAINER_MEMORY_CEILING_GIB", "GIB", "GOVERNOR_ENV",
    "GOVERNOR_MODEL", "GOVERNOR_NAME", "TRAINER_MEMORY_CEILING_ENV",
    "TrainerMemoryPolicy", "supervise_running_process",
)
