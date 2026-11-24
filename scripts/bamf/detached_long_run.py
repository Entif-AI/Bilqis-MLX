#!/usr/bin/env python3
"""Launch a long-running command detached from the agent socket.

The launcher writes durable PID/log/receipt files and asks macOS Notification
Center to alert the operator when the command exits. Interactive agents should
launch once, report the returned paths, and yield instead of polling.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

try:
    from scripts.bamf.detached.checked_launch import (
        CONTRACT_ENV, child_environment, prepare_checked_launch,
        read_checked_completion, read_checked_preflight, require_launch_contract,
    )
    from scripts.bamf.detached.support import (
        MUTATION_IGNORED_NAMES,
        _notify,
        _run_child_with_heartbeats,
        _snapshot_workdir,
        _tree_digest,
        _utc_now,
        _write_json,
    )
except ModuleNotFoundError:  # direct execution from scripts/bamf
    from detached.checked_launch import (
        CONTRACT_ENV, child_environment, prepare_checked_launch,
        read_checked_completion, read_checked_preflight, require_launch_contract,
    )
    from detached.support import (
        MUTATION_IGNORED_NAMES,
        _notify,
        _run_child_with_heartbeats,
        _snapshot_workdir,
        _tree_digest,
        _utc_now,
        _write_json,
    )


SCHEMA = "bilqis.bamf.detached-long-run/v2"
SOURCE_MUTATED_EXIT = 86
DEFAULT_HEARTBEAT_SECONDS = 60.0


def _initial_receipt(args) -> dict:
    workdir = args.workdir.resolve()
    source_workdir = (args.source_workdir or args.workdir).resolve()
    log = args.log.resolve()
    pid_file = args.pid_file.resolve()
    log.parent.mkdir(parents=True, exist_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
    started = _utc_now()
    heartbeat_seconds = float(getattr(args, "heartbeat_seconds", DEFAULT_HEARTBEAT_SECONDS))
    snapshot_sha256 = _tree_digest(workdir)
    mutation_guard_sha256 = _tree_digest(
        workdir, ignored_names=MUTATION_IGNORED_NAMES)
    return {
        "schema": SCHEMA,
        "status": "RUNNING",
        "label": args.label,
        "pid": os.getpid(),
        "source_workdir": str(source_workdir),
        "workdir": str(workdir),
        "source_sha256": args.source_sha256 or snapshot_sha256,
        "snapshot_sha256": snapshot_sha256,
        "mutation_guard_sha256": mutation_guard_sha256,
        "command": args.command,
        "checked_witness": getattr(args, "witness", None) is not None,
        "preflight_status": None,
        "raw_command_reason": getattr(args, "raw_command_reason", None),
        "log": str(log),
        "heartbeat_seconds": heartbeat_seconds,
        "started_at": started,
    }


def _fail_worker_start(args, initial, message, *, mutated=False):
    code = SOURCE_MUTATED_EXIT if mutated else 1
    with args.log.resolve().open("ab") as stream:
        stream.write(f"DETACHED_LONG_RUN_START_FAILED {message}\n".encode())
    _write_json(args.receipt.resolve(), {
        **initial, "status": "FAIL", "stage": "WORKER_START",
        "snapshot_sha256": args.snapshot_sha256 or initial["snapshot_sha256"],
        "final_snapshot_sha256": initial["snapshot_sha256"],
        "source_mutated": mutated, "returncode": code,
        "finished_at": _utc_now(), "error": message,
    })
    if not args.no_notify:
        _notify(args.label, code)
    return code


def _worker(args) -> int:
    initial = _initial_receipt(args)
    workdir = Path(initial["workdir"])
    source_workdir = Path(initial["source_workdir"])
    log = Path(initial["log"])
    receipt = args.receipt.resolve()
    started = initial["started_at"]
    snapshot_sha256 = initial["snapshot_sha256"]
    mutation_guard_sha256 = initial["mutation_guard_sha256"]
    heartbeat_seconds = initial["heartbeat_seconds"]
    if args.snapshot_sha256 and snapshot_sha256 != args.snapshot_sha256:
        return _fail_worker_start(
            args, initial, "detached source snapshot changed before worker start", mutated=True)
    if heartbeat_seconds <= 0:
        return _fail_worker_start(args, initial, "heartbeat seconds must be positive")
    if initial["checked_witness"]:
        try:
            initial.update(read_checked_preflight(args, initial))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            return _fail_worker_start(args, initial, f"checked witness preflight rejected: {error}")
    _write_json(receipt, initial)
    with log.open("ab", buffering=0) as stream:
        stream.write(
            (f"DETACHED_LONG_RUN_START {started} label={args.label!r} "
             f"pid={os.getpid()} command={args.command!r}\n").encode()
        )
        environment = child_environment(
            source_workdir, workdir, snapshot_sha256,
            checked=initial["checked_witness"])
        if initial["checked_witness"]:
            environment[CONTRACT_ENV] = initial["probe_contract_sha256"]
        offset = stream.tell()
        try:
            command_returncode = _run_child_with_heartbeats(
                args, workdir=workdir, stream=stream, receipt=receipt, initial=initial,
                heartbeat_seconds=heartbeat_seconds, environment=environment)
        except OSError as error:
            return _fail_worker_start(args, initial, str(error))
        proof, returncode = _checked_result(initial, log, offset, command_returncode, stream)
        finished = _utc_now()
        final_snapshot_sha256 = _tree_digest(workdir)
        final_mutation_guard_sha256 = _tree_digest(
            workdir, ignored_names=MUTATION_IGNORED_NAMES)
        source_mutated = final_mutation_guard_sha256 != mutation_guard_sha256
        returncode = SOURCE_MUTATED_EXIT if source_mutated else returncode
        stream.write(
            (f"DETACHED_LONG_RUN_END {finished} label={args.label!r} "
             f"returncode={returncode} source_mutated={source_mutated}\n").encode()
        )
    final = {
        **initial,
        **proof,
        "status": "PASS" if returncode == 0 else "FAIL",
        "returncode": returncode,
        "command_returncode": command_returncode,
        "source_mutated": source_mutated,
        "final_snapshot_sha256": final_snapshot_sha256,
        "final_mutation_guard_sha256": final_mutation_guard_sha256,
        "finished_at": finished,
    }
    _write_json(receipt, final)
    if not args.no_notify:
        _notify(args.label, returncode)
    return returncode


def _checked_result(initial, log, offset, code, stream):
    if not initial["checked_witness"] or code:
        return {}, code
    try:
        results = read_checked_completion(log, offset, initial["probe_contract_sha256"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        stream.write(f"DETACHED_LONG_RUN_PROOF_FAILED {error}\n".encode())
        return {"completion_error": str(error)}, 1
    return {"probe_results": results}, 0


def _launch(args) -> int:
    source_workdir = args.workdir.resolve()
    require_launch_contract(args, source_workdir)
    snapshot = (args.snapshot or (args.receipt.resolve().parent / "source-snapshot")).resolve()
    if args.witness is not None:
        outputs = [path.resolve() for path in (args.log, args.receipt, args.pid_file)]
        if len(set(outputs)) != len(outputs) or any(
                path.is_relative_to(snapshot) for path in outputs):
            raise SystemExit("checked witness log, receipt and PID must be distinct and outside snapshot")
    snapshot_receipt = _snapshot_workdir(source_workdir, snapshot)
    if args.witness is not None:
        args.command = prepare_checked_launch(
            args, source_workdir, snapshot, snapshot_receipt, SCHEMA)
    launcher = Path(__file__).resolve()
    if args.witness is not None:
        worker_script = snapshot / "scripts/bamf/detached_long_run.py"
    else:
        try:
            worker_script = snapshot / launcher.relative_to(source_workdir)
        except ValueError:
            worker_script = launcher
    worker_args = [
        sys.executable, "-B", str(worker_script), "_worker",
        "--label", args.label,
        "--workdir", str(snapshot),
        "--source-workdir", str(source_workdir),
        "--source-sha256", snapshot_receipt["source_sha256"],
        "--snapshot-sha256", snapshot_receipt["snapshot_sha256"],
        "--heartbeat-seconds", str(args.heartbeat_seconds),
        "--log", str(args.log.resolve()),
        "--receipt", str(args.receipt.resolve()),
        "--pid-file", str(args.pid_file.resolve()),
    ]
    if args.no_notify:
        worker_args.append("--no-notify")
    if args.witness is not None:
        worker_args.extend(["--witness", str(args.witness)])
    if args.raw_command_reason:
        worker_args.extend(["--raw-command-reason", args.raw_command_reason])
    worker_args.extend(["--", *args.command])
    process = subprocess.Popen(
        worker_args,
        cwd=snapshot,
        env=child_environment(source_workdir, snapshot, snapshot_receipt["snapshot_sha256"],
                              checked=args.witness is not None),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    print(json.dumps({
        "schema": SCHEMA,
        "status": "LAUNCHED",
        "preflight_status": "PASS" if args.witness is not None else None,
        "label": args.label,
        "launcher_pid": process.pid,
        "source_workdir": str(source_workdir),
        "source_snapshot": str(snapshot),
        **snapshot_receipt,
        "log": str(args.log.resolve()),
        "receipt": str(args.receipt.resolve()),
        "pid_file": str(args.pid_file.resolve()),
        "continuation": (
            "After the desktop notification, return to the controlling chat and "
            f"ask it to resume from receipt {args.receipt.resolve()}"
        ),
    }, indent=2, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("launch", "_worker"):
        subparser = subparsers.add_parser(mode)
        subparser.add_argument("--label", required=True)
        subparser.add_argument("--workdir", type=Path, required=True)
        subparser.add_argument("--log", type=Path, required=True)
        subparser.add_argument("--receipt", type=Path, required=True)
        subparser.add_argument("--pid-file", type=Path, required=True)
        subparser.add_argument("--snapshot", type=Path)
        subparser.add_argument("--source-workdir", type=Path)
        subparser.add_argument("--source-sha256")
        subparser.add_argument("--snapshot-sha256")
        subparser.add_argument(
            "--heartbeat-seconds", type=float, default=DEFAULT_HEARTBEAT_SECONDS,
            help="Seconds between durable liveness records while the child is running.",
        )
        subparser.add_argument("--no-notify", action="store_true")
        subparser.add_argument("--witness", type=Path,
                               help="Explicit checked witness defining prepare(argv, probes)")
        subparser.add_argument("--raw-command-reason",
                               help="Reason for deliberately running a legacy/raw Python harness")
        subparser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    return _worker(args) if args.mode == "_worker" else _launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
