#!/usr/bin/env python3
"""Fast inner-loop test gate with a separate pre-merge proof tier."""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

if __package__:
    from .dependency_map import affected_test_map
else:
    from dependency_map import affected_test_map


RECEIPT_DIR = Path(".local/test-gate")
TESTMON_DATA = Path(".testmondata")
IGNORED_PARTS = frozenset({".git", ".local", ".venv", "node_modules", "runs", "vendor"})
LEAF_GATE_POLICY_NAME = "BILQIS_LEAF_GATE_POLICY"
DETACHED_ONLY_POLICY = "DETACHED_ONLY"


@dataclass(frozen=True)
class Receipt:
    gate: str
    fingerprint: str
    head: str
    base_ref: str
    command: list[str]
    passed: bool


@dataclass(frozen=True)
class LeafPlan:
    mode: str
    base_ref: str
    changed: tuple[str, ...]
    tests: tuple[str, ...]


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=check)
    return result.stdout.strip()


def _valid_ref(root: Path, ref: str) -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref], cwd=root,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def read_receipt(root: Path, gate: str) -> Receipt | None:
    path = root / RECEIPT_DIR / f"{gate}.json"
    if not path.exists():
        return None
    try:
        return Receipt(**json.loads(path.read_text()))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def write_receipt(root: Path, receipt: Receipt) -> None:
    directory = root / RECEIPT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{receipt.gate}.json").write_text(
        json.dumps(asdict(receipt), sort_keys=True, indent=2) + "\n")


def workspace_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    digest.update(git(root, "rev-parse", "HEAD").encode())
    digest.update(sys.version.encode())
    for module in ("pytest", "testmon", "xdist"):
        spec = importlib.util.find_spec(module)
        if spec is not None:
            try:
                loaded = __import__(module)
                digest.update(f"{module}:{getattr(loaded, '__version__', 'present')}".encode())
            except Exception:
                digest.update(f"{module}:present".encode())
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"], cwd=root, capture_output=True, check=True)
    digest.update(diff.stdout)
    untracked = git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    for relative in sorted(path for path in untracked if not path.startswith(".local/")):
        path = root / relative
        digest.update(relative.encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def receipt_reusable(root: Path, receipt: Receipt | None) -> bool:
    return bool(receipt and receipt.passed and receipt.fingerprint == workspace_fingerprint(root))


def resolve_test_base(
    root: Path, *, environ: dict[str, str] | None = None, gate: str = "leaf"
) -> str:
    env = os.environ if environ is None else environ
    explicit = env.get("BILQIS_TEST_BASE_REF")
    if explicit:
        return explicit
    previous = read_receipt(root, gate)
    if previous and previous.passed and _valid_ref(root, previous.head):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", previous.head, "HEAD"], cwd=root
        ).returncode == 0:
            return previous.head
    return "HEAD"


def _changed_paths(root: Path, base_ref: str) -> tuple[str, ...]:
    names = set()
    if _valid_ref(root, base_ref):
        names.update(git(root, "diff", "--name-only", f"{base_ref}...HEAD").splitlines())
    names.update(git(root, "diff", "--name-only", "HEAD").splitlines())
    names.update(git(root, "ls-files", "--others", "--exclude-standard").splitlines())
    return tuple(sorted(name for name in names if name and not name.startswith(".local/")))


def _test_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(
        path for path in root.rglob("test_*.py")
        if "tests" in path.relative_to(root).parts
        and not IGNORED_PARTS.intersection(path.relative_to(root).parts)
    ))


def _nearest_test_scope(root: Path, relative: Path) -> tuple[Path, ...]:
    parent = (root / relative).parent
    while parent != root and root in parent.parents:
        test_dir = parent / "tests"
        if test_dir.is_dir():
            return tuple(sorted(test_dir.rglob("test_*.py")))
        parent = parent.parent
    return ()


def _leaf_schedulable(test: Path) -> bool:
    """Return False for tests that must run only as explicit detached witnesses."""
    try:
        tree = ast.parse(test.read_text(errors="ignore"))
    except (OSError, SyntaxError):
        return True
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        if any(isinstance(target, ast.Name) and target.id == LEAF_GATE_POLICY_NAME
               for target in targets):
            return value.value != DETACHED_ONLY_POLICY
    return True


def _candidate_tests(root: Path, changed: tuple[str, ...]) -> tuple[str, ...]:
    selected: set[Path] = set()
    python_changes = [Path(name) for name in changed if name.endswith(".py")]
    dependency_tests = affected_test_map(root, tuple(python_changes))
    for relative in python_changes:
        absolute = root / relative
        if "tests" in relative.parts and relative.name.startswith("test_"):
            selected.add(absolute)
            continue
        mapped = dependency_tests.get(relative, ())
        if mapped:
            selected.update(mapped)
            continue
        module = ".".join(relative.with_suffix("").parts)
        stem = relative.stem
        scope = _nearest_test_scope(root, relative)
        matches: set[Path] = set()
        for test in scope:
            text = test.read_text(errors="ignore")
            if module in text or stem in text:
                matches.add(test)
        if not matches:
            matches.update(scope)
        selected.update(matches)
    return tuple(
        str(path.relative_to(root))
        for path in sorted(selected)
        if _leaf_schedulable(path)
    )


def plan_leaf(root: Path, *, base_ref: str | None = None) -> LeafPlan:
    base = base_ref or resolve_test_base(root)
    changed = _changed_paths(root, base)
    if not any(name.endswith(".py") for name in changed):
        return LeafPlan("skip", base, changed, ())
    tests = _candidate_tests(root, changed)
    mode = "testmon-targeted" if (root / TESTMON_DATA).exists() else "cold-targeted"
    return LeafPlan(mode, base, changed, tests)


def _pytest_available() -> bool:
    return importlib.util.find_spec("pytest") is not None


def _plugin_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _pytest_command(mode: str, tests: tuple[str, ...] = ()) -> list[str]:
    workers = os.environ.get("BILQIS_TEST_WORKERS", "4")
    command = [sys.executable, "-m", "pytest", "-q", "--import-mode=importlib"]
    if _plugin_available("xdist"):
        command += ["-n", workers, "--dist=loadscope"]
    if _plugin_available("testmon"):
        command += [
            "--testmon-forceselect" if mode == "testmon-targeted" else "--testmon-noselect"
        ]
    command.extend(tests)
    return command


def _run(root: Path, gate_name: str, base_ref: str, command: list[str]) -> int:
    print(f"TEST_GATE_RUN gate={gate_name} base={base_ref} command={' '.join(command)}")
    result = subprocess.run(command, cwd=root, check=False)
    if result.returncode == 0:
        write_receipt(root, Receipt(
            gate=gate_name,
            fingerprint=workspace_fingerprint(root),
            head=git(root, "rev-parse", "HEAD"),
            base_ref=base_ref,
            command=command,
            passed=True,
        ))
    return result.returncode


def run_leaf(root: Path) -> int:
    previous = read_receipt(root, "leaf")
    if os.environ.get("BILQIS_TEST_FORCE") != "1" and receipt_reusable(root, previous):
        print(f"TEST_GATE_REUSED gate=leaf head={previous.head}")
        return 0
    plan = plan_leaf(root)
    print(f"TEST_GATE_PLAN mode={plan.mode} base={plan.base_ref} changed={len(plan.changed)}")
    if plan.mode == "skip":
        command = ["skip", "non-python-change"]
        write_receipt(root, Receipt(
            "leaf", workspace_fingerprint(root), git(root, "rev-parse", "HEAD"),
            plan.base_ref, command, True))
        return 0
    if not _pytest_available():
        command = [sys.executable, "-B", "scripts/run_tests.py", *plan.tests]
    elif plan.tests:
        command = _pytest_command(plan.mode, plan.tests)
    else:
        print("TEST_GATE_UNMAPPED_PYTHON_CHANGE no bounded owner tests found")
        return 2
    return _run(root, "leaf", plan.base_ref, command)


def run_premerge(root: Path) -> int:
    previous = read_receipt(root, "premerge")
    if os.environ.get("BILQIS_TEST_FORCE") != "1" and receipt_reusable(root, previous):
        print(f"TEST_GATE_REUSED gate=premerge head={previous.head}")
        return 0
    base = resolve_test_base(root, gate="premerge")
    command = [sys.executable, "-B", "scripts/run_tests.py"]
    return _run(root, "premerge", base, command)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate", choices=("leaf", "premerge", "status"))
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    if args.gate == "leaf":
        return run_leaf(root)
    if args.gate == "premerge":
        return run_premerge(root)
    for name in ("leaf", "premerge"):
        receipt = read_receipt(root, name)
        state = "reusable" if receipt_reusable(root, receipt) else "stale-or-missing"
        print(f"TEST_GATE_STATUS gate={name} state={state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
