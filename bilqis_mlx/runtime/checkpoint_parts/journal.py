"""Append and observe causal checkpoint events without changing learner authority."""
from __future__ import annotations

import bilqis_mlx.runtime.state as _runtime_state
import contextlib as _contextlib
import json as _json
import os as _os
import pathlib as _pathlib
import sys as _sys

from contextvars import ContextVar

_event_view = ContextVar("grade_a_event_view", default=None)

@_contextlib.contextmanager
def operator_view(callback):
    token = _event_view.set(callback)
    try:
        yield
    finally:
        _event_view.reset(token)


def _record(run_dir: _pathlib.Path, event: dict):
    path = run_dir / "events.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(_runtime_state._canonical(event) + "\n")
        stream.flush()
        _os.fsync(stream.fileno())
    if _event_view.get() is None:
        print(_json.dumps(event, sort_keys=True), flush=True)
    else:
        _notify_viewer(event)


def _notify_viewer(event: dict):
    """Send ephemeral operator telemetry without making it training evidence."""
    viewer = _event_view.get()
    if viewer is None:
        return
    try:
        viewer(event)
    except Exception as exc:
        print("DASHBOARD UNAVAILABLE: " + str(exc), file=_sys.stderr, flush=True)
