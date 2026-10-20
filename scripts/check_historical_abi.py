"""Advisory/required source-only guard for original Bilqis model token ABI.

Run locally: python3 -B scripts/check_historical_abi.py
To verify against an independently controlled expectation:
  BILQIS_EXPECTED_ABI_SHA256=<approved-semantic-source-SHA> python3 -B scripts/check_historical_abi.py --require-external
No human/student model optimization is performed or imported by this checker.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bilqis_mlx.semantics.abi import (
    HISTORICAL_ABI, HISTORICAL_PREFIX_SIZE, fingerprint_sheet_prefix,
    require_external_expected, require_historical_prefix,
)


def detect_literal_prefix_count(source_root: Path, count: int) -> tuple[str, ...]:
    """Flag numeric AST constants in live Python, not immutable prose or seeds."""
    problems = []
    for path in sorted((source_root / "bilqis_mlx").rglob("*.py")):
        if "tests" in path.relative_to(source_root / "bilqis_mlx").parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and type(node.value) is int and node.value == count:
                problems.append(f"{path.relative_to(source_root)}:{node.lineno}")
    return tuple(problems)


def check_abi(snapshot_path: Path, *, expected: str | None,
              require_external: bool, check_literal: bool = True,
              root: Path = ROOT) -> dict:
    """Recompute the index/identity/meaning contract from real source records."""
    snapshot = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    actual = fingerprint_sheet_prefix(snapshot)
    require_historical_prefix(actual)
    external = require_external_expected(expected, required=require_external)
    literals = detect_literal_prefix_count(root, HISTORICAL_PREFIX_SIZE) if check_literal else ()
    if literals:
        raise ValueError("HISTORICAL_ABI_SCATTERED_NUMERIC_LITERAL:"+",".join(literals))
    return {
        "release": HISTORICAL_ABI.release,
        "historical_prefix_tokens": HISTORICAL_PREFIX_SIZE,
        "source_index_contract_sha256": actual,
        "source_fields_sha256": HISTORICAL_ABI.source_fields_sha256,
        "external_expected_verified": external,
        "prohibited_executable_literals": len(literals),
        "current_vocab_is_implicitly_capped": False,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path,
                        default=ROOT / "docs/provenance/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json")
    parser.add_argument("--require-external", action="store_true",
                        help="Fail when BILQIS_EXPECTED_INDEX_SHA256 is absent")
    args = parser.parse_args(argv)
    try:
        receipt = check_abi(args.snapshot,
                            expected=os.getenv("BILQIS_EXPECTED_ABI_SHA256"),
                            require_external=args.require_external)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"ABI_GUARD_FAILURE: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(receipt, sort_keys=True))
    if not receipt["external_expected_verified"]:
        print("ABI_GUARD_ADVISORY: independent semantic ABI SHA missing; cannot claim enforced protection",
              file=sys.stderr)


if __name__ == "__main__":
    main()
