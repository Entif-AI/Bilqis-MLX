"""Git-native input identities for reusable CI command results."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from .verification_ledger import fingerprint
from .verification_environment import installed_identity
from .verification_projection import validate_projection


def _git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "--no-replace-objects", *args], cwd=root)


def frontier_digest(root: Path, check: str) -> str:
    # Broad commands use the complete committed tree until a narrower input
    # boundary has been independently qualified.
    return fingerprint(check, _git(root, "rev-parse", "HEAD^{tree}").decode().strip())


def hosted_runner() -> bool:
    return (os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted")


def trusted_producer() -> bool:
    return (hosted_runner() and os.environ.get("GITHUB_REF") == "refs/heads/main"
            and os.environ.get("GITHUB_EVENT_NAME") in ("push", "schedule"))


def clean_tracked_tree(root: Path, *, command: list[str]) -> bool:
    if subprocess.run(["git", "--no-replace-objects", "diff", "--quiet", "HEAD", "--"],
                      cwd=root).returncode:
        return False
    # A sparse or assume-unchanged index is not a clean source checkout.
    index = _git(root, "ls-files", "-v", "-z")
    if any(not entry.startswith(b"H ") for entry in index.split(b"\0") if entry):
        return False
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "--directory", "-z")
    if any(not os.fsdecode(path).startswith("bilqis_mlx_private.egg-info/")
           for path in untracked.split(b"\0") if path):
        return False
    ignored = _git(root, "ls-files", "--others", "--ignored", "--exclude-standard",
                   "--directory", "-z")
    return not any(path for path in ignored.split(b"\0"))


def _configuration() -> dict[str, str]:
    # Runner correlation/temporary file identities do not alter these commands.
    # Bind all other environment, including npm, shell, loader and import config.
    volatile = {
        "PWD", "OLDPWD", "SHLVL", "_", "GITHUB_ACTION", "GITHUB_ACTION_PATH",
        "GITHUB_EVENT_PATH", "GITHUB_ENV", "GITHUB_OUTPUT", "GITHUB_PATH",
        "GITHUB_STEP_SUMMARY", "GITHUB_STATE", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
        "GITHUB_RUN_NUMBER", "GITHUB_REF", "GITHUB_REF_NAME", "GITHUB_REF_TYPE",
        "GITHUB_HEAD_REF", "GITHUB_BASE_REF", "GITHUB_SHA", "GITHUB_WORKFLOW_SHA",
        "GITHUB_EVENT_NAME", "GITHUB_WORKFLOW_REF", "GITHUB_REF_PROTECTED",
        "GITHUB_ACTOR", "GITHUB_ACTOR_ID", "GITHUB_TRIGGERING_ACTOR",
        "RUNNER_TEMP", "RUNNER_TRACKING_ID", "RUNNER_NAME", "RUNNER_PERFLOG",
        "ACTIONS_RUNTIME_TOKEN", "ACTIONS_RUNTIME_URL", "ACTIONS_RESULTS_URL",
        "ACTIONS_CACHE_URL", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL",
        "BILQIS_VERIFICATION_LEDGER", "BILQIS_VERIFICATION_FULL",
        "BILQIS_VERIFICATION_TRUSTED_LEDGER", "BILQIS_VERIFICATION_TRUSTED_SHA256",
        "BILQIS_VERIFICATION_TRUSTED_DESTINATION",
    }
    return {key: value for key, value in os.environ.items() if key not in volatile}


def _editable_metadata(root: Path) -> tuple[tuple[str, str], ...]:
    directory = root / "bilqis_mlx_private.egg-info"
    if not directory.exists():
        return ()
    return tuple(
        (str(path.relative_to(root)), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(directory.rglob("*")) if path.is_file()
    )


def execution_identity(root: Path, check: str, command: list[str], *,
                       execution_root: Path | None = None, projected_digest: str | None = None
                       ) -> tuple[str, str] | None:
    source = execution_root or root
    frontier = frontier_digest(root, check) if source == root else (
        projected_digest or validate_projection(root, source))
    if frontier is None:
        return None
    if not hosted_runner() or not os.environ.get("ImageVersion") or not os.environ.get("ImageOS"):
        return None
    if not clean_tracked_tree(root, command=command):
        return None
    if command[0] == "npm" or os.environ.get("PYTHONPATH") or os.environ.get("PYTHONHOME"):
        return None
    executable = shutil.which(command[0])
    git = shutil.which("git")
    if executable is None or git is None:
        return None
    packages = installed_identity((Path(executable), Path(sys.executable), Path(git)))
    if packages is None:
        return None
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    if os.environ.get("GITHUB_SHA") != head:
        return None
    environment = fingerprint(
        sys.implementation.name, sys.version, platform.platform(), platform.machine(),
        os.environ["ImageOS"], os.environ["ImageVersion"],
        os.environ.get("RUNNER_OS"), os.environ.get("RUNNER_ARCH"),
        packages, _configuration(), _editable_metadata(source),
    )
    return head, fingerprint("ci-command/v2", check, command, frontier, environment)
