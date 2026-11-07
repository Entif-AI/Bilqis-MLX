"""Validate the BAMF legacy-trainer adaptation source and stale-reference guard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = Path("docs/tasks/bamf-0.2/legacy-trainer-authority.json")
CANONICAL_BRANCH = "codex/337-replay-349-20261026"
CANONICAL_WORKTREE = "/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026"
CANONICAL_RUN = f"{CANONICAL_WORKTREE}/runs/microspenics-349-replay"
CANONICAL_STATE = f"{CANONICAL_RUN}/state.json"
STALE_PROMETHEUS_RUN = "runs/codex-0001-prometheus"
SCAN_ROOTS = (Path("docs/tasks/bamf-0.2"), Path("docs/evidence/bamf"))
SCAN_SUFFIXES = (".md", ".txt", ".json", ".jsonl")
POLICY_DOC = Path("docs/tasks/bamf-0.2/LEGACY_TRAINER_AUTHORITY.md")
LEGACY_TRAINER_RE = re.compile(r"(?i)\blegacy[- ]trainer\b|\blatest legacy (?:trainer|run)\b")
PROMETHEUS_CURRENT_RE = re.compile(
    r"(?i)(?:\bprometheus\b.{0,100}\b(?:trainer|training|baseline|resume|adapt(?:ation|ing)?)\b"
    r"|\b(?:trainer|training|baseline|resume|adapt(?:ation|ing)?)\b.{0,100}\bprometheus\b)"
)
HISTORICAL_QUALIFIER_RE = re.compile(
    r"(?i)\b(?:historical|history|non-authoritative|evidence only|not (?:the )?(?:current|latest)|not the prometheus|not .*adaptation source|(?:no|stale) prometheus)\b"
)


class LegacyTrainerAuthorityError(RuntimeError):
    pass


def _load_authority(root: Path) -> dict:
    path = root / AUTHORITY_PATH
    if not path.is_file():
        raise LegacyTrainerAuthorityError(f"LEGACY_TRAINER_AUTHORITY_MISSING {path}")
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise LegacyTrainerAuthorityError(f"LEGACY_TRAINER_AUTHORITY_INVALID {path}: {exc}") from exc
    return value


def _iter_scan_files(root: Path):
    for relative_root in SCAN_ROOTS:
        target = root / relative_root
        if not target.exists():
            continue
        for path in sorted(target.rglob("*")):
            if (
                path.is_file()
                and path.suffix in SCAN_SUFFIXES
                and path not in {root / AUTHORITY_PATH, root / POLICY_DOC}
            ):
                yield path


def validate_static(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    try:
        authority = _load_authority(root)
    except LegacyTrainerAuthorityError as exc:
        return [str(exc)]

    expected = {
        "schema": "bilqis.bamf.legacy-trainer-authority/v1",
        "version": "1.0.0",
        "effective_date": "2026-11-07",
        "source_branch": CANONICAL_BRANCH,
        "source_worktree": CANONICAL_WORKTREE,
        "source_run": CANONICAL_RUN,
        "source_state": CANONICAL_STATE,
        "operator_preflight": "python3 -B scripts/check_legacy_trainer_authority.py --live",
    }
    for key, expected_value in expected.items():
        if authority.get(key) != expected_value:
            problems.append(
                f"LEGACY_TRAINER_AUTHORITY_DRIFT {key} expected={expected_value!r} actual={authority.get(key)!r}"
            )

    historical = authority.get("historical_non_authoritative_runs", [])
    prometheus = [item for item in historical if item.get("run") == STALE_PROMETHEUS_RUN]
    if not prometheus or "never" not in prometheus[0].get("disposition", "").lower():
        problems.append("LEGACY_TRAINER_PROMETHEUS_BOUNDARY_MISSING")

    for governance_path in (Path("AGENTS.md"), Path("docs/tasks/bamf-0.2/README.md")):
        text = (root / governance_path).read_text() if (root / governance_path).is_file() else ""
        if CANONICAL_RUN not in text:
            problems.append(f"LEGACY_TRAINER_GOVERNANCE_SOURCE_MISSING {governance_path}")
        if governance_path.name == "AGENTS.md" and "BAMF02:LEGACY-TRAINER-AUTHORITY:20261107" not in text:
            problems.append("LEGACY_TRAINER_GOVERNANCE_MARKER_MISSING AGENTS.md")

    for path in _iter_scan_files(root):
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(root)
        if STALE_PROMETHEUS_RUN in text:
            problems.append(f"LEGACY_TRAINER_STALE_RUN_REFERENCE {relative}")
        if LEGACY_TRAINER_RE.search(text) and CANONICAL_RUN not in text:
            problems.append(f"LEGACY_TRAINER_SOURCE_OMITTED {relative}")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if PROMETHEUS_CURRENT_RE.search(line) and not HISTORICAL_QUALIFIER_RE.search(line):
                problems.append(f"LEGACY_TRAINER_PROMETHEUS_AMBIGUITY {relative}:{lineno}")
    return problems


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise LegacyTrainerAuthorityError(
            f"LEGACY_TRAINER_GIT_CHECK_FAILED cwd={cwd} command={' '.join(args)} stderr={result.stderr.strip()}"
        )
    return result.stdout.strip()


def validate_live(root: Path = ROOT) -> tuple[list[str], dict[str, str | int]]:
    problems = validate_static(root)
    authority = _load_authority(root)
    worktree = Path(authority["source_worktree"])
    run = Path(authority["source_run"])
    state = Path(authority["source_state"])
    observed: dict[str, str | int] = {}

    if not worktree.is_dir():
        problems.append(f"LEGACY_TRAINER_WORKTREE_MISSING {worktree}")
        return problems, observed
    try:
        branch = _git("branch", "--show-current", cwd=worktree)
        head = _git("rev-parse", "HEAD", cwd=worktree)
    except LegacyTrainerAuthorityError as exc:
        problems.append(str(exc))
        return problems, observed
    observed.update(branch=branch, head=head)
    if branch != authority["source_branch"]:
        problems.append(
            f"LEGACY_TRAINER_BRANCH_MISMATCH expected={authority['source_branch']} actual={branch}"
        )
    if not run.is_dir():
        problems.append(f"LEGACY_TRAINER_RUN_MISSING {run}")
    if not state.is_file():
        problems.append(f"LEGACY_TRAINER_STATE_MISSING {state}")
        return problems, observed
    try:
        state_value = json.loads(state.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"LEGACY_TRAINER_STATE_INVALID {state}: {exc}")
        return problems, observed
    observed["state_schema"] = state_value.get("schema", "")
    observed["generation"] = state_value.get("generation", -1)
    if state_value.get("schema") != "bilqis.state-head/v1":
        problems.append(
            f"LEGACY_TRAINER_STATE_SCHEMA_INVALID expected='bilqis.state-head/v1' actual={state_value.get('schema')!r}"
        )
    if not isinstance(state_value.get("generation"), int) or state_value["generation"] < 0:
        problems.append(f"LEGACY_TRAINER_GENERATION_INVALID actual={state_value.get('generation')!r}")
    return problems, observed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="also verify the preserved local worktree and run")
    args = parser.parse_args(argv)
    if args.live:
        problems, observed = validate_live()
    else:
        problems = validate_static()
        observed = {}
    for problem in problems:
        print(problem)
    if problems:
        print(f"LEGACY_TRAINER_AUTHORITY_FAIL mode={'live' if args.live else 'static'} violations={len(problems)}")
        return 1
    extra = ""
    if args.live:
        extra = (
            f" branch={observed['branch']} head={observed['head']}"
            f" generation={observed['generation']} state_schema={observed['state_schema']}"
        )
    print(f"LEGACY_TRAINER_AUTHORITY_OK mode={'live' if args.live else 'static'}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
