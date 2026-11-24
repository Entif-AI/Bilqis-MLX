"""Restore only evidence published by a successful main quality workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .verification_frontier import hosted_runner, trusted_producer
from .verification_ledger import full_requested

WORKFLOW = ".github/workflows/quality.yml"


def trusted_run(run: dict, repository: str) -> bool:
    return (isinstance(run, dict) and isinstance(run.get("head_repository"), dict)
            and run.get("path") == WORKFLOW and run.get("head_branch") == "main"
            and run.get("event") in ("push", "schedule")
            and run.get("status") == "completed" and run.get("conclusion") == "success"
            and (run.get("head_repository") or {}).get("full_name") == repository
            and isinstance(run.get("head_sha"), str)
            and re.fullmatch(r"[0-9a-f]{40}", run["head_sha"]) is not None
            and type(run.get("id")) is int and run["id"] > 0
            and type(run.get("run_attempt")) is int and run["run_attempt"] > 0
            and str(run["id"]) != os.environ.get("GITHUB_RUN_ID"))


def _runs(repository: str) -> list[dict]:
    result = subprocess.check_output([
        "gh", "api", "--method", "GET", f"repos/{repository}/actions/workflows/quality.yml/runs",
        "-f", "branch=main", "-f", "status=success", "-f", "per_page=8",
    ], timeout=12)
    return json.loads(result)["workflow_runs"]


def restore(destination: Path, scope: str) -> bool:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not hosted_runner() or full_requested() or destination.exists():
        return False
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        return False
    try:
        candidates = [run for run in _runs(repository) if trusted_run(run, repository)]
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            for run in candidates[:4]:
                name = f"verification-ledger-{scope}-{run['run_attempt']}"
                result = subprocess.run([
                    "gh", "run", "download", str(run["id"]), "--repo", repository,
                    "--name", name, "--dir", temporary,
                ], capture_output=True, timeout=15)
                candidate = Path(temporary) / "ledger.sqlite3"
                if result.returncode == 0 and candidate.is_file() and not candidate.is_symlink():
                    if 0 < candidate.stat().st_size <= 64 * 1024 * 1024:
                        candidate.replace(destination)
                        print(f"VERIFICATION_LEDGER_RESTORED scope={scope} "
                              f"main_run={run['id']} head={run['head_sha']}")
                        return True
                candidate.unlink(missing_ok=True)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        pass
    print(f"VERIFICATION_LEDGER_COLD scope={scope}")
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("core", "readiness"), required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    restored = restore(args.destination, args.scope)
    digest = ""
    if restored:
        try:
            digest = hashlib.sha256(args.destination.read_bytes()).hexdigest()
        except OSError:
            restored = False
    if restored:
        if args.output is not None and trusted_producer():
            try:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                # The fresh output is separate from the immutable read input.
                with args.destination.open("rb") as source, args.output.open("xb") as target:
                    shutil.copyfileobj(source, target)
            except OSError:
                print("VERIFICATION_LEDGER_SEED_UNAVAILABLE")
    if environment := os.environ.get("GITHUB_ENV"):
        with Path(environment).open("a", encoding="utf-8") as stream:
            stream.write("BILQIS_VERIFICATION_TRUSTED_LEDGER="
                         + (str(args.destination.resolve()) if restored else "") + "\n")
            stream.write(f"BILQIS_VERIFICATION_TRUSTED_SHA256={digest}\n")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"restored={str(restored).lower()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
