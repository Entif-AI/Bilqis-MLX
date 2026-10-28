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
CHILDREN = json.loads((TASKS / "children/index.json").read_text(encoding="utf-8"))["entries"]
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
INTEGRATION_BRANCH = "codex/bamf-unified-base-20261028"
LANE_BRANCHES = {
    "A": "codex/bamf02-a-semantics",
    "B": "codex/bamf02-b-neural",
    "C": "codex/bamf02-c-runtime",
}


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
        lane = key[0]
        if f"<!-- BAMF02:LANE-BRANCH-LIFECYCLE:{lane} -->" not in body:
            errors.append(f"{key}: missing lane branch lifecycle marker")
        if LANE_BRANCHES[lane] not in body or INTEGRATION_BRANCH not in body:
            errors.append(f"{key}: missing exact lane/integration branch binding")
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

    # Lossless recursive issue-shaping check. The original 43 owner contracts
    # remain full; child files are additional, bounded implementation packets.
    child_map = {child["key"]: child for child in CHILDREN}
    issue_map = json.loads((TASKS / "issue-map.json").read_text(encoding="utf-8"))
    if len(child_map) != len(CHILDREN) or set(child_map) & set(by_key):
        errors.append("duplicate or colliding recursive child key")
    a09_children = next(item for item in ITEMS if item["key"] == "A09").get("children", [])
    if a09_children != ["A09.1", "A09.2", "A09.3", "A09.4", "A09.5"]:
        errors.append("A09: direct child dispatch map drift")
    child_visiting: set[str] = set()
    child_visited: set[str] = set()

    def visit_child(key: str) -> None:
        if key in child_visiting:
            errors.append(f"recursive child dependency cycle at {key}")
            return
        if key in child_visited:
            return
        child_visiting.add(key)
        for dep in child_map[key]["deps"]:
            if dep in child_map:
                visit_child(dep)
            elif dep not in by_key:
                errors.append(f"{key}: unknown prerequisite {dep}")
        child_visiting.remove(key)
        child_visited.add(key)

    for child in CHILDREN:
        key = child["key"]
        parent = child["parent_key"]
        path = TASKS / "children" / f"{key}.md"
        body = path.read_text(encoding="utf-8")
        if hashlib.sha256(body.encode("utf-8")).hexdigest() != child["body_sha256"]:
            errors.append(f"{key}: child body differs from indexed live-GitHub fingerprint")
        if f"<!-- BAMF02:RECURSIVE-CHILD:{key} -->" not in body:
            errors.append(f"{key}: child provenance marker absent")
        if issue_map.get(key) != child["number"]:
            errors.append(f"{key}: issue-map ID mismatch")
        expected_parent = 360 if parent == "A09" else child_map.get(parent, {}).get("number")
        if expected_parent is None or child["parent_number"] != expected_parent:
            errors.append(f"{key}: parent missing or wrong")
        if parent == "A09.1" and child["kind"] != "leaf":
            errors.append(f"{key}: expected bounded leaf below intermediate A09.1")
        for phrase in OBSOLETE_LIVE_POLICY:
            if phrase in body:
                errors.append(f"{key}: obsolete named-grade policy: {phrase}")
        lane = key[0]
        if f"<!-- BAMF02:LANE-BRANCH-LIFECYCLE:{lane} -->" not in body:
            errors.append(f"{key}: missing lane branch lifecycle marker")
        if LANE_BRANCHES[lane] not in body or INTEGRATION_BRANCH not in body:
            errors.append(f"{key}: missing exact lane/integration branch binding")
        visit_child(key)
    if "<!-- BAMF02:A09-LOSSLESS-DECOMPOSITION-20261027 -->" not in (TASKS / "issues/A09.md").read_text(encoding="utf-8"):
        errors.append("A09: no lossless decomposition dispatch in full parent body")
    # All new recursive sub-issues are tracked separately from the historical
    # A09-only index. This validates static contract preservation and routing,
    # not neural execution or any research/execution proof.
    registry_path = TASKS / "children/registry.json"
    if registry_path.exists():
        from bamf02_groom_backlog import plan_for, SLICES

        entries = json.loads(registry_path.read_text(encoding="utf-8"))["entries"]
        all_children = {entry["key"]: entry for entry in entries}
        if len(all_children) != len(entries):
            errors.append("recursive issue registry has duplicate child keys")
        for entry in entries:
            key = entry["key"]
            path = TASKS / "children" / f"{key}.md"
            if not path.exists():
                errors.append(f"{key}: missing child issue mirror")
                continue
            body = path.read_text(encoding="utf-8")
            if hashlib.sha256(body.encode("utf-8")).hexdigest() != entry["body_sha256"]:
                errors.append(f"{key}: child SHA differs from registry")
            if issue_map.get(key) != entry["number"]:
                errors.append(f"{key}: child identity differs from issue map")
            parent = entry["parent_key"]
            if issue_map.get(parent) != entry["parent_number"]:
                errors.append(f"{key}: child has incorrect native parent")
            if parent != "A09" and not parent.startswith("A09.") and f"<!-- BAMF02:WORK-PACKET:{key} -->" not in body:
                errors.append(f"{key}: missing provenance and work-packet marker")
            for dep in entry["deps"]:
                if dep not in by_key and dep not in all_children:
                    errors.append(f"{key}: dependency {dep} absent from work graph")
        for item in ITEMS:
            if item["key"] not in SLICES or not item.get("children"):
                continue
            key = item["key"]
            full = (TASKS / "issues" / f"{key}.md").read_text(encoding="utf-8")
            try:
                planned = plan_for(key, full, item["number"], item["deps"])
                expected = {step["key"] for step in planned}
                if not expected.issubset(all_children):
                    errors.append(f"{key}: lost or unindexed source clauses")
                if [p["key"] for p in planned if p["parent"] == key] != item["children"]:
                    errors.append(f"{key}: direct child dispatch drift")
            except (KeyError, ValueError, IndexError) as exc:
                errors.append(f"{key}: source-prescription partition invalid: {exc}")
    if "decompose" not in (TASKS / "README.md").read_text(encoding="utf-8").lower():
        errors.append("BAMF README missing recursive dispatch rule")
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
    print("PASS: all 200 BAMF owner/child specs bind exact lane branches and reviewed unified lifecycle")
    print("PASS: 12 owner issues and 3 repository entrypoints carry ADR-BAMF02-004")
    print(f"PASS: {len(CHILDREN)} recursive A09 sub-issues retain exact indexed mirrors, linked ownership and acyclic dependencies")
    if registry_path.exists():
        print(f"PASS: {len(entries)} total indexed recursive child mirrors have correct SHA, parent identity and lossless source partitions")
    print("NOTE: live GitHub SHA readback and executable Factory behavior require separate checks")


if __name__ == "__main__":
    main()
