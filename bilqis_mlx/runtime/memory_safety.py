"""Shared trainer memory policy and retained-memory plateau checks."""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import gc
import os
from pathlib import Path
import sys
import tracemalloc


MIB = 1024 ** 2
GIB = 1024 ** 3
DEFAULT_TRAINER_MEMORY_CEILING_GIB = 12.0
MAX_TRAINER_MEMORY_CEILING_GIB = 16.0
DEFAULT_WARNING_MARGIN_MIB = 2048
DEFAULT_TRIP_MARGIN_MIB = 1024
DEFAULT_SAMPLE_INTERVAL_MS = 20
TRAINER_MEMORY_CEILING_ENV = "BILQIS_TRAINER_MEMORY_CEILING_GIB"


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
        if (type(warning_margin_mib) is not int or type(trip_margin_mib) is not int
                or warning_margin_mib <= trip_margin_mib or trip_margin_mib <= 0):
            raise ValueError("memory warning margin must exceed the positive trip margin")
        if type(sample_interval_ms) is not int or sample_interval_ms <= 0:
            raise ValueError("memory sample interval must be positive")
        ceiling_bytes = int(ceiling * GIB)
        warning_bytes = ceiling_bytes - warning_margin_mib * MIB
        trip_bytes = ceiling_bytes - trip_margin_mib * MIB
        if warning_bytes <= 0 or warning_bytes >= trip_bytes:
            raise ValueError("memory margins leave no usable trainer budget")
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
        return {
            "ceiling_bytes": self.ceiling_bytes,
            "warning_bytes": self.warning_bytes,
            "trip_bytes": self.trip_bytes,
            "sample_interval_seconds": self.sample_interval_seconds,
        }


@dataclass(frozen=True)
class ProcessMemorySnapshot:
    physical_footprint_bytes: int
    rss_bytes: int
    source: str


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


def process_memory_snapshot(pid: int) -> ProcessMemorySnapshot | None:
    if type(pid) is not int or pid <= 0:
        raise ValueError("pid must be a positive integer")
    if sys.platform == "darwin":
        value = _DarwinRusage()
        if _PROC_PID_RUSAGE(pid, 0, ctypes.byref(value)) != 0:
            return None
        return ProcessMemorySnapshot(
            physical_footprint_bytes=int(value.footprint),
            rss_bytes=int(value.resident),
            source="proc_pid_rusage",
        )
    status = Path(f"/proc/{pid}/status")
    try:
        rows = status.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    rss_kib = next((
        int(row.split()[1]) for row in rows if row.startswith("VmRSS:")), None)
    if rss_kib is None:
        return None
    rss = rss_kib * 1024
    return ProcessMemorySnapshot(rss, rss, "procfs-rss-fallback")


@dataclass(frozen=True)
class MemoryPlateauSample:
    ordinal: int
    physical_footprint_bytes: int
    python_heap_bytes: int | None = None
    mlx_active_bytes: int | None = None
    mlx_cache_bytes: int | None = None
    mlx_peak_bytes: int | None = None
    live_mlx_bytes: int | None = None


@dataclass(frozen=True)
class MemoryPlateauPolicy:
    warmup_samples: int = 2
    min_samples: int = 6
    max_net_growth_bytes: int = 512 * MIB
    max_slope_bytes_per_sample: int = 128 * MIB


@dataclass(frozen=True)
class MemoryPlateauResult:
    plateau: bool
    sample_count: int
    net_growth_bytes: int
    slope_bytes_per_sample: float
    reasons: tuple[str, ...]
    last_unattributed_mlx_bytes: int | None


def _slope(values: tuple[int, ...]) -> float:
    count = len(values)
    x_mean = (count - 1) / 2.0
    y_mean = sum(values) / count
    numerator = sum((index - x_mean) * (value - y_mean)
                    for index, value in enumerate(values))
    denominator = sum((index - x_mean) ** 2 for index in range(count))
    return numerator / denominator if denominator else 0.0


def assess_memory_plateau(
        samples: tuple[MemoryPlateauSample, ...] | list[MemoryPlateauSample],
        policy: MemoryPlateauPolicy | None = None) -> MemoryPlateauResult:
    policy = policy or MemoryPlateauPolicy()
    samples = tuple(samples)
    if len(samples) < policy.min_samples:
        raise ValueError("memory plateau requires more representative samples")
    if not (0 <= policy.warmup_samples < len(samples) - 1):
        raise ValueError("memory plateau warmup leaves too few samples")
    window = samples[policy.warmup_samples:]
    values = tuple(int(sample.physical_footprint_bytes) for sample in window)
    net_growth = values[-1] - values[0]
    slope = _slope(values)
    reasons = []
    if net_growth > policy.max_net_growth_bytes:
        reasons.append("net retained-memory growth")
    if slope > policy.max_slope_bytes_per_sample:
        reasons.append("positive retained-memory slope")
    last = samples[-1]
    unattributed = None
    if last.mlx_active_bytes is not None and last.live_mlx_bytes is not None:
        unattributed = max(0, last.mlx_active_bytes - last.live_mlx_bytes)
    return MemoryPlateauResult(
        plateau=not reasons,
        sample_count=len(samples),
        net_growth_bytes=net_growth,
        slope_bytes_per_sample=slope,
        reasons=tuple(reasons),
        last_unattributed_mlx_bytes=unattributed,
    )


def capture_quiescent_memory_sample(
        ordinal: int, *, mx=None, live_mlx_bytes: int | None = None,
        collect_python: bool = True) -> MemoryPlateauSample:
    if collect_python:
        gc.collect()
    mlx_active = mlx_cache = mlx_peak = None
    if mx is not None:
        mx.synchronize()
        mx.clear_cache()
        mlx_active = int(mx.get_active_memory())
        mlx_cache = int(mx.get_cache_memory())
        mlx_peak = int(mx.get_peak_memory())
    python_heap = tracemalloc.get_traced_memory()[0] if tracemalloc.is_tracing() else None
    process = process_memory_snapshot(os.getpid())
    if process is None:
        raise RuntimeError("process memory measurement unavailable")
    return MemoryPlateauSample(
        ordinal=ordinal,
        physical_footprint_bytes=process.physical_footprint_bytes,
        python_heap_bytes=python_heap,
        mlx_active_bytes=mlx_active,
        mlx_cache_bytes=mlx_cache,
        mlx_peak_bytes=mlx_peak,
        live_mlx_bytes=live_mlx_bytes,
    )


__all__ = (
    "DEFAULT_TRAINER_MEMORY_CEILING_GIB", "GIB", "MAX_TRAINER_MEMORY_CEILING_GIB",
    "MIB", "MemoryPlateauPolicy", "MemoryPlateauResult", "MemoryPlateauSample",
    "ProcessMemorySnapshot", "TrainerMemoryPolicy", "assess_memory_plateau",
    "TRAINER_MEMORY_CEILING_ENV", "capture_quiescent_memory_sample",
    "process_memory_snapshot",
)
