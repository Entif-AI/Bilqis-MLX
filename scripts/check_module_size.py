"""Enforce the ratified anti-monolith encounter contract on observable code paths.

Changed/staged code is mechanically treated as encountered. Explicit paths let an
agent check a file or directory immediately when it reads it. Untouched legacy
debt is not recursively swept by this checker.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess

try:
    from quality.change_scope import effective_base
except ModuleNotFoundError:  # dynamic test import from repository root
    from scripts.quality.change_scope import effective_base

ROOT = Path(__file__).resolve().parents[1]
FILE_TRIGGER = 360
FILE_TARGET = 240
DIRECTORY_TRIGGER = 18
DIRECTORY_TARGET = 12
CODE_SUFFIXES = frozenset({".py", ".sh", ".js", ".mjs", ".cjs", ".ts", ".tsx"})
EXTERNAL_ROOTS = frozenset({"vendor", ".venv", "node_modules"})


@dataclass(frozen=True)
class Change:
    old: str | None
    new: str | None


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=check)


def is_code(path: str | Path) -> bool:
    value = Path(path)
    return value.suffix.lower() in CODE_SUFFIXES and not EXTERNAL_ROOTS.intersection(value.parts)


def line_count_bytes(data: bytes | None) -> int | None:
    if data is None:
        return None
    text = data.decode("utf-8")
    return len(text.splitlines())


def current_bytes(path: str, *, staged: bool = False) -> bytes | None:
    if staged:
        result = subprocess.run(["git", "show", f":{path}"], cwd=ROOT, capture_output=True)
        return result.stdout if result.returncode == 0 else None
    candidate = ROOT / path
    return candidate.read_bytes() if candidate.is_file() else None


def ref_bytes(ref: str, path: str) -> bytes | None:
    result = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True)
    return result.stdout if result.returncode == 0 else None


def _parse_name_status(text: str) -> list[Change]:
    changes = []
    for line in text.splitlines():
        fields = line.split("\t")
        status = fields[0]
        if status.startswith(("R", "C")) and len(fields) >= 3:
            changes.append(Change(fields[1], fields[2]))
        elif len(fields) >= 2:
            path = fields[1]
            changes.append(Change(path if not status.startswith("A") else None,
                                  path if not status.startswith("D") else None))
    return changes


def changed_paths(*, staged: bool = False, base_ref: str | None = None) -> list[Change]:
    if staged:
        result = _git("diff", "--cached", "--name-status", "-M", "--diff-filter=ACMRD")
    else:
        if not base_ref:
            raise ValueError("BASE_REF_REQUIRED")
        comparison_base = effective_base(ROOT, base_ref)
        result = _git("diff", "--name-status", "-M", "--diff-filter=ACMRD", comparison_base, "HEAD")
    return _parse_name_status(result.stdout)


def direct_code_count(directory: str, *, ref: str | None = None, staged: bool = False) -> int | None:
    directory = directory.strip("./")
    if staged:
        result = _git("ls-files", "--cached", "--", directory, check=False)
        prefix = directory + "/" if directory else ""
        return sum(
            name.startswith(prefix) and "/" not in name[len(prefix):] and is_code(name)
            for name in result.stdout.splitlines()
        )
    if ref is None:
        root = ROOT / directory
        if not root.is_dir():
            return None
        return sum(path.is_file() and is_code(path.relative_to(ROOT)) for path in root.iterdir())
    prefix = directory + "/" if directory else ""
    result = _git("ls-tree", "-r", "--name-only", ref, "--", directory, check=False)
    if result.returncode != 0:
        return None
    direct = []
    for name in result.stdout.splitlines():
        if not name.startswith(prefix):
            continue
        remainder = name[len(prefix):]
        if "/" not in remainder and is_code(name):
            direct.append(name)
    return len(direct)


def _file_violation(change: Change, *, base_ref: str, staged: bool) -> str | None:
    new = change.new
    old = change.old
    before = line_count_bytes(ref_bytes(base_ref, old)) if old and is_code(old) else None
    after = line_count_bytes(current_bytes(new, staged=staged)) if new and is_code(new) else None
    triggered = (before is not None and before > FILE_TRIGGER) or (after is not None and after > FILE_TRIGGER)
    if triggered and after is not None and after >= FILE_TARGET:
        return f"FILE_REFACTOR_REQUIRED {new} before={before} current={after} target=<{FILE_TARGET}"
    return None


def violations(changes: list[Change], *, base_ref: str, staged: bool = False) -> list[str]:
    problems = []
    directories: set[tuple[str, str]] = set()
    for change in changes:
        file_problem = _file_violation(change, base_ref=base_ref, staged=staged)
        if file_problem:
            problems.append(file_problem)
        for path in (change.old, change.new):
            if path and is_code(path):
                directories.add((str(Path(path).parent), path))
    for directory, witness in sorted(directories):
        before = direct_code_count(directory, ref=base_ref)
        after = direct_code_count(directory, staged=staged)
        # A directory absent at the base is a newly created compartment and is
        # deliberately not recursively swept during the same interruption.
        existed_before = before is not None and before > 0
        triggered = existed_before and ((before or 0) >= DIRECTORY_TRIGGER or (after or 0) >= DIRECTORY_TRIGGER)
        if triggered and after is not None and after > DIRECTORY_TARGET:
            problems.append(
                f"DIRECTORY_REFACTOR_REQUIRED {directory} witness={witness} "
                f"before={before} current={after} target<={DIRECTORY_TARGET}"
            )
    return problems


def explicit_violations(paths: list[str]) -> list[str]:
    problems = []
    for raw in paths:
        path = (ROOT / raw).resolve()
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            problems.append(f"PATH_OUTSIDE_REPOSITORY {raw}")
            continue
        if path.is_file() and is_code(rel):
            lines = len(path.read_text(encoding="utf-8").splitlines())
            if lines > FILE_TRIGGER:
                problems.append(f"FILE_REFACTOR_REQUIRED {rel.as_posix()} current={lines} target=<{FILE_TARGET}")
        elif path.is_dir():
            count = direct_code_count(rel.as_posix())
            if count is not None and count >= DIRECTORY_TRIGGER:
                problems.append(f"DIRECTORY_REFACTOR_REQUIRED {rel.as_posix()} current={count} target<={DIRECTORY_TARGET}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--changed-from")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    if args.paths:
        problems = explicit_violations(args.paths)
    else:
        base_ref = "HEAD" if args.staged else effective_base(ROOT, args.changed_from or "HEAD")
        changes = changed_paths(staged=args.staged, base_ref=None if args.staged else base_ref)
        problems = violations(changes, base_ref=base_ref, staged=args.staged)
    for problem in problems:
        print(problem)
    print(f"DEVELOPMENT_STRUCTURE_CHECK {'FAILED' if problems else 'OK'} violations={len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
