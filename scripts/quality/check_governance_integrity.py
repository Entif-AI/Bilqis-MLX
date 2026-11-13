"""Protect ratified structure thresholds and forbid ordinary baseline laundering."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
STRUCTURE_CHECK = "scripts/check_module_size.py"
CHANGE_SCOPE = "scripts/quality/change_scope.py"
SMELL_BASELINE = "docs/evidence/development/code_smell_baseline.json"
SIZE_BASELINE = "docs/evidence/development/module_size_baseline.json"
EXPECTED_ADOPTION_COMMIT = "f3c33e2ef06650a04914d2660ca9cc5e14f0f08b"
EXPECTED = (
    ("FILE_TRIGGER", 360),
    ("FILE_TARGET", 240),
    ("DIRECTORY_TRIGGER", 18),
    ("DIRECTORY_TARGET", 12),
)


def git_bytes(spec: str) -> bytes | None:
    result = subprocess.run(["git", "show", spec], cwd=ROOT, capture_output=True)
    return result.stdout if result.returncode == 0 else None


def current_bytes(path: str, *, staged: bool) -> bytes | None:
    if staged:
        return git_bytes(f":{path}")
    target = ROOT / path
    return target.read_bytes() if target.is_file() else None


def base_bytes(ref: str, path: str) -> bytes | None:
    return git_bytes(f"{ref}:{path}")


def _json(data: bytes | None) -> dict | None:
    return json.loads(data.decode("utf-8")) if data is not None else None


def _thresholds(source: bytes | None) -> dict[str, int]:
    text = source.decode("utf-8") if source else ""
    found = {}
    for name, _ in EXPECTED:
        match = re.search(rf"(?m)^{name}\s*=\s*(\d+)\s*$", text)
        if match:
            found[name] = int(match.group(1))
    return found


def threshold_problems(*, staged: bool) -> list[str]:
    source = current_bytes(STRUCTURE_CHECK, staged=staged)
    actual = _thresholds(source)
    problems = []
    for name, expected in EXPECTED:
        if actual.get(name) != expected:
            problems.append(f"STRUCTURE_THRESHOLD_DRIFT {name} expected={expected} actual={actual.get(name)}")
    readme = (current_bytes("README.md", staged=staged) or b"").decode("utf-8")
    agents = (current_bytes("AGENTS.md", staged=staged) or b"").decode("utf-8")
    required = (">360", "<240", ">=18", "<=12")
    for path, text in (("README.md", readme), ("AGENTS.md", agents)):
        missing = [token for token in required if token not in text]
        if not re.search(r"@Entif\s+Work\s+Stack", text):
            missing.append("@Entif Work Stack")
        if missing:
            problems.append(f"STRUCTURE_GOVERNANCE_TEXT_DRIFT {path} missing={','.join(missing)}")
    scope = (current_bytes(CHANGE_SCOPE, staged=staged) or b"").decode("utf-8")
    match = re.search(r'(?m)^GOVERNANCE_ADOPTION_COMMIT\s*=\s*"([0-9a-f]{40})"\s*$', scope)
    actual_adoption = match.group(1) if match else None
    if actual_adoption != EXPECTED_ADOPTION_COMMIT:
        problems.append(
            "STRUCTURE_ADOPTION_SCOPE_DRIFT "
            f"expected={EXPECTED_ADOPTION_COMMIT} actual={actual_adoption}"
        )
    return problems


def smell_baseline_problems(base: dict | None, current: dict | None) -> list[str]:
    if base is None or current is None:
        return [] if base is None and current is not None else ["CODE_SMELL_BASELINE_MISSING"]
    if current.get("schema") != "bilqis.code-smell-baseline/v1":
        return ["CODE_SMELL_BASELINE_SCHEMA_INVALID"]
    before = Counter((item[1], item[2]) for item in base.get("fingerprints", []))
    after = Counter((item[1], item[2]) for item in current.get("fingerprints", []))
    added = after - before
    return [f"CODE_SMELL_BASELINE_EXPANSION {rule} {context} added={count}"
            for (rule, context), count in sorted(added.items())]


def size_baseline_problems(base: dict | None, current: dict | None) -> list[str]:
    if base is None or current is None:
        return [] if base is None and current is not None else ["MODULE_SIZE_BASELINE_MISSING"]
    if current.get("schema") != "bilqis.production-size-baseline/v1":
        return ["MODULE_SIZE_BASELINE_SCHEMA_INVALID"]
    old = base.get("sizes", {})
    new = current.get("sizes", {})
    problems = []
    for key, size in sorted(new.items()):
        if key not in old:
            problems.append(f"MODULE_SIZE_BASELINE_EXPANSION {key} added={size}")
        elif size > old[key]:
            problems.append(f"MODULE_SIZE_BASELINE_EXPANSION {key} before={old[key]} current={size}")
    return problems


def baseline_problems(base_ref: str, *, staged: bool) -> list[str]:
    problems = []
    for path, compare in ((SMELL_BASELINE, smell_baseline_problems),
                          (SIZE_BASELINE, size_baseline_problems)):
        base = _json(base_bytes(base_ref, path))
        current = _json(current_bytes(path, staged=staged))
        problems.extend(compare(base, current))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--base-ref", default="HEAD")
    args = parser.parse_args(argv)
    base_ref = "HEAD" if args.staged else subprocess.check_output(
        ["git", "merge-base", args.base_ref, "HEAD"], cwd=ROOT, text=True
    ).strip()
    problems = threshold_problems(staged=args.staged)
    problems.extend(baseline_problems(base_ref, staged=args.staged))
    for problem in problems:
        print(problem)
    print(f"GOVERNANCE_INTEGRITY_CHECK {'FAILED' if problems else 'OK'} violations={len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
