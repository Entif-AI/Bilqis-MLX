"""Report production size debt; reject new or worsened hard-limit violations.

Only active Python under bilqis_mlx is production here. Vendor, generated source
exports, tests and fixtures are outside this inventory. Size prompts architecture
review; the baseline records inherited debt rather than declaring it acceptable.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs/evidence/development/module_size_baseline.json"
MODULE_REVIEW = 800
MODULE_HARD = 1200
FUNCTION_REVIEW = 150
FUNCTION_HARD = 300
EXCLUDED_PARTS = frozenset({"tests", "fixtures", "__pycache__", "generated"})


def inventory(root: Path) -> dict[str, int]:
    sizes = {}
    for path in sorted((root / "bilqis_mlx").rglob("*.py")):
        if EXCLUDED_PARTS.intersection(path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        sizes[relative] = len(source.splitlines())

        def functions(node, parents=()):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names = (*parents, child.name)
                    if not isinstance(child, ast.ClassDef):
                        sizes[relative + "::" + ".".join(names)] = child.end_lineno - child.lineno + 1
                    functions(child, names)
                else:
                    functions(child, parents)
        functions(ast.parse(source, filename=relative))
    return sizes


def violations(current: dict[str, int], baseline: dict[str, int]) -> list[str]:
    return [key for key, size in sorted(current.items())
            if size >= (FUNCTION_HARD if "::" in key else MODULE_HARD)
            and size > baseline.get(key, 0)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    args = parser.parse_args(argv)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    if baseline.get("schema") != "bilqis.production-size-baseline/v1":
        raise ValueError("MODULE_SIZE_BASELINE_SCHEMA_INVALID")
    current = inventory(ROOT)
    for kind, separator, threshold in (("MODULE", False, MODULE_REVIEW),
                                       ("FUNCTION", True, FUNCTION_REVIEW)):
        review = [(key, size) for key, size in current.items()
                  if ("::" in key) == separator and size >= threshold]
        for key, size in sorted(review, key=lambda item: (-item[1], item[0])):
            print(f"SIZE_REVIEW {kind} {size} {key}")
    new = violations(current, baseline["sizes"])
    for key in new:
        print(f"SIZE_REGRESSION {current[key]} {key}")
    print(f"MODULE_SIZE_CHECK {'FAILED' if new else 'OK'} new_or_worsened={len(new)}")
    return 1 if new else 0


if __name__ == "__main__":
    raise SystemExit(main())
