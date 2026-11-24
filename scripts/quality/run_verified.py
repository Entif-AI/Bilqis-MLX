#!/usr/bin/env python3
"""Run an existing CI gate or reuse an exact trusted passing receipt."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import time

from .verification_frontier import execution_identity, trusted_producer
from .verification_ledger import VerificationLedger, full_requested, ledger_path

ROOT = Path(__file__).resolve().parents[2]
CHECKS = ("bamf-readiness",)


def valid_pass(payload) -> bool:
    return (isinstance(payload, dict) and payload.get("result") == "PASS"
            and payload.get("repository") == os.environ.get("GITHUB_REPOSITORY")
            and payload.get("producer_event") in ("push", "schedule")
            and isinstance(payload.get("verified_head"), str)
            and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", payload["verified_head"]) is not None
            and isinstance(payload.get("run_id"), str) and payload["run_id"].isdigit()
            and isinstance(payload.get("run_attempt"), str) and payload["run_attempt"].isdigit()
            and type(payload.get("duration_seconds")) in (float, int)
            and payload["duration_seconds"] >= 0)


def execute(root: Path, check: str, command: list[str], *, full: bool = False) -> int:
    started = time.perf_counter()
    command_env = dict(os.environ, GIT_NO_REPLACE_OBJECTS="1")
    try:
        identity = execution_identity(root, check, command)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        identity = None
    if identity is None:
        print(f"VERIFICATION_LEDGER {check} FRESH identity-unavailable", flush=True)
        return subprocess.run(command, cwd=root, env=command_env).returncode
    head, key = identity
    with VerificationLedger(ledger_path(root), full=full or full_requested()) as ledger:
        receipt = ledger.lookup(check, key, validate=valid_pass)
        if receipt is not None:
            print(f"TEST_EVIDENCE_REUSED check={check} tested_head={receipt['verified_head']} "
                  f"run={receipt['run_id']} attempt={receipt['run_attempt']} "
                  f"previous_seconds={receipt['duration_seconds']:.3f}", flush=True)
            ledger.report(check, time.perf_counter() - started)
            return 0
        print(f"VERIFICATION_LEDGER {check} FRESH frontier={key}", flush=True)
        command_started = time.perf_counter()
        result = subprocess.run(command, cwd=root, env=command_env)
        duration = time.perf_counter() - command_started
        if result.returncode == 0 and trusted_producer():
            run_id = os.environ.get("GITHUB_RUN_ID", "")
            attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
            receipt = dict(result="PASS", verified_head=head, run_id=run_id,
                           run_attempt=attempt, duration_seconds=round(duration, 6),
                           repository=os.environ.get("GITHUB_REPOSITORY"),
                           producer_event=os.environ.get("GITHUB_EVENT_NAME"))
            if valid_pass(receipt):
                # Never publish a proof after a command changed its input frontier.
                try:
                    unchanged = execution_identity(root, check, command) == identity
                except (OSError, ValueError, TypeError, subprocess.SubprocessError):
                    unchanged = False
                if unchanged:
                    ledger.record(check, key, receipt)
        ledger.report(check, time.perf_counter() - started)
        return result.returncode


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=CHECKS, required=True)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    return execute(ROOT, args.check, command, full=args.full)


if __name__ == "__main__":
    raise SystemExit(main())
