"""Fail-closed local execution of the repository's pull-request CI predicates."""
from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

CORE_BEFORE_BRANCH = (
    "release", "structure", "flow-control", "invariant-transfer",
    "detached-witness", "historical-abi",
)
BRANCH_GROUPS = ("legacy-semantic", "bamf-contracts")
CORE_AFTER_BRANCH = ("architecture", "frontend", "code-smell", "portable-custody")
ABI_GROUPS = ("abi-scope", "abi-contract", "abi-tests")
SEMANTIC_GROUPS = ("semantic-plan", "semantic-diff", "semantic-shard")
NATIVE_GROUPS = ("native-witness", "readiness")
CI_GROUPS = frozenset(
    CORE_BEFORE_BRANCH + BRANCH_GROUPS + CORE_AFTER_BRANCH + ABI_GROUPS
    + SEMANTIC_GROUPS + NATIVE_GROUPS + ("commit-subjects",)
)
WALL_CLOCK_SECONDS = 7200


class PrePushError(RuntimeError):
    """A candidate cannot be certified for push."""


def git(root: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, env=env, text=True,
    ).strip()


def source_updates(lines: list[str]) -> tuple[str, ...]:
    """Git sends local ref, local OID, remote ref, remote OID on stdin."""
    updates = []
    for line in lines:
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4:
            raise PrePushError("Invalid pre-push ref record")
        local_ref, local_oid, remote_ref, _ = fields
        if local_ref == "(delete)" and set(local_oid) == {"0"}:
            continue
        if not remote_ref.startswith(("refs/heads/", "refs/tags/")):
            raise PrePushError(f"Unsupported push destination: {remote_ref}")
        updates.append(local_oid)
    return tuple(dict.fromkeys(updates))


def require_clean(root: Path, env: dict[str, str], head: str) -> None:
    if git(root, env, "rev-parse", "HEAD") != head:
        raise PrePushError("HEAD changed during verification")
    if git(root, env, "status", "--porcelain", "--untracked-files=normal"):
        raise PrePushError("Commit or remove uncommitted source before pushing")
    index = git(root, env, "ls-files", "-v").splitlines()
    if any(not entry.startswith("H ") for entry in index):
        raise PrePushError("Sparse/assume-unchanged index cannot certify a push")


def branch_context(root: Path, env: dict[str, str], remote_url: str,
                   head_ref: str) -> tuple[str, str]:
    base = env.get("BILQIS_CI_BASE_BRANCH", "")
    title = env.get("BILQIS_CI_PR_TITLE", "")
    if "github.com" in remote_url and shutil.which("gh"):
        try:
            result = subprocess.run(
                ["gh", "pr", "view", head_ref, "--json", "baseRefName,title,state"],
                cwd=root, env=dict(env, GH_PROMPT_DISABLED="1"),
                capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                pr = json.loads(result.stdout)
                if pr["state"] == "OPEN":
                    if base and base != pr["baseRefName"]:
                        raise PrePushError("Explicit base disagrees with open PR base")
                    return pr["baseRefName"], pr["title"]
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
            pass
    return base or "main", title


def branch_group(head_ref: str, base_ref: str) -> str:
    return "bamf-contracts" if "bamf" in head_ref or "bamf" in base_ref else "legacy-semantic"


def require_dependencies(root: Path, requirements: tuple[str, ...]) -> None:
    pins = []
    for requirement in requirements:
        if requirement.endswith(".txt"):
            for line in (root / requirement).read_text().splitlines():
                line = line.strip()
                if line.startswith("-r "):
                    nested = Path(requirement).parent / line[3:]
                    require_dependencies(root, (str(nested),))
                elif line and not line.startswith("#"):
                    pins.append(line)
        else:
            pins.append(requirement)
    for pin in pins:
        name, separator, expected = pin.partition("==")
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        if installed is None or (separator and installed != expected):
            raise PrePushError(
                f"CI dependency {pin} required; installed={installed}. "
                "Install in your verification environment before pushing.")


class LocalChecks:
    def __init__(self, root: Path, env: dict[str, str]):
        self.root = root
        self.env = env
        self.deadline = time.monotonic() + WALL_CLOCK_SECONDS

    def run(self, group: str, **extra: str) -> None:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise PrePushError("Pre-push verification exceeded its two-hour ceiling")
        print(f"PRE_PUSH_CI {group}", flush=True)
        command = ["bash", "scripts/quality/ci_checks.sh", group]
        with subprocess.Popen(command, cwd=self.root, env=dict(self.env, **extra),
                              start_new_session=True) as process:
            try:
                status = process.wait(timeout=remaining)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
        if status:
            raise subprocess.CalledProcessError(status, command)

    def outputs(self, group: str) -> dict[str, str]:
        with tempfile.TemporaryDirectory(prefix="bilqis-pre-push-") as directory:
            output = Path(directory) / "output"
            self.run(group, GITHUB_OUTPUT=str(output))
            return dict(line.split("=", 1) for line in output.read_text().splitlines())

    def dependencies(self, *requirements: str) -> None:
        require_dependencies(self.root, requirements)

    def verify(self) -> None:
        self.run("commit-subjects")
        self.dependencies("lib/ithkuil/requirements-semantic.txt", "numpy==2.4.4")
        for group in CORE_BEFORE_BRANCH:
            self.run(group)
        self.run(branch_group(self.env["HEAD_REF"], self.env["BASE_REF"]))
        for group in CORE_AFTER_BRANCH:
            self.run(group)
        self.run("local-governance")
        abi = self.outputs("abi-scope")["run"]
        if abi == "true":
            self.run("abi-contract")
            self.run("abi-tests")
        elif abi != "false":
            raise PrePushError(f"Unexpected semantic ABI scope: {abi}")
        action = self.outputs("semantic-plan")["action"]
        if action in ("DIFF", "FULL"):
            self.dependencies("lib/ithkuil/requirements-extraction.txt",
                              "lib/ithkuil/requirements-falkor.txt")
        if action == "DIFF":
            self.run("semantic-diff")
        elif action == "FULL":
            for shard in range(8):
                self.run("semantic-shard", SKOS_SHARD_INDEX=str(shard))
        elif action != "SKIP":
            raise PrePushError(f"Unexpected semantic profile plan: {action}")
        self.dependencies("mlx==0.31.1", "cryptography")
        for group in NATIVE_GROUPS:
            self.run(group)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        raise SystemExit("Usage: pre_push REMOTE_NAME REMOTE_URL")
    remote, remote_url = args
    root = Path.cwd().resolve()
    env = dict(os.environ)
    for key in git(root, env, "rev-parse", "--local-env-vars").splitlines():
        env.pop(key, None)
    env.update(GIT_NO_REPLACE_OBJECTS="1", GITHUB_ACTIONS="false",
               BILQIS_LOCAL_CI="1", BILQIS_TEST_WORKERS="1",
               PYTHONDONTWRITEBYTECODE="1")
    try:
        updates = source_updates(sys.stdin.readlines())
        if not updates:
            print("PRE_PUSH_NO_SOURCE_UPDATE")
            return 0
        head = git(root, env, "rev-parse", "HEAD")
        for oid in updates:
            if git(root, env, "rev-parse", "--verify", f"{oid}^{{commit}}") != head:
                raise PrePushError("Push only the checked-out, verified commit")
        require_clean(root, env, head)
        head_ref = git(root, env, "rev-parse", "--abbrev-ref", "HEAD")
        base_ref, title = branch_context(root, env, remote_url, head_ref)
        git(root, env, "check-ref-format", f"refs/heads/{base_ref}")
        git(root, env, "fetch", "--no-tags", "--no-recurse-submodules",
            remote, f"refs/heads/{base_ref}")
        base = git(root, env, "rev-parse", "FETCH_HEAD")
        if subprocess.run(["git", "merge-base", "--is-ancestor", base, head],
                          cwd=root, env=env, check=False).returncode:
            raise PrePushError(f"Merge the fetched {base_ref} ({base[:12]}) before pushing")
        env.update(BASE_REF=base_ref, BASE_SHA=base, HEAD_SHA=head, HEAD_REF=head_ref,
                   PR_TITLE=title, QUALITY_BASE_REF=base, SKOS_BASE_REF=base,
                   EVENT_NAME="pull_request")
        print(f"PRE_PUSH_CANDIDATE head={head} base={base}", flush=True)
        LocalChecks(root, env).verify()
        require_clean(root, env, head)
    except (PrePushError, subprocess.CalledProcessError, subprocess.TimeoutExpired,
            OSError, KeyError, ValueError) as error:
        print(f"PRE_PUSH_CI_FAILED {error}", file=sys.stderr, flush=True)
        return 1
    print(f"PRE_PUSH_CI_OK head={head}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
