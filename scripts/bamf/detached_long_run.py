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


def _worker(args) -> int:
    workdir = args.workdir.resolve()
    source_workdir = (args.source_workdir or args.workdir).resolve()
    log = args.log.resolve()
    receipt = args.receipt.resolve()
    pid_file = args.pid_file.resolve()
    log.parent.mkdir(parents=True, exist_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
    started = _utc_now()
    heartbeat_seconds = float(getattr(args, "heartbeat_seconds", DEFAULT_HEARTBEAT_SECONDS))
    if heartbeat_seconds <= 0:
        raise SystemExit("heartbeat seconds must be positive")
    snapshot_sha256 = _tree_digest(workdir)
    mutation_guard_sha256 = _tree_digest(
        workdir, ignored_names=MUTATION_IGNORED_NAMES)
    if args.snapshot_sha256 and snapshot_sha256 != args.snapshot_sha256:
        raise SystemExit("detached source snapshot changed before worker start")
    initial = {
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
        "log": str(log),
        "heartbeat_seconds": heartbeat_seconds,
        "started_at": started,
    }
    _write_json(receipt, initial)
    with log.open("ab", buffering=0) as stream:
        stream.write(
            (f"DETACHED_LONG_RUN_START {started} label={args.label!r} "
             f"pid={os.getpid()} command={args.command!r}\n").encode()
        )
        environment = os.environ.copy()
        environment.update({
            "BILQIS_DETACHED_SOURCE_WORKDIR": str(source_workdir),
            "BILQIS_DETACHED_SOURCE_SNAPSHOT": str(workdir),
            "BILQIS_DETACHED_SOURCE_SHA256": snapshot_sha256,
            "PYTHONUNBUFFERED": "1",
        })
        command_returncode = _run_child_with_heartbeats(
            args,
            workdir=workdir,
            stream=stream,
            receipt=receipt,
            initial=initial,
            heartbeat_seconds=heartbeat_seconds,
            environment=environment,
        )
        finished = _utc_now()
        final_snapshot_sha256 = _tree_digest(workdir)
        final_mutation_guard_sha256 = _tree_digest(
            workdir, ignored_names=MUTATION_IGNORED_NAMES)
        source_mutated = final_mutation_guard_sha256 != mutation_guard_sha256
        returncode = SOURCE_MUTATED_EXIT if source_mutated else command_returncode
        stream.write(
            (f"DETACHED_LONG_RUN_END {finished} label={args.label!r} "
             f"returncode={returncode} source_mutated={source_mutated}\n").encode()
        )
    final = {
        **initial,
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


def _launch(args) -> int:
    if not args.command:
        raise SystemExit("command required after --")
    source_workdir = args.workdir.resolve()
    snapshot = (args.snapshot or (args.receipt.resolve().parent / "source-snapshot")).resolve()
    snapshot_receipt = _snapshot_workdir(source_workdir, snapshot)
    launcher = Path(__file__).resolve()
    try:
        worker_script = snapshot / launcher.relative_to(source_workdir)
    except ValueError:
        worker_script = launcher
    worker_args = [
        sys.executable, str(worker_script), "_worker",
        "--label", args.label,
        "--workdir", str(snapshot),
        "--source-workdir", str(source_workdir),
        "--source-sha256", snapshot_receipt["source_sha256"],
        "--snapshot-sha256", snapshot_receipt["snapshot_sha256"],
        "--heartbeat-seconds", str(args.heartbeat_seconds),
        "--log", str(args.log),
        "--receipt", str(args.receipt),
        "--pid-file", str(args.pid_file),
    ]
    if args.no_notify:
        worker_args.append("--no-notify")
    worker_args.extend(["--", *args.command])
    process = subprocess.Popen(
        worker_args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    print(json.dumps({
        "schema": SCHEMA,
        "status": "LAUNCHED",
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
        subparser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    return _worker(args) if args.mode == "_worker" else _launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
