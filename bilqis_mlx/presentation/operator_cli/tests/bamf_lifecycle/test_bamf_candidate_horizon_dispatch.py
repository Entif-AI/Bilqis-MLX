"""BAMF resume forwards the operator-owned candidate horizon."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import threading
from unittest.mock import Mock, patch

from bilqis_mlx.presentation.operator_cli.command import _dispatch_bamf_resume
from bilqis_mlx.runtime.bamf_operator import BamfOperatorResult


def test_bamf_resume_forwards_explicit_candidate_horizon():
    args = SimpleNamespace(
        human_run=True,
        dry_run=False,
        minutes=90,
        max_visits=1,
        steps_per_visit=8,
        batch_size=18,
        reserve_gib=100.0,
        source_prefetch_workers=2,
        experiment_mastery_debt_min_utility=0.08,
    )
    report = {"result": "READY_TO_RESUME"}
    run_dir = Path("/run")
    result = BamfOperatorResult("VISIT_LIMIT", 1, 0, 1, 0, 0)
    with patch(
            "bilqis_mlx.control_plane.active_endpoint.advertise_active_endpoint",
            return_value=nullcontext()), patch(
            "bilqis_mlx.runtime.bamf_operator.operate_bamf",
            return_value=result) as operate:
        handled, _code, _next = _dispatch_bamf_resume(args, run_dir, report)

    assert handled is True
    assert operate.call_args.args == (run_dir,)
    assert operate.call_args.kwargs["minutes"] == 90
    assert operate.call_args.kwargs["max_visits"] == 1
    assert operate.call_args.kwargs["steps_per_visit"] == 8
    assert operate.call_args.kwargs["batch_size"] == 18
    assert operate.call_args.kwargs["reserve_gib"] == 100.0
    assert operate.call_args.kwargs["source_prefetch_workers"] == 2
    assert operate.call_args.kwargs["mastery_debt_min_utility"] == 0.08
    assert operate.call_args.kwargs["strict_evidence"] is False
    assert callable(operate.call_args.kwargs["progress"])


def test_bamf_resume_strict_evidence_is_explicit_opt_in():
    args = SimpleNamespace(
        human_run=True, dry_run=False, minutes=90, max_visits=1,
        steps_per_visit=6, batch_size=32, reserve_gib=100.0, source_prefetch_workers=2,
        strict_evidence=True)
    report = {"result": "READY_TO_RESUME"}
    run_dir = Path("/run")
    result = BamfOperatorResult("VISIT_LIMIT", 1, 0, 1, 0, 0)
    with patch(
            "bilqis_mlx.control_plane.active_endpoint.advertise_active_endpoint",
            return_value=nullcontext()), patch(
            "bilqis_mlx.runtime.bamf_operator.operate_bamf",
            return_value=result) as operate:
        handled, _code, _next = _dispatch_bamf_resume(args, run_dir, report)
    assert handled is True
    assert operate.call_args.kwargs["strict_evidence"] is True


def test_bamf_resume_preserves_explicit_serial_and_single_worker_modes():
    report = {"result": "READY_TO_RESUME"}
    run_dir = Path("/run")
    result = BamfOperatorResult("VISIT_LIMIT", 1, 0, 1, 0, 0)
    for workers in (0, 1):
        args = SimpleNamespace(
            human_run=True, dry_run=False, minutes=90, max_visits=1,
            steps_per_visit=8, batch_size=32, reserve_gib=100.0,
            source_prefetch_workers=workers)
        with patch(
                "bilqis_mlx.control_plane.active_endpoint.advertise_active_endpoint",
                return_value=nullcontext()), patch(
                "bilqis_mlx.runtime.bamf_operator.operate_bamf",
                return_value=result) as operate:
            handled, _code, _next = _dispatch_bamf_resume(args, run_dir, report)
        assert handled is True
        assert operate.call_args.kwargs["source_prefetch_workers"] == workers


def test_post_accept_admission_status_overrides_only_the_initial_fallback(capsys):
    args = SimpleNamespace(
        human_run=True, dry_run=False, minutes=90, max_visits=1,
        steps_per_visit=8, batch_size=32, reserve_gib=100.0, source_prefetch_workers=0)
    report = {
        "result": "WAITING_FOR_EVIDENCE",
        "admission_policy": "atlas-release",
    }
    run_dir = Path("/run")
    result = BamfOperatorResult(
        "VISIT_LIMIT", 1, 1, 0, 2, 4,
        admission_status="FIXED_POINT", admission_advances=1)
    parent_graph = {"tokens": ["source"]}
    with patch(
            "bilqis_mlx.control_plane.active_endpoint.advertise_active_endpoint",
            return_value=nullcontext()), patch(
                "bilqis_mlx.runtime.bamf_operator.operate_bamf",
                return_value=result) as operate:
        handled, _code, _next = _dispatch_bamf_resume(
            args, run_dir, report, parent_graph=parent_graph)
    assert handled is True
    assert operate.call_args.kwargs["parent_graph"] is parent_graph
    assert '"admission_status": "FIXED_POINT"' in capsys.readouterr().out


def test_interactive_bamf_resume_uses_compact_dashboard_not_final_json(capsys):
    args = SimpleNamespace(
        human_run=True, dry_run=False, minutes=90, max_visits=1,
        steps_per_visit=4, batch_size=32, reserve_gib=100.0, source_prefetch_workers=0)
    report = {"result": "READY_TO_RESUME"}
    run_dir = Path("/run")
    result = BamfOperatorResult(
        "VISIT_LIMIT", 1, 0, 1, 7, 31, elapsed_seconds=12.5)
    board = SimpleNamespace(
        mode="", state={}, rows={"SYSTEM & QUALIFICATION": []}, draw=Mock(), _draw_lock=threading.RLock())
    with patch(
            "bilqis_mlx.control_plane.active_endpoint.advertise_active_endpoint",
            return_value=nullcontext()), patch(
            "bilqis_mlx.runtime.bamf_operator.operate_bamf",
            return_value=result) as operate, patch(
            "sys.stdout.isatty", return_value=True), patch(
            "bilqis_mlx.presentation.dashboard.build", return_value=board):
        handled, code, _next = _dispatch_bamf_resume(args, run_dir, report)
        operate.call_args.kwargs["progress"]("planner: compiling semantic curriculum")

    output = capsys.readouterr().out
    assert handled is True and code == 0
    assert "BAMF TRAINER STOPPED: VISIT_LIMIT" in output
    assert '"status":' not in output
    assert board.rows["SYSTEM & QUALIFICATION"][-1] == {
        "kind": "TRAINER", "detail": "planner: compiling semantic curriculum"}
    # Initial and final draws are contractual; refresh-thread draws are timing-dependent.
    assert board.draw.call_count >= 2


def test_interactive_bamf_resume_routes_checkpoint_events_into_dashboard_not_stdout(capsys, tmp_path):
    args = SimpleNamespace(
        human_run=True, dry_run=False, minutes=90, max_visits=1,
        steps_per_visit=4, batch_size=32, reserve_gib=0.0, source_prefetch_workers=0)
    report = {"result": "READY_TO_RESUME"}
    result = BamfOperatorResult("VISIT_LIMIT", 1, 0, 1, 7, 31, elapsed_seconds=1.0)
    board = SimpleNamespace(
        mode="", state={}, rows={"SYSTEM & QUALIFICATION": []}, draw=Mock(), _draw_lock=threading.RLock())

    def operate(run_dir, **_kwargs):
        from bilqis_mlx.runtime import checkpoints
        checkpoints._record(run_dir, {"event": "BAMF_TEST_CHECKPOINT", "value": 7})
        return result

    with patch(
            "bilqis_mlx.control_plane.active_endpoint.advertise_active_endpoint",
            return_value=nullcontext()), patch(
            "bilqis_mlx.runtime.bamf_operator.operate_bamf", side_effect=operate), patch(
            "sys.stdout.isatty", return_value=True), patch(
            "bilqis_mlx.presentation.dashboard.build", return_value=board), patch(
            "bilqis_mlx.presentation.dashboard.ingest") as ingest:
        handled, code, _next = _dispatch_bamf_resume(args, tmp_path, report)

    output = capsys.readouterr().out
    assert handled is True and code == 0
    assert "BAMF_TEST_CHECKPOINT" not in output
    ingest.assert_any_call(board, {"event": "BAMF_TEST_CHECKPOINT", "value": 7})



def test_final_bamf_dashboard_preserves_command_session_baseline(capsys):
    args = SimpleNamespace(
        human_run=True, dry_run=False, minutes=90, max_visits=1,
        steps_per_visit=4, batch_size=32, reserve_gib=0.0, source_prefetch_workers=0)
    report = {"result": "READY_TO_RESUME"}
    result = BamfOperatorResult(
        "VISIT_LIMIT", 1, 1, 0, 7, 31, elapsed_seconds=1.0)
    baseline = {("visit", "before-command")}
    live_board = SimpleNamespace(
        mode="", state={}, rows={"SYSTEM & QUALIFICATION": []},
        draw=Mock(), _draw_lock=threading.RLock(),
        _bamf_session_visit_baseline=baseline)
    final_board = SimpleNamespace(
        mode="", state={}, rows={"SYSTEM & QUALIFICATION": []},
        draw=Mock(), _draw_lock=threading.RLock())

    with patch(
            "bilqis_mlx.control_plane.active_endpoint.advertise_active_endpoint",
            return_value=nullcontext()), patch(
            "bilqis_mlx.runtime.bamf_operator.operate_bamf",
            return_value=result), patch(
            "sys.stdout.isatty", return_value=True), patch(
            "bilqis_mlx.presentation.dashboard.build",
            side_effect=[live_board, final_board]):
        handled, code, _next = _dispatch_bamf_resume(args, Path("/run"), report)

    assert handled is True and code == 0
    assert final_board._bamf_session_visit_baseline == baseline
    assert final_board.state["visits"] == 1
    assert final_board.state["retained_visits"] == 1
    assert "accepted 1" in capsys.readouterr().out
