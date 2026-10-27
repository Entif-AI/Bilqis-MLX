"""Verify BAMF-0.2 issue mirrors and executable planning-contract metadata.

This is a static document/issue alignment check. It does not prove that BAMF
training or the recursive curriculum planner has been implemented or run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "docs/tasks/bamf-0.2"
ITEMS = json.loads((TASKS / "workstack.json").read_text(encoding="utf-8"))["items"]
REQUIRED_ADR = {
    "A08", "A09", "B09", "C01", "C02", "C03", "C05", "C06",
    "C07", "C14", "C15", "C16",
}
OBSOLETE_LIVE_POLICY = (
    "B's nongating debt follows ADR-094",
    "one complete imperfect-B turn",
    "C progresses while carrying B debt",
    "Keep B debt and numeric scope from the real run manifest",
)


def section(body: str, start: str, end: str) -> str:
    before = "\n## " + start + "\n"
    after = "\n## " + end + "\n"
    return body.split(before, 1)[1].split(after, 1)[0].strip()


def main() -> None:
    errors: list[str] = []
    keys = [item["key"] for item in ITEMS]
    if len(keys) != 43 or len(set(keys)) != 43:
        errors.append(f"expected 43 unique BAMF leaves, got {len(keys)} / {len(set(keys))}")
    by_key = {item["key"]: item for item in ITEMS}
    for item in ITEMS:
        key = item["key"]
        path = TASKS / "issues" / f"{key}.md"
        body = path.read_text(encoding="utf-8")
        actual_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if actual_sha != item["body_sha256"]:
            errors.append(f"{key}: mirror SHA differs from workstack/live issue receipt")
        try:
            expected_api = section(body, "Interface to implement", "Implementation prescription").split("\n\n", 1)[0].strip("`")
            expected_steps = section(body, "Implementation prescription", "Relevant shared contracts")
            expected_tests = section(body, "Acceptance and bounded proof", "EGM and faithful execution")
            for field, expected in (("api", expected_api), ("steps", expected_steps), ("tests", expected_tests)):
                if item[field] != expected:
                    errors.append(f"{key}: stale workstack.{field}")
        except (IndexError, KeyError) as exc:
            errors.append(f"{key}: malformed issue sections: {exc}")
        for phrase in OBSOLETE_LIVE_POLICY:
            if phrase in body:
                errors.append(f"{key}: obsolete grade-specific BAMF policy: {phrase}")
        if key in REQUIRED_ADR and "<!-- BAMF02:ADR-004-FUNCTIONAL-FACTORY -->" not in body:
            errors.append(f"{key}: missing ADR-004 functional Factory acceptance")
        if item["number"] < 345 or item["number"] > 387:
            errors.append(f"{key}: unexpected issue #{item['number']}")
        for dep in item["deps"]:
            if dep not in by_key:
                errors.append(f"{key}: missing dependency {dep}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            errors.append(f"dependency cycle at {key}")
            return
        if key in visited:
            return
        visiting.add(key)
        for dependency in by_key[key]["deps"]:
            if dependency in by_key:
                visit(dependency)
        visiting.remove(key)
        visited.add(key)

    for key in keys:
        visit(key)
    for filename in ("README.md", "AGENTS.md", "docs/architecture/BAMF_0_2.md"):
        text = (ROOT / filename).read_text(encoding="utf-8")
        if "ADR-BAMF02-004" not in text:
            errors.append(f"{filename}: missing ADR-004")
    if errors:
        for error in errors:
            print("FAIL:", error)
        raise SystemExit(1)
    print("PASS: 43/43 exact checked-in issue mirrors equal workstack SHA-256 receipts")
    print("PASS: 43/43 issue API, implementation and acceptance fields match workstack")
    print("PASS: no missing/cyclic dependencies, no obsolete named-grade debt exception")
    print("PASS: 12 owner issues and 3 repository entrypoints carry ADR-BAMF02-004")
    print("NOTE: live GitHub SHA readback and executable Factory behavior require separate checks")


if __name__ == "__main__":
    main()
