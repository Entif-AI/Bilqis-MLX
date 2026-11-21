"""Bounded read of disposable BAMF trainer observation for terminal display."""
from __future__ import annotations

import json
from pathlib import Path


MAX_OBSERVATION_BYTES = 64 * 1024
MAX_VISITS = 8
SCHEMAS = frozenset(
    f"bilqis.bamf.trainer-observed/v{version}" for version in range(1, 8))


def read_bamf_terminal_observation(run_dir: Path):
    try:
        pointer = json.loads((run_dir / "bamf-state.json").read_text())
        run_id = pointer.get("run_id")
        with (run_dir / "trainer-observed.json").open("rb") as stream:
            raw = stream.read(MAX_OBSERVATION_BYTES + 1)
        if len(raw) > MAX_OBSERVATION_BYTES:
            return None
        payload = json.loads(raw)
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    visits = payload.get("visits")
    if (payload.get("schema") not in SCHEMAS or
            not isinstance(run_id, str) or not run_id or
            not isinstance(visits, list)):
        return None
    bounded = tuple(
        row for row in visits[-MAX_VISITS:]
        if isinstance(row, dict) and row.get("run_id") == run_id)
    return run_id, bounded
