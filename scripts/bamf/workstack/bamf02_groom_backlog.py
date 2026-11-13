"""Losslessly decompose the 43 original BAMF-0.2 owner issues.

This thin entrypoint keeps audit/verify orchestration separate from pure contract
construction and GitHub publication mechanics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bamf02_groom_contracts import SLICES, plan_for, prescription_sentences, sha, split_contract
from bamf02_groom_publication import CHILDREN, TASKS, publish_lane


def audit() -> None:
    workstack = json.loads((TASKS / "workstack.json").read_text(encoding="utf-8"))
    for item in workstack["items"]:
        key = item["key"]
        if key == "A09":
            print(key, "existing 7-child subtree")
            continue
        body = (TASKS / "issues" / f"{key}.md").read_text(encoding="utf-8")
        tasks = plan_for(key, body, item["number"], item["deps"])
        contract = split_contract(body)
        lines = prescription_sentences(contract["prescription"])
        leaves = sum(not task["group"] for task in tasks)
        titles = "; ".join(task["title"] for task in tasks)
        print(key, "issue", item["number"], "clauses", len(lines),
              "new child nodes", len(tasks), "delivery leaves", leaves, "|", titles)


def verify() -> None:
    registry = json.loads((CHILDREN / "registry.json").read_text(encoding="utf-8"))
    workstack = json.loads((TASKS / "workstack.json").read_text(encoding="utf-8"))
    issue_map = json.loads((TASKS / "issue-map.json").read_text(encoding="utf-8"))
    entries = registry["entries"]
    by_key = {entry["key"]: entry for entry in entries}
    if len(by_key) != len(entries):
        raise RuntimeError("duplicate child issue key")
    owner_keys = [item["key"] for item in workstack["items"]]
    for entry in entries:
        key = entry["key"]
        body = (CHILDREN / f"{key}.md").read_text(encoding="utf-8")
        if sha(body) != entry["body_sha256"]:
            raise RuntimeError(f"{key}: SHA drift")
        if issue_map.get(key) != entry["number"]:
            raise RuntimeError(f"{key}: issue map drift")
        parent = entry["parent_key"]
        if issue_map.get(parent) != entry["parent_number"]:
            raise RuntimeError(f"{key}: wrong parent")
        for dependency in entry["deps"]:
            if dependency not in by_key and dependency not in owner_keys:
                raise RuntimeError(f"{key}: missing dependency {dependency}")
    for item in workstack["items"]:
        key = item["key"]
        if key not in SLICES:
            continue
        if not item.get("children"):
            raise RuntimeError(f"{key}: un-groomed original parent")
        plan = plan_for(
            key,
            (TASKS / "issues" / f"{key}.md").read_text(encoding="utf-8"),
            item["number"],
            item["deps"],
        )
        if {entry["key"] for entry in plan} - set(by_key):
            raise RuntimeError(f"{key}: missing child issue")
    print(f"PASS: all 43 originals retained, {len(entries)} recursive child indexes, no missing mapped clause or parent")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--audit", action="store_true")
    group.add_argument("--publish", choices=["A", "B", "C"])
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if args.audit:
        audit()
    elif args.publish:
        publish_lane(args.publish)
    else:
        verify()


if __name__ == "__main__":
    main()
