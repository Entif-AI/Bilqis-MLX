"""Source-derived error/status atlas and non-growing legacy-debt gate."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

from operations.operator_contract_paths import logical_source_path
from operations.operator_contract_scan import (
    CodeSite, ContractDebt, SourceReport, _repository_python_files,
    analyze_source, scan_git_tree, scan_tree,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "bilqis.operator-contract-debt/v1"


def debt_counter(debt: tuple[ContractDebt, ...]) -> Counter[tuple[str, ...]]:
    """Track opaque contracts without making safe function extraction illegal."""
    return Counter((item.path, item.kind, item.token) for item in debt)


def new_debt(
    current: Counter[tuple[str, ...]], baseline: Counter[tuple[str, ...]],
) -> tuple[tuple[str, ...], ...]:
    return tuple(key for key, count in sorted(current.items())
                 for _ in range(max(0, count - baseline[key])))


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
    parser.add_argument("--json", action="store_true",
                        help="Output machine-readable atlas data")
    parser.add_argument("--check-baseline", type=Path,
                        help="Exit nonzero if any new raw error identity or opaque policy number appears")
    parser.add_argument("--write-baseline", type=Path,
                        help="Explicit bootstrap only; never refresh baseline to silence new errors")
    args = parser.parse_args(argv)
    report = scan_tree(args.source_root.resolve())
    if args.write_baseline:
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(
            json.dumps(_baseline(debt_counter(report.debt)), indent=2) + "\n")
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
