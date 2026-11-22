"""Interactive BAMF resume dispatch and terminal event routing."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from pathlib import Path
import sys
import threading

from .inspection import _print_status


LIVE_DASHBOARD_REFRESH_SECONDS = 0.5


@contextmanager
def _live_bamf_dashboard_refresh(board, *, interval=LIVE_DASHBOARD_REFRESH_SECONDS):
    if board is None:
        yield
        return
    stop = threading.Event()

    def redraw():
        while not stop.wait(interval):
            board.draw()

    thread = threading.Thread(target=redraw, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()


def _bamf_operator_admission_status(report):
    """Return safe admission terminal state that still permits retained learning."""
    if report.get("result") == "READY_TO_RESUME":
        return None
    if report.get("admission_policy") != "atlas-release":
        return False
    from bilqis_mlx.runtime.atlas_flywheel import AdmissionFlywheelStatus
    safe = {
        AdmissionFlywheelStatus.FIXED_POINT.value,
        AdmissionFlywheelStatus.WAITING_FOR_EVIDENCE.value,
        AdmissionFlywheelStatus.IMPLEMENTATION_UNCOVERED.value,
        AdmissionFlywheelStatus.LEASE_REQUIRED.value,
    }
    return report.get("result") if report.get("result") in safe else False


def _prepare_bamf_resume_board(args, run_dir: Path):
    if not sys.stdout.isatty():
        return None
    from bilqis_mlx.presentation.dashboard import build
    board = build(run_dir, reserve_gib=args.reserve_gib)
    telemetry = getattr(board, "school_telemetry", None)
    if telemetry is not None:
        telemetry.begin_execution(
            grade=board.state.get("prefix"), step=board.state.get("step"))
    from bilqis_mlx.presentation.bamf_terminal_accounting import (
        begin_bamf_command_accounting,
    )
    begin_bamf_command_accounting(board)
    board.mode = "BAMF | RESUMING"
    board.state["stop"] = "RUNNING"
    board.draw()
    return board


def _bamf_dashboard_event(board, event) -> None:
    if board is None:
        return
    from bilqis_mlx.presentation.dashboard import ingest
    with board._draw_lock:
        ingest(board, event)
        runtime_phase = event.get("_runtime_phase")
        if isinstance(runtime_phase, str) and runtime_phase:
            board.state["phase"] = runtime_phase
        if event.get("_dashboard_redraw", True):
            board.draw()


def _bamf_progress(board, message) -> None:
    if board is None:
        print("BAMF TRAINER: " + message, file=sys.stderr, flush=True)
        return
    with board._draw_lock:
        rows = board.rows["SYSTEM & QUALIFICATION"]
        retained = [row for row in rows if row.get("kind") != "TRAINER"]
        rows.clear()
        rows.extend(retained)
        rows.append({"kind": "TRAINER", "detail": str(message)})
        board.mode = "BAMF | LIVE"
        board.state["stop"] = "RUNNING"
        board.draw()


def _run_bamf_resume(
        args, run_dir: Path, board, parent_graph, profile_release, run_authority):
    from bilqis_mlx.control_plane.active_endpoint import advertise_active_endpoint
    from bilqis_mlx.runtime.bamf_operator import operate_bamf
    from bilqis_mlx.runtime.checkpoints import operator_view
    view = (
        operator_view(lambda event: _bamf_dashboard_event(board, event))
        if board is not None else nullcontext())
    with advertise_active_endpoint(run_dir), view, _live_bamf_dashboard_refresh(board):
        return operate_bamf(
            run_dir, minutes=args.minutes,
            max_visits=args.max_visits, steps_per_visit=args.steps_per_visit,
            batch_size=args.batch_size,
            reserve_gib=args.reserve_gib,
            source_prefetch_workers=args.source_prefetch_workers,
            strict_evidence=bool(getattr(args, "strict_evidence", False)),
            parent_graph=parent_graph,
            **({"profile_release": profile_release} if profile_release is not None else {}),
            run_authority=run_authority,
            progress=lambda message: _bamf_progress(board, message))


def _bamf_operator_report(result, admission_status, report):
    from dataclasses import asdict
    operator_report = asdict(result)
    if (operator_report.get("admission_status") is None
            and admission_status is not None):
        operator_report["admission_status"] = admission_status
        for field in ("admission_reason", "admission_advances"):
            if field in report:
                operator_report[field] = report[field]
    if operator_report.get("admission_status") is not None:
        from bilqis_mlx.errors.authority import authority_label
        operator_report["admission_label"] = authority_label(
            operator_report["admission_status"], domain="admission")
    return operator_report


def _finish_bamf_resume(board, args, run_dir: Path, operator_report):
    if board is None:
        return True, _print_status(operator_report), None
    from bilqis_mlx.presentation.dashboard import build
    prior_board = board
    session_baseline = getattr(prior_board, "_bamf_session_visit_baseline", None)
    board = build(run_dir, reserve_gib=args.reserve_gib)
    if session_baseline is not None:
        board._bamf_session_visit_baseline = set(session_baseline)
    from bilqis_mlx.presentation.bamf_terminal_accounting import (
        finalize_bamf_command_accounting, transfer_bamf_command_accounting,
    )
    transfer_bamf_command_accounting(prior_board, board)
    finalize_bamf_command_accounting(board, operator_report)
    board.mode = "BAMF | " + str(operator_report.get("status", "STOPPED"))
    board.state["stop"] = str(operator_report.get("status", "STOPPED"))
    board.draw()
    elapsed = operator_report.get("elapsed_seconds")
    elapsed_text = (
        f"{elapsed:.1f}s" if isinstance(elapsed, (int, float)) else "unknown")
    print(
        "BAMF TRAINER STOPPED: "
        f"{operator_report.get('status')} | visits {operator_report.get('visits')} | "
        f"accepted {operator_report.get('accepted')} | rejected {operator_report.get('rejected')} | "
        f"generation {operator_report.get('generation')} | "
        f"optimizer {operator_report.get('optimizer_step')} | elapsed {elapsed_text}",
        flush=True)
    return True, 0, None


def _dispatch_bamf_resume(
        args, run_dir: Path, report, parent_graph=None, run_authority=None):
    profile_release = getattr(args, "factory_profile_release", None)
    if profile_release is not None:
        from bilqis_mlx.runtime._release_adoption.native_profile import preview_profile_release
        report = {
            **report,
            "profile_expansion": preview_profile_release(run_dir, profile_release),
        }
    admission_status = _bamf_operator_admission_status(report)
    if (args.human_run and not args.dry_run
            and admission_status is not False):
        board = _prepare_bamf_resume_board(args, run_dir)
        result = _run_bamf_resume(
            args, run_dir, board, parent_graph, profile_release, run_authority)
        operator_report = _bamf_operator_report(result, admission_status, report)
        return _finish_bamf_resume(board, args, run_dir, operator_report)
    return True, _print_status(report), None


__all__ = ("_dispatch_bamf_resume",)
