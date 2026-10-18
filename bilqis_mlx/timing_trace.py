"""High-resolution chronological timing trace for short human-run diagnostics."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import threading
import time


SCHEMA = "bilqis.timing-trace/v1"


@dataclass(frozen=True)
class _Event:
    sequence: int
    monotonic_ns: int
    delta_ns: int
    event: str
    depth: int
    module: str
    function: str
    line: int
    duration_ns: int | None
    thread_id: int


def default_trace_path(run_dir: Path) -> Path:
    """Keep profiler output outside the student's state directory."""
    run = Path(run_dir).expanduser().resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return run.parent / ".timing-traces" / run.name / f"timing-{stamp}.jsonl"


class TimingTrace:
    """Record Bilqis Python function boundaries with monotonic nanosecond clocks."""

    def __init__(self, path: Path, *, package_root: Path, include_c_calls: bool = False,
                 metadata: dict | None = None):
        self.path = Path(path).expanduser().resolve()
        self.package_root = Path(package_root).expanduser().resolve()
        self.include_c_calls = bool(include_c_calls)
        self.metadata = dict(metadata or {})
        self._events: list[_Event] = []
        self._starts: dict[int, tuple[int, int]] = {}
        self._c_starts: dict[tuple[int, int], list[tuple[int, int]]] = {}
        self._scope_cache: dict[object, bool] = {}
        self._last_ns: int | None = None
        self._depth = 0
        self._base_monotonic_ns = 0
        self._base_wall_ns = 0

    def _in_scope(self, frame) -> bool:
        code = frame.f_code
        cached = self._scope_cache.get(code)
        if cached is not None:
            return cached
        try:
            filename = Path(code.co_filename).resolve()
            value = filename == self.package_root or self.package_root in filename.parents
        except OSError:
            value = False
        self._scope_cache[code] = value
        return value

    def _profile(self, frame, event, arg):
        supported = ("call", "return")
        if self.include_c_calls:
            supported += ("c_call", "c_return", "c_exception")
        if event not in supported or not self._in_scope(frame):
            return
        now = time.perf_counter_ns()
        delta = 0 if self._last_ns is None else now - self._last_ns
        self._last_ns = now
        frame_id = id(frame)
        function = frame.f_code.co_name
        if event == "call":
            depth = self._depth
            self._starts[frame_id] = (now, depth)
            self._depth += 1
            duration = None
        elif event == "return":
            started = self._starts.pop(frame_id, None)
            if started is None:
                depth, duration = max(0, self._depth - 1), None
            else:
                start_ns, depth = started
                duration = now - start_ns
            self._depth = max(0, depth)
        elif event == "c_call":
            depth = self._depth
            key = (frame_id, id(arg))
            self._c_starts.setdefault(key, []).append((now, depth))
            self._depth += 1
            duration = None
            function = "c:" + str(getattr(arg, "__name__", type(arg).__name__))
        else:
            key = (frame_id, id(arg))
            stack = self._c_starts.get(key, [])
            started = stack.pop() if stack else None
            if not stack:
                self._c_starts.pop(key, None)
            if started is None:
                depth, duration = max(0, self._depth - 1), None
            else:
                start_ns, depth = started
                duration = now - start_ns
            self._depth = max(0, depth)
            function = "c:" + str(getattr(arg, "__name__", type(arg).__name__))
        self._events.append(_Event(
            sequence=len(self._events), monotonic_ns=now, delta_ns=delta,
            event=event, depth=depth,
            module=str(frame.f_globals.get("__name__", "")),
            function=function, line=frame.f_lineno,
            duration_ns=duration, thread_id=threading.get_ident()))

    def __enter__(self):
        if self.path.exists():
            raise ValueError("TIMING_TRACE_PATH_ALREADY_EXISTS")
        self._base_monotonic_ns = time.perf_counter_ns()
        self._base_wall_ns = time.time_ns()
        sys.setprofile(self._profile)
        return self

    def __exit__(self, exc_type, exc, tb):
        sys.setprofile(None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("x", encoding="utf-8", buffering=1024 * 1024) as handle:
            handle.write(json.dumps({
                "record": "HEADER", "schema": SCHEMA,
                "clock": "time.perf_counter_ns",
                "base_monotonic_ns": self._base_monotonic_ns,
                "base_wall_time_ns": self._base_wall_ns,
                "pid": os.getpid(),
                "package_root": str(self.package_root),
                "include_c_calls": self.include_c_calls,
                "metadata": self.metadata,
                "timing_semantics": (
                    "HOST_FUNCTION_BOUNDARIES; MLX DEVICE WORK MAY COMPLETE ASYNCHRONOUSLY"),
            }, sort_keys=True) + "\n")
            for item in self._events:
                wall_ns = self._base_wall_ns + (
                    item.monotonic_ns - self._base_monotonic_ns)
                row = {
                    "record": "EVENT", "sequence": item.sequence,
                    "wall_time_ns": wall_ns,
                    "monotonic_ns": item.monotonic_ns,
                    "delta_ns": item.delta_ns,
                    "delta_ms": item.delta_ns / 1_000_000,
                    "event": item.event, "depth": item.depth,
                    "module": item.module, "function": item.function,
                    "line": item.line, "thread_id": item.thread_id,
                }
                if item.duration_ns is not None:
                    row["duration_ns"] = item.duration_ns
                    row["duration_ms"] = item.duration_ns / 1_000_000
                handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.write(json.dumps({
                "record": "FOOTER", "schema": SCHEMA,
                "event_count": len(self._events),
                "exception_type": exc_type.__name__ if exc_type is not None else None,
            }, sort_keys=True) + "\n")
        return False

