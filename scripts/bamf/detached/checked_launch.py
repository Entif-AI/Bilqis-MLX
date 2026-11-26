"""Preflight the explicit witness protocol before starting a detached worker."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import re

from .support import _discard_snapshot, _git_toplevel, _tree_digest, _utc_now, _write_json


PREFLIGHT_TIMEOUT = 30
CONTRACT_ENV = "BILQIS_CHECKED_WITNESS_CONTRACT"


def child_environment(source: Path, snapshot: Path, digest: str, *, checked: bool):
    environment = os.environ.copy()
    environment.update({
        "BILQIS_DETACHED_SOURCE_WORKDIR": str(source),
        "BILQIS_DETACHED_SOURCE_SNAPSHOT": str(snapshot),
        "BILQIS_DETACHED_SOURCE_SHA256": digest,
        "PYTHONUNBUFFERED": "1",
    })
    if checked:
        environment.update({"PYTHONPATH": str(snapshot), "PYTHONDONTWRITEBYTECODE": "1"})
        environment.pop(CONTRACT_ENV, None)
    return environment


def read_checked_preflight(args, initial: dict) -> dict:
    """Accept only the prepared receipt for this exact worker command and source."""
    prepared = json.loads(args.receipt.resolve().read_text(encoding="utf-8"))
    if prepared.get("status") != "PREFLIGHT_PASS" or any(
        prepared.get(key) != initial[key] for key in
        ("schema", "label", "source_workdir", "workdir", "source_sha256", "snapshot_sha256", "command")
    ):
        raise ValueError("checked witness preflight receipt does not match worker")
    digest = prepared.get("probe_contract_sha256", "")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("checked witness preflight probe contract missing")
    return {
        "preflight_status": "PASS", "probe_contract_sha256": digest,
        "witness_sha256": prepared["witness_sha256"],
        "preflight_finished_at": prepared["preflight_finished_at"],
        "preflight_command": prepared["preflight_command"],
    }


def read_checked_completion(log: Path, offset: int, contract: str) -> dict:
    """Require the current callback's explicit proof, never an old log marker."""
    prefix = b"CHECKED_WITNESS_COMPLETE "
    records = []
    with log.open("rb") as stream:
        stream.seek(offset)
        for line in stream:
            if line.startswith(prefix):
                records.append(json.loads(line[len(prefix):]))
    if len(records) != 1 or records[0].get("probe_contract_sha256") != contract:
        raise ValueError("checked witness completion missing or mismatched")
    results = records[0]["probe_results"]
    if not isinstance(results, dict) or any(
            type(sample.get("calls")) is not int or sample["calls"] <= 0
            for sample in results.values()):
        raise ValueError("checked witness completion has invalid probe observations")
    return results


def require_launch_contract(args, source: Path):
    if args.witness is not None:
        if args.raw_command_reason is not None:
            raise SystemExit("--witness and --raw-command-reason are mutually exclusive")
        return
    if not args.command:
        raise SystemExit("command required after --")
    executable, *arguments = args.command
    if not Path(executable).name.startswith("python"):
        return
    skip_value = False
    for index, token in enumerate(arguments):
        if skip_value:
            skip_value = False
            continue
        if token in ("-W", "-X", "--check-hash-based-pycs"):
            skip_value = True
            continue
        if token == "-c":
            return
        if token == "-m":
            is_harness = (index + 1 < len(arguments)
                          and arguments[index + 1].startswith("scripts.bamf.profiling."))
            break
        if token.startswith("-"):
            continue
        path = (source / token).resolve()
        is_harness = path.suffix == ".py" and (
            not path.is_relative_to(source)
            or path.is_relative_to(source / "scripts/bamf/profiling"))
        break
    else:
        return
    if is_harness and not (args.raw_command_reason or "").strip():
        raise SystemExit("Python harness requires --witness PATH (shared prepare contract); "
                         "use --raw-command-reason only for non-witness or legacy commands")


def prepare_checked_launch(args, source: Path, snapshot: Path, identity: dict, schema: str):
    original = (source / args.witness).resolve()
    path = snapshot / original.relative_to(source) if original.is_relative_to(source) else original
    common = [sys.executable, "-B", "-m", "scripts.bamf.detached.checked_witness"]
    environment = child_environment(source, snapshot, identity["snapshot_sha256"], checked=True)
    started = _utc_now()
    log = args.log.resolve()
    log.parent.mkdir(parents=True, exist_ok=True)
    digest = None
    contract = None
    preflight = [*common, "preflight", str(path)]
    try:
        if not (snapshot / "scripts/bamf/detached_long_run.py").is_file():
            raise FileNotFoundError("snapshot worker entrypoint missing")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        suffix = [str(path), digest, *args.command]
        preflight = [*common, "preflight", *suffix]
        run = [*common, "run", *suffix]
        completed = subprocess.run(preflight, cwd=snapshot, env=environment,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=PREFLIGHT_TIMEOUT)
        output = completed.stdout
        matches = re.findall(rb"^CHECKED_WITNESS_PREFLIGHT_PASS ([a-f0-9]{64})$",
                             output, re.MULTILINE)
        passed = completed.returncode == 0 and len(matches) == 1
        if passed:
            contract = matches[0].decode("ascii")
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b"") + b"\nCHECKED_WITNESS_PREFLIGHT_TIMEOUT\n"
        passed = False
    except OSError as error:
        output = f"CHECKED_WITNESS_PREFLIGHT_ERROR {error}\n".encode()
        passed = False
    mutated = _tree_digest(snapshot) != identity["snapshot_sha256"]
    with log.open("ab") as stream:
        stream.write(output)
        stream.write(b"\n")
        if mutated:
            stream.write(b"CHECKED_WITNESS_PREFLIGHT_SOURCE_MUTATED\n")
    if not passed or mutated:
        failure = {
            "schema": schema, "status": "FAIL", "stage": "PREFLIGHT",
            "label": args.label, "source_workdir": str(source), "workdir": str(snapshot),
            **identity, "source_mutated": mutated, "started_at": started,
            "finished_at": _utc_now(), "returncode": 1, "log": str(log),
            "command": preflight, "witness_sha256": digest,
        }
        _write_json(args.receipt.resolve(), failure)
        if not mutated:
            # This is the newly created, exclusively owned snapshot, not the
            # original worktree. Its digest still matches the copied surface.
            _discard_snapshot(source, snapshot,
                              git_snapshot=_git_toplevel(snapshot) == snapshot)
            failure["snapshot_removed"] = not snapshot.exists()
        else:
            failure["snapshot_removed"] = False
        _write_json(args.receipt.resolve(), failure)
        raise SystemExit(f"checked witness preflight failed; see {log}")
    _write_json(args.receipt.resolve(), {
        "schema": schema, "status": "PREFLIGHT_PASS", "stage": "PREFLIGHT",
        "label": args.label, "source_workdir": str(source), "workdir": str(snapshot),
        **identity, "started_at": started, "preflight_finished_at": _utc_now(),
        "log": str(log), "command": run, "preflight_command": preflight,
        "witness_sha256": digest, "probe_contract_sha256": contract,
    })
    return run
