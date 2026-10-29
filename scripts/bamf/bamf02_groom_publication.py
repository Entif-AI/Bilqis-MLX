"""GitHub publication and registry mutation for BAMF-0.2 backlog grooming."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from bamf02_groom_contracts import REPO, child_body, plan_for, sha

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "docs/tasks/bamf-0.2"
CHILDREN = TASKS / "children"
ENDPOINT = f"repos/{REPO}"
PROGRESS = CHILDREN / "grooming_progress.json"
MARKER = "<!-- BAMF02:LOSSLESS-CHILD-ROUTING:"


def gh(method: str, path: str, payload: dict | None = None):
    cmd = ["gh", "api", "-X", method, path]
    if payload is not None:
        cmd.extend(["--input", "-"])
    result = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"GitHub {method} {path}: {result.stderr[:900]}")
    return json.loads(result.stdout) if result.stdout else None


def read_progress() -> dict:
    if not PROGRESS.exists():
        return {}
    return json.loads(PROGRESS.read_text(encoding="utf-8"))


def save_progress(progress: dict) -> None:
    CHILDREN.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def existing_title(title: str):
    for page in range(1, 5):
        items = gh("GET", f"{ENDPOINT}/issues?state=all&sort=created&direction=desc&per_page=100&page={page}")
        found = [item for item in items if item.get("title") == title and not item.get("pull_request")]
        if found:
            return found[0]
        if len(items) < 100:
            break
    return None


def publish_issue(d: dict, parent_key: str, parent_num: int, full_parent: str,
                  identifiers: dict[str, int], progress: dict) -> dict:
    key = d["key"]
    title = f"BAMF-0.2 {key} | {d['title']}"
    if key in identifiers:
        issue = gh("GET", f"{ENDPOINT}/issues/{identifiers[key]}")
        if issue["title"] != title:
            raise RuntimeError(f"{key}: issue title mismatch, refuse accidental overwrite")
    else:
        issue = existing_title(title)
        if issue is None:
            issue = gh("POST", f"{ENDPOINT}/issues", {
                "title": title,
                "body": child_body(parent_key, d, identifiers, full_parent, parent_num),
            })
        if f"<!-- BAMF02:WORK-PACKET:{key} -->" not in (issue.get("body") or ""):
            raise RuntimeError(f"{key}: matching issue title lacks provenance marker")
        identifiers[key] = int(issue["number"])
        progress[key] = identifiers[key]
        save_progress(progress)
    parent_id = parent_num if d["parent"] == parent_key else identifiers[d["parent"]]
    linked = gh("GET", f"{ENDPOINT}/issues/{parent_id}/sub_issues")
    if identifiers[key] not in [item["number"] for item in linked]:
        gh("POST", f"{ENDPOINT}/issues/{parent_id}/sub_issues", {"sub_issue_id": issue["id"]})
    return issue


def append_parent_navigation(key: str, full: str, descendants: list[dict], identifiers: dict[str, int]) -> str:
    marker = MARKER + key + " -->"
    if marker in full:
        return full
    lines = [marker, "## Lossless recursive implementation routing | 27 October 2026", "",
             "**The complete technical specification and acceptance below remain unchanged.** This issue is an integration/ownership parent, not one low-tier coding assignment. Assign the deepest dependency-ready implementation child; group nodes are not coding tasks. Every child inherits the original source, safety, engineering and acceptance contracts. Close this parent only when all child outcomes and all original owner acceptance conditions are satisfied.", ""]
    for d in descendants:
        child_key = d["key"]
        number = identifiers[child_key]
        label = "intermediate group (assign grandchildren)" if d["group"] else "bounded implementable leaf"
        lines.append(f"- [{child_key} #{number}](https://github.com/{REPO}/issues/{number}) | {d['title']} | {label}; parent {d['parent']}.")
    lines.extend(["", "Source semantics, grades, privacy, optimizer custody, independent gold and implementation acceptance are not relaxed. This planning/decomposition pass runs no live learner, BAV crosswalk or new research experiment.", "", ""])
    anchor = "## Direct dependencies and existing owners\n"
    if full.count(anchor) != 1:
        raise RuntimeError(f"{key}: nonunique safe insertion anchor")
    return full.replace(anchor, "\n".join(lines) + anchor, 1)


def publish_lane(lane: str) -> None:
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    if branch != "codex/bamf02-specification-20261027":
        raise RuntimeError(f"unsafe branch: {branch}")
    workstack = json.loads((TASKS / "workstack.json").read_text(encoding="utf-8"))
    mapping = json.loads((TASKS / "issue-map.json").read_text(encoding="utf-8"))
    progress = read_progress()
    for item in [entry for entry in workstack["items"] if entry["lane"] == lane]:
        key = item["key"]
        if key == "A09":
            print("SKIP A09: earlier native #389-#395 subtree preserved", flush=True)
            continue
        number = item["number"]
        original = (TASKS / "issues" / f"{key}.md").read_text(encoding="utf-8")
        live = gh("GET", f"{ENDPOINT}/issues/{number}")
        current = live.get("body") or ""
        if current != original and MARKER + key not in current:
            raise RuntimeError(f"{key}: live parent has unexpected drift; reconcile first")
        descendants = plan_for(key, original, number, item["deps"])
        identifiers = dict(mapping)
        identifiers.update({k: int(v) for k, v in progress.items()})
        if not any(d["key"] in identifiers for d in descendants):
            preexisting = gh("GET", f"{ENDPOINT}/issues/{number}/sub_issues")
            if preexisting:
                raise RuntimeError(f"{key}: unindexed live child already exists")
        for d in descendants:
            created = publish_issue(d, key, number, original, identifiers, progress)
            print(f"{lane} {key} {d['key']} #{created['number']} linked", flush=True)
        for d in descendants:
            child_key = d["key"]
            body = child_body(key, d, identifiers, original, number)
            live_child = gh("GET", f"{ENDPOINT}/issues/{identifiers[child_key]}")
            if live_child.get("body") != body:
                gh("PATCH", f"{ENDPOINT}/issues/{identifiers[child_key]}", {"body": body})
            actual = gh("GET", f"{ENDPOINT}/issues/{identifiers[child_key]}")
            if actual.get("body") != body:
                raise RuntimeError(f"{child_key}: child readback failed")
            (CHILDREN / f"{child_key}.md").write_text(body, encoding="utf-8")
        proposed = append_parent_navigation(key, original, descendants, identifiers)
        if current != proposed:
            gh("PATCH", f"{ENDPOINT}/issues/{number}", {"body": proposed})
        readback = gh("GET", f"{ENDPOINT}/issues/{number}")
        if readback.get("body") != proposed:
            raise RuntimeError(f"{key}: original parent navigation readback failed")
        (TASKS / "issues" / f"{key}.md").write_text(proposed, encoding="utf-8")
        item["body_sha256"] = sha(proposed)
        item["children"] = [d["key"] for d in descendants if d["parent"] == key]
        item["execution_role"] = "integration_parent_after_recursive_decomposition"
        mapping.update({d["key"]: identifiers[d["key"]] for d in descendants})
        (TASKS / "workstack.json").write_text(json.dumps(workstack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (TASKS / "issue-map.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
        refresh_registry()
        print(f"DONE OWNER {key} #{number} children={len(descendants)}; full original preserved", flush=True)


def refresh_registry() -> None:
    workstack = json.loads((TASKS / "workstack.json").read_text(encoding="utf-8"))
    mapping = json.loads((TASKS / "issue-map.json").read_text(encoding="utf-8"))
    old = json.loads((CHILDREN / "index.json").read_text(encoding="utf-8"))["entries"]
    all_entries = {entry["key"]: entry for entry in old}
    for item in workstack["items"]:
        key = item["key"]
        if key == "A09" or not item.get("children"):
            continue
        original = (TASKS / "issues" / f"{key}.md").read_text(encoding="utf-8")
        for d in plan_for(key, original, item["number"], item["deps"]):
            child_key = d["key"]
            if child_key not in mapping:
                continue
            path = CHILDREN / f"{child_key}.md"
            if not path.exists():
                continue
            body = path.read_text(encoding="utf-8")
            parent = d["parent"]
            all_entries[child_key] = dict(
                key=child_key, number=mapping[child_key], parent_key=parent,
                parent_number=mapping[parent], deps=d["deps"],
                kind="group" if d["group"] else "leaf",
                title=f"BAMF-0.2 {child_key} | {d['title']}", body_sha256=sha(body),
                clause_span=d["owned"], source_parent_sha256=item["body_sha256"],
            )
    entries = sorted(all_entries.values(), key=lambda entry: (
        entry["key"][0], int(entry["key"].split(".")[0][1:]),
        entry["key"].split(".")[1] if "." in entry["key"] else "",
    ))
    registry = dict(schema="bilqis.bamf.all-child-registry/v1", program="BAMF-0.2",
                    original_owners=43, entries=entries)
    (CHILDREN / "registry.json").write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# BAMF-0.2 recursively decomposed implementation issues", "",
             "The original 43 owner contracts stay authoritative and unabridged. Agents take the deepest ready child. See `registry.json` for exact stable identities, parent links, dependency graph, source-clause spans and body hashes.", ""]
    for entry in entries:
        lines.append(f"- [{entry['key']} #{entry['number']}](https://github.com/{REPO}/issues/{entry['number']}): {entry['title'].split(' | ', 1)[-1]} ({entry['kind']}; parent {entry['parent_key']})")
    (CHILDREN / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
