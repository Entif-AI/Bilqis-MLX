#!/usr/bin/env python3
"""Paired disposable witness for ADR-156 teacher-search yield."""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mlx.core as mx

import bilqis_mlx.runtime.outcomes.issuance as outcome_issuance
from bilqis_mlx.learning.teacher_strategy_population import (
    LEGACY_CHECKPOINT_RETIREMENT_POLICY,
)
from bilqis_mlx.presentation.operator_cli.bamf_resume_dispatch import (
    _live_bamf_dashboard_refresh,
)
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_operator.session import operate_bamf
import bilqis_mlx.runtime.active_grade_cadence_replay as cadence_replay
from bilqis_mlx.data_plane import data_plane


SOVEREIGN = Path("/Users/emilie/Code/bilqis-mlx-runs/aspirant")
VISITS = 12
STEPS_PER_VISIT = 12


def _clone_run(destination: Path) -> None:
    """Create an APFS clone when available; fall back to a metadata copy."""
    try:
        subprocess.run(
            ["cp", "-cR", str(SOVEREIGN), str(destination)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        shutil.copytree(SOVEREIGN, destination, copy_function=shutil.copy2)


def _clone_data_plane(destination: Path, source: Path | None = None) -> None:
    """Take a consistent private SQLite backup of the workstation data plane."""
    source = data_plane().path if source is None else Path(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source_db, sqlite3.connect(destination) as target_db:
        source_db.backup(target_db)
    for suffix in (".archive", ".objects"):
        source_sidecar = Path(str(source) + suffix)
        if not source_sidecar.is_dir():
            continue
        destination_sidecar = Path(str(destination) + suffix)
        subprocess.run(
            ["cp", "-cR", str(source_sidecar), str(destination_sidecar)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _seed_cadence_projection(run_dir: Path, plane_path: Path, state: dict) -> dict:
    """Bind a captured cadence projection to a disposable ledger and catch up its tail."""
    frontier = int(state["indexed_bytes"])
    events_path = run_dir / "events.jsonl"
    size = events_path.stat().st_size
    if size < frontier:
        raise RuntimeError("disposable cadence frontier precedes captured projection")
    tail_bytes = b""
    if size > frontier:
        with events_path.open("rb") as stream:
            stream.seek(frontier)
            tail_bytes = stream.read()
        with events_path.open("r+b") as stream:
            stream.truncate(frontier)
    with patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(plane_path)}):
        clone_plane = data_plane()
        try:
            indexed = clone_plane.indexed_event_tail(run_dir, 0)
            if indexed["indexed_bytes"] != frontier:
                raise RuntimeError("disposable cadence seed frontier drift")
            clone_plane.remember_event_projection(
                run_dir, cadence_replay._PROJECTION_KEY,
                cadence_replay._PROJECTION_SCHEMA,
                indexed["ledger_identity"], frontier, state["payload"])
        finally:
            if tail_bytes:
                with events_path.open("ab") as stream:
                    stream.write(tail_bytes)
        cadence_replay.authenticated_cadence_attempts(run_dir)
        rebound = clone_plane.event_projection_state(
            run_dir, cadence_replay._PROJECTION_KEY, cadence_replay._PROJECTION_SCHEMA)
        if rebound is None or rebound["indexed_bytes"] != events_path.stat().st_size:
            raise RuntimeError("disposable cadence projection did not catch up")
        return rebound


def _capture_cadence_projection() -> dict:
    state = data_plane().event_projection_state(
        SOVEREIGN, cadence_replay._PROJECTION_KEY, cadence_replay._PROJECTION_SCHEMA)
    if state is None:
        raise RuntimeError("sovereign cadence projection missing")
    return state


def _frozen_baseline(root: Path) -> tuple[Path, Path, dict]:
    """Freeze one disposable source, then make its cadence state self-contained."""
    captured = _capture_cadence_projection()
    run_dir = root / "baseline"
    plane_path = root / "baseline-plane.sqlite3"
    _clone_run(run_dir)
    events = run_dir / "events.jsonl"
    if events.stat().st_size:
        with events.open("rb") as stream:
            stream.seek(-1, 2)
            if stream.read(1) != b"\n":
                raise RuntimeError("disposable event ledger captured an incomplete line")
    _clone_data_plane(plane_path)
    state = _seed_cadence_projection(run_dir, plane_path, captured)
    with patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(plane_path)}):
        load_accepted_generation(run_dir)
    return run_dir, plane_path, state


def _dashboard(run_dir: Path):
    board = Dashboard(
        stream=io.StringIO(), tables=LETTER_TABLES,
        compact_header=True, show_all_panels=True)
    board.school_telemetry = SchoolTelemetry(board, active_grades=("A",))
    board.log_hint = str(run_dir / "events.jsonl")
    draws = {"count": 0, "seconds": 0.0}
    original = board.draw

    def measured():
        started = time.perf_counter()
        try:
            return original()
        finally:
            draws["count"] += 1
            draws["seconds"] += max(0.0, time.perf_counter() - started)

    board.draw = measured
    return board, draws


def _new_terminal_events(events_path: Path, start_offset: int):
    records = []
    with events_path.open("rb") as stream:
        stream.seek(start_offset)
        for raw in stream:
            try:
                event = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if event.get("event") in {"BAMF_CANDIDATE_REJECTED", "BAMF_CANDIDATE_ACCEPTED"}:
                records.append(event)
    return records


def _terminal_evidence(event: dict) -> dict:
    return event.get("evidence") if event.get("event") == "BAMF_CANDIDATE_REJECTED" else event


def _arm(run_dir: Path, *, treatment: bool, plane_source: Path,
         cadence_state: dict) -> dict:
    plane_path = run_dir / "plane.sqlite3"
    _clone_data_plane(plane_path, plane_source)
    _seed_cadence_projection(run_dir, plane_path, cadence_state)
    with patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(plane_path)}):
        events_path = run_dir / "events.jsonl"
        start_offset = events_path.stat().st_size
        before = load_accepted_generation(run_dir).retained_state.optimizer_step
        board, draws = _dashboard(run_dir)
        board.draw()
        progress = []
        patches = ExitStack()
        if not treatment:
            patches.enter_context(patch.object(
                outcome_issuance, "TARGET_FAILURE_CHECKPOINT_RETIREMENT_POLICY",
                LEGACY_CHECKPOINT_RETIREMENT_POLICY))
        started = time.perf_counter()
        try:
            with patches, _live_bamf_dashboard_refresh(board):
                result = operate_bamf(
                    run_dir, minutes=20, max_visits=VISITS,
                    steps_per_visit=STEPS_PER_VISIT, batch_size=32,
                    reserve_gib=100.0, source_prefetch_workers=2,
                    strict_mode=False, progress=progress.append)
        finally:
            wall = max(0.0, time.perf_counter() - started)
        mx.synchronize()
        board.draw()
        after = load_accepted_generation(run_dir).retained_state.optimizer_step
    terminal = _new_terminal_events(events_path, start_offset)
    evidence = [_terminal_evidence(event) for event in terminal]
    attempted = sum(
        int((record.get("how_outcome") or {}).get("attempted_steps", 0))
        for record in evidence)
    selection_reasons = Counter(
        record.get("teacher_selection_reason", "UNKNOWN") for record in evidence)
    retention_reasons = Counter(
        (record.get("how_outcome") or {}).get("decision", {}).get("reason", "UNKNOWN")
        for record in evidence)
    retained_steps = max(0, int(after) - int(before))
    teacher_rows = list(board.rows.get("SOUP & TEACHER", ()))
    return {
        "mode": "treatment" if treatment else "control",
        "visits_requested": VISITS,
        "candidate_horizon": STEPS_PER_VISIT,
        "operator_status": result.status,
        "operator_visits": result.visits,
        "operator_accepted": result.accepted,
        "operator_rejected": result.rejected,
        "wall_seconds": wall,
        "optimizer_step_before": int(before),
        "optimizer_step_after": int(after),
        "retained_optimizer_steps": retained_steps,
        "attempted_optimizer_steps": attempted,
        "attempted_steps_per_minute": 0.0 if wall <= 0 else attempted * 60.0 / wall,
        "retained_steps_per_minute": 0.0 if wall <= 0 else retained_steps * 60.0 / wall,
        "retention_efficiency": 0.0 if attempted <= 0 else retained_steps / attempted,
        "selection_reasons": dict(sorted(selection_reasons.items())),
        "retention_reasons": dict(sorted(retention_reasons.items())),
        "dashboard_draws": draws["count"],
        "dashboard_draw_wall_seconds": draws["seconds"],
        "teacher_rows_tail": teacher_rows[-8:],
        "progress_tail": progress[-12:],
    }


def main() -> int:
    if not mx.metal.is_available():
        raise SystemExit("Metal required")
    if not (SOVEREIGN / "events.jsonl").is_file():
        raise SystemExit("sovereign aspirant missing")
    sovereign_before = load_accepted_generation(SOVEREIGN).retained_state.optimizer_step
    sovereign_event_bytes = (SOVEREIGN / "events.jsonl").stat().st_size
    with tempfile.TemporaryDirectory(prefix="issue1566-teacher-yield-") as temporary:
        root = Path(temporary)
        baseline_dir, baseline_plane, cadence_state = _frozen_baseline(root)
        control_dir = root / "control"
        treatment_dir = root / "treatment"
        subprocess.run(
            ["cp", "-cR", str(baseline_dir), str(control_dir)], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(
            ["cp", "-cR", str(baseline_dir), str(treatment_dir)], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        control = _arm(
            control_dir, treatment=False, plane_source=baseline_plane,
            cadence_state=cadence_state)
        treatment = _arm(
            treatment_dir, treatment=True, plane_source=baseline_plane,
            cadence_state=cadence_state)
    sovereign_after = load_accepted_generation(SOVEREIGN).retained_state.optimizer_step
    sovereign_event_bytes_after = (SOVEREIGN / "events.jsonl").stat().st_size
    receipt = {
        "schema": "bilqis.bamf.issue1566-teacher-yield-witness/v1",
        "authorizing": False,
        "published": False,
        "sovereign_read_only": str(SOVEREIGN),
        "sovereign_optimizer_step_before": int(sovereign_before),
        "sovereign_optimizer_step_after": int(sovereign_after),
        "sovereign_event_bytes_before": sovereign_event_bytes,
        "sovereign_event_bytes_after": sovereign_event_bytes_after,
        "human_run_mutated": (
            int(sovereign_before) != int(sovereign_after)
            or sovereign_event_bytes != sovereign_event_bytes_after),
        "control_policy": {
            "checkpoint_retirement": "legacy-no-target-gain-v1",
        },
        "treatment_policy": {
            "checkpoint_retirement": "target-failure-v2",
        },
        "control": control,
        "treatment": treatment,
        "retained_steps_per_minute_delta": (
            treatment["retained_steps_per_minute"]
            - control["retained_steps_per_minute"]),
        "retention_efficiency_delta": (
            treatment["retention_efficiency"] - control["retention_efficiency"]),
    }
    print("ISSUE1566_TEACHER_YIELD " + json.dumps(receipt, sort_keys=True), flush=True)
    return int(receipt["human_run_mutated"])


if __name__ == "__main__":
    raise SystemExit(main())
