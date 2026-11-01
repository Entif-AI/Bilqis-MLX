"""Low-overhead, write-ahead timing markers for short human-run diagnostics."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time


SCHEMA = "bilqis.timing-trace/v2"
_ACTIVE_TRACE: ContextVar["TimingTrace | None"] = ContextVar(
    "bilqis_timing_trace", default=None)


def default_trace_path(run_dir: Path) -> Path:
    """Keep timing output outside the student's state directory."""
    run = Path(run_dir).expanduser().resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return run.parent / ".timing-traces" / run.name / f"timing-{stamp}.jsonl"


class TimingTrace:
    """Append each explicit timing marker immediately to a JSONL trace."""

    def __init__(self, path: Path, *, metadata: dict | None = None):
        self.path = Path(path).expanduser().resolve()
        self.metadata = dict(metadata or {})
        self._handle = None
        self._token = None
        self._sequence = 0
        self._last_ns: int | None = None
        self._base_monotonic_ns = 0
        self._base_wall_ns = 0

    def _write(self, record: str, *, timestamp_ns: int | None = None,
               duration_ns: int | None = None, **fields) -> int:
        if self._handle is None:
            return time.perf_counter_ns()
        now = time.perf_counter_ns() if timestamp_ns is None else timestamp_ns
        delta = 0 if self._last_ns is None else now - self._last_ns
        self._last_ns = now
        row = {
            "record": record,
            "sequence": self._sequence,
            "wall_time_ns": self._base_wall_ns + (now - self._base_monotonic_ns),
            "monotonic_ns": now,
            "delta_ns": delta,
            "delta_ms": delta / 1_000_000,
            **fields,
        }
        if duration_ns is not None:
            row["duration_ns"] = duration_ns
            row["duration_ms"] = duration_ns / 1_000_000
        self._sequence += 1
        self._handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        self._handle.flush()
        return now

    def __enter__(self):
        if self.path.exists():
            raise ValueError("TIMING_TRACE_PATH_ALREADY_EXISTS")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._base_monotonic_ns = time.perf_counter_ns()
        self._base_wall_ns = time.time_ns()
        self._handle = self.path.open("x", encoding="utf-8", buffering=1)
        self._handle.write(json.dumps({
            "record": "HEADER",
            "schema": SCHEMA,
            "clock": "time.perf_counter_ns",
            "base_monotonic_ns": self._base_monotonic_ns,
            "base_wall_time_ns": self._base_wall_ns,
            "pid": os.getpid(),
            "metadata": self.metadata,
            "timing_semantics": (
                "EXPLICIT_HOST_BOUNDARIES; MLX DEVICE WORK MAY COMPLETE ASYNCHRONOUSLY"),
        }, sort_keys=True, separators=(",", ":")) + "\n")
        self._handle.flush()
        self._token = _ACTIVE_TRACE.set(self)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._write(
                "FOOTER",
                exception_type=exc_type.__name__ if exc_type is not None else None)
        finally:
            if self._token is not None:
                _ACTIVE_TRACE.reset(self._token)
                self._token = None
            if self._handle is not None:
                self._handle.close()
                self._handle = None
        return False


def trace_mark(name: str, **fields) -> None:
    """Write one named boundary when a timing trace is active."""
    trace = _ACTIVE_TRACE.get()
    if trace is not None:
        trace._write("MARK", name=name, **fields)


@contextmanager
def trace_span(name: str, **fields):
    """Write start/end timing boundaries for one coarse operation."""
    trace = _ACTIVE_TRACE.get()
    if trace is None:
        yield
        return
    start_ns = trace._write("SPAN_START", name=name, **fields)
    try:
        yield
    except BaseException as exc:
        end_ns = time.perf_counter_ns()
        trace._write(
            "SPAN_END", timestamp_ns=end_ns, duration_ns=end_ns - start_ns,
            name=name, exception_type=type(exc).__name__, **fields)
        raise
    else:
        end_ns = time.perf_counter_ns()
        trace._write(
            "SPAN_END", timestamp_ns=end_ns, duration_ns=end_ns - start_ns,
            name=name, exception_type=None, **fields)
