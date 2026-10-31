"""Source-derived error/status atlas and non-growing legacy-debt gate.

The atlas locates strings but does NOT invent their meaning. Only definitions
from the typed diagnostic registry carry authoritatively authored guidance.
An immutable baseline fences the pre-existing literal-error/magic-guard debt:
new opaque source constructs fail CI until expressed as domain contracts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import subprocess

try:
    from .operator_contract_scan import (
        CodeSite, ContractDebt, SourceReport, analyze_source,
        logical_source_path,
    )
except ImportError:  # direct script execution
    from operator_contract_scan import (
        CodeSite, ContractDebt, SourceReport, analyze_source,
        logical_source_path,
    )


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "bilqis.operator-contract-debt/v1"
def _repository_python_files(root: Path) -> tuple[Path, ...]:
    """Scan repository state, not another worker's untracked scratch files."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached"],
            check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return tuple(sorted((root / "bilqis_mlx").rglob("*.py")))
    files = []
    for relative in result.stdout.splitlines():
        path = Path(relative)
        candidate = root / path
        if (path.suffix == ".py" and path.parts and path.parts[0] == "bilqis_mlx"
                and not candidate.is_symlink()):
            files.append(candidate)
    return tuple(sorted(files))


def scan_tree(root: Path) -> SourceReport:
    sites: list[CodeSite] = []
    debt: list[ContractDebt] = []
    for file in _repository_python_files(root):
        if ("tests" in file.relative_to(root).parts or
                file.name.startswith("test_")):
            continue
        report = analyze_source(logical_source_path(file, root), file.read_text())
        sites.extend(report.codes)
        debt.extend(report.debt)
    return SourceReport(tuple(sites), tuple(debt))


def scan_git_tree(root: Path, ref: str) -> SourceReport:
    """Scan one committed tree using today's canonical owner mapping.

    PR gates compare the candidate tree with the exact base SHA. Reading the
    base through Git avoids mutating the worktree and, importantly, preserves
    the same logical-module normalization on both sides of a physical move.
    """
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", ref],
        check=True, capture_output=True, text=True,
    )
    sites: list[CodeSite] = []
    debt: list[ContractDebt] = []
    for row in listed.stdout.splitlines():
        metadata, raw_relative = row.split("\t", 1)
        mode = metadata.split(" ", 1)[0]
        relative = Path(raw_relative)
        if (relative.suffix != ".py" or not relative.parts
                or relative.parts[0] != "bilqis_mlx"
                or mode == "120000"
                or "tests" in relative.parts
                or relative.name.startswith("test_")):
            continue
        shown = subprocess.run(
            ["git", "-C", str(root), "show", f"{ref}:{relative.as_posix()}"],
            check=True, capture_output=True, text=True,
        )
        report = analyze_source(
            logical_source_path(root / relative, root), shown.stdout)
        sites.extend(report.codes)
        debt.extend(report.debt)
    return SourceReport(tuple(sites), tuple(debt))


def debt_counter(debt: tuple[ContractDebt, ...]) -> Counter[tuple[str, ...]]:
    """Track opaque contracts without making safe function extraction illegal.

    Moving an existing literal into a smaller pure function is not new debt.
    Adding another occurrence of that literal, adding a new literal, or moving
    the same opaque contract into a new module still increases the counter.
    """
    return Counter((item.path, item.kind, item.token) for item in debt)


def new_debt(
    current: Counter[tuple[str, ...]], baseline: Counter[tuple[str, ...]],
) -> tuple[tuple[str, ...], ...]:
    """Return net-new debt while allowing one-for-one module relocation.

    Exact path-qualified matches consume first. A current excess occurrence may
    then consume only a disappeared occurrence of the same ``(kind, token)``.
    Copies and genuinely new opaque contracts therefore remain debt while a
    structural move keeps its existing debt identity.
    """
    exact_excess = current - baseline
    disappeared = baseline - current
    relocation_credit: Counter[tuple[str, str]] = Counter()
    for (_, kind, token), count in disappeared.items():
        relocation_credit[(kind, token)] += count

    introduced: list[tuple[str, ...]] = []
    for key, count in sorted(exact_excess.items()):
        _, kind, token = key
        credit_key = (kind, token)
        relocated = min(count, relocation_credit[credit_key])
        relocation_credit[credit_key] -= relocated
        introduced.extend([key] * (count - relocated))
    return tuple(introduced)


def _baseline(counter: Counter[tuple[str, ...]]) -> dict:
    return {
        "schema": SCHEMA,
        "description": "Existing debt only; NOT an endorsement of magic numbers or string errors.",
        "counts": [list(key) + [count] for key, count in sorted(counter.items())],
    }


def _read_baseline(path: Path) -> Counter[tuple[str, ...]]:
    data = json.loads(path.read_text())
    if data.get("schema") != SCHEMA:
        raise ValueError("INVALID_OPERATOR_CONTRACT_BASELINE_SCHEMA")
    return Counter({tuple(row[:-1]): row[-1] for row in data["counts"]})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT,
                        help="Root of the checkout/worktree to inspect; defaults to this checkout")
    parser.add_argument("--lookup", metavar="CODE_FRAGMENT",
                        help="Find source occurrences, including unregistered status/gate codes")
    parser.add_argument("--json", action="store_true", help="Output machine-readable atlas data")
    parser.add_argument("--check-baseline", type=Path,
                        help="Exit nonzero if any new raw error identity or opaque policy number appears")
    parser.add_argument("--write-baseline", type=Path,
                        help="Explicit bootstrap only; never refresh baseline to silence new errors")
    args = parser.parse_args(argv)
    report = scan_tree(args.source_root.resolve())
    if args.write_baseline:
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(
            json.dumps(_baseline(debt_counter(report.debt)), indent=2) + "\n"
        )
    introduced = ()
    if args.check_baseline:
        introduced = new_debt(
            debt_counter(report.debt), _read_baseline(args.check_baseline))
    matches = [item for item in report.codes
               if not args.lookup or args.lookup.upper() in item.code]
    if args.json:
        print(json.dumps({
            "source_files": len({item.path for item in report.codes}),
            "code_occurrences": len(report.codes),
            "distinct_codes": len({item.code for item in report.codes}),
            "results": [asdict(item) for item in matches],
            "new_debt": [list(item) for item in introduced],
        }, indent=2))
    else:
        print(f"Source-derived atlas: {len({item.code for item in report.codes})} "
              f"distinct uppercase symbols; {len(report.debt)} old-style "
              "error/numeric-guard occurrences.")
        for site in matches[:80] if args.lookup else ():
            print(f"{site.code} [{site.kind}] {site.path}:{site.line} ({site.owner})")
        if args.lookup and len(matches) > 80:
            print(f"... {len(matches) - 80} more source matches; use --json.")
        if args.check_baseline:
            print(f"New opaque-contract debt: {len(introduced)}")
            for item in introduced[:30]:
                print("NEW", *item, sep=" | ")
    return 2 if introduced else 0


if __name__ == "__main__":
    raise SystemExit(main())
