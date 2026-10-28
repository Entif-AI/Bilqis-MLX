"""Losslessly decompose the 43 original BAMF-0.2 owner issues.

This is a work-shaping tool, not a student/Factory implementation or test run.
Only use already-public GitHub issue prose in newly created public child bodies.
The two approved private native Docs are not source inputs to public tickets.

Modes:
  python3 scripts/bamf02_groom_backlog.py --audit
  python3 scripts/bamf02_groom_backlog.py --publish A
  python3 scripts/bamf02_groom_backlog.py --publish B
  python3 scripts/bamf02_groom_backlog.py --publish C
  python3 scripts/bamf02_groom_backlog.py --verify

Public writes require the already-authorized BAMF planning branch, user owner
instruction, exact live-parent parity, and GitHub authentication. Creating
issues/linking parents is resumable; an ambiguous GitHub result is reconciled
from the recent live issue listing before retrying, not assumed to have failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from bamf02_grooming_slices import GROUP_TITLES, NESTED_FIRST_TWO, SLICES
from bamf02_bind_lane_branches import lifecycle_block

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "docs/tasks/bamf-0.2"
CHILDREN = TASKS / "children"
REPO = "Entif-AI/Bilqis-MLX"
ENDPOINT = f"repos/{REPO}"
PROGRESS = CHILDREN / "grooming_progress.json"
MARKER = "<!-- BAMF02:LOSSLESS-CHILD-ROUTING:"


def sha(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def gh(method: str, path: str, payload: dict | None = None):
    cmd = ["gh", "api", "-X", method, path]
    if payload is not None:
        cmd.extend(["--input", "-"])
    result = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"GitHub {method} {path}: {result.stderr[:900]}")
    return json.loads(result.stdout) if result.stdout else None


def split_contract(body: str) -> dict:
    def section(a: str, b: str) -> str:
        return body.split("\n## " + a + "\n", 1)[1].split("\n## " + b + "\n", 1)[0].strip()
    return {
        "outcome": section("Outcome", "Direct dependencies and existing owners"),
        "deps": section("Direct dependencies and existing owners", "Source and allowed edit surface"),
        "paths": section("Source and allowed edit surface", "Interface to implement"),
        "interface": section("Interface to implement", "Implementation prescription"),
        "prescription": section("Implementation prescription", "Relevant shared contracts"),
        "shared": section("Relevant shared contracts", "Acceptance and bounded proof"),
        "acceptance": section("Acceptance and bounded proof", "EGM and faithful execution"),
    }


def prescription_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip())]


def plan_for(key: str, body: str, original_num: int, original_deps: list[str]) -> list[dict]:
    contract = split_contract(body)
    sentences = prescription_sentences(contract["prescription"])
    sliced = SLICES[key]
    if not sliced or sliced[-1][1] != len(sentences):
        raise ValueError(f"{key}: expected final sentence index {len(sentences)}; got {sliced[-1][1]}")
    items: list[dict] = []
    prev = 0
    if key in NESTED_FIRST_TWO:
        items.append(dict(key=f"{key}.1", parent=key, group=True,
                          title=GROUP_TITLES[key],
                          owned=[], deps=list(original_deps), clauses=[], external=list(original_deps)))
    for i, (title, end) in enumerate(sliced):
        if end <= prev or end > len(sentences):
            raise ValueError(f"{key} slice #{i+1} invalid [{prev},{end})")
        if key in NESTED_FIRST_TWO:
            child_key = (f"{key}.1a" if i == 0 else f"{key}.1b" if i == 1 else f"{key}.{i}")
            parent = f"{key}.1" if i <= 1 else key
        else:
            child_key = f"{key}.{i+1}"
            parent = key
        if i == 0:
            deps = list(original_deps)
        else:
            deps = [items[-1]["key"]]
        items.append(dict(key=child_key, parent=parent, group=False, title=title,
                          owned=[prev, end], deps=deps, clauses=sentences[prev:end], external=list(original_deps)))
        prev = end
    # Every complete parent clause is inherited by exactly one implementing leaf.
    covered = [clause for item in items if not item["group"] for clause in item["clauses"]]
    if covered != sentences:
        raise ValueError(f"{key} source clauses missing/duplicated")
    return items


def shared_sections(whole: str, owned_text: str, title: str) -> str:
    headings = re.split(r"(?m)^### ", whole)
    chunks = []
    for h in headings[1:]:
        t, _, rest = h.partition("\n")
        chunks.append((t.strip(), rest.strip()))
    if not chunks:
        return whole[:3500]
    # Select relevant existing contract sections, not newly invented policy.
    words = lambda s: set(re.findall(r"[a-z]{4,}", s.lower())) - {
        "existing", "contract", "section", "source", "qualified", "version", "original", "their",
        "exact", "this", "that", "with", "from", "into", "under", "current", "which", "while"
    }
    target = words(title + " " + owned_text)
    ranked = sorted(chunks, key=lambda x: (-len(words(x[0] + " " + x[1]) & target), x[0]))
    selected = ranked[:2]
    return "\n\n".join(f"### {t}\n{s}" for t,s in selected)


def child_body(key: str, d: dict, byid: dict[str, int], parent_text: str, owner_num: int) -> str:
    c = split_contract(parent_text)
    parent = d["parent"]
    parent_id = owner_num if parent == key else byid.get(parent)
    p = f"[{parent} #{parent_id}](https://github.com/{REPO}/issues/{parent_id})" if parent_id else f"{parent} (linked by this publishing batch)"
    dep_links = ", ".join(
        f"[{x} #{byid[x]}](https://github.com/{REPO}/issues/{byid[x]})" if x in byid
        else f"{x} (original workstack dependency)" for x in d["deps"]
    ) or "No additional BAMF dependency; preserve the original parent's external prerequisites."
    intro = f"""<!-- BAMF02:WORK-PACKET:{d['key']} -->
# {d['key']} | {d['title']}

**BAMF-0.2 implementation packet. Lane {key[0]}.** Full original owner: [{key} #{owner_num}](https://github.com/{REPO}/issues/{owner_num}); direct native parent: {p}. **This issue is {'a non-implementing group' if d['group'] else 'an implementable leaf'}**, not an amendment to the approved design.

{lifecycle_block(key[0]).rstrip()}

## Authority and lossless scope
The two approved BAMF-0.2 native Docs, the original complete [{key} issue #{owner_num}](https://github.com/{REPO}/issues/{owner_num}), root #341, ADR-BAMF02-004 and existing source/Factory rights remain controlling. No original algorithm, schema, acceptance, correctness constraint or workload is waived, simplified or removed. The parent's full acceptance remains with its eventual integration. Prior BAV/Grade-B exceptions and the rejected alternate design do not become current policy. All grades use the same functional recursive Factory/teacher/retention machinery with typed source-family-specific rule subsets, not grade-based branches. Live optimizer starts remain human-owned.

## Direct prerequisites
{dep_links}. Original {key} external dependency contract is preserved exactly: {c['deps'][:1700]}

## Original owner API and allowed edit surface
{c['interface']}

{c['paths']}

"""
    if d["group"]:
        return intro + f"""## Group outcome and recursive boundaries
This node groups the first two contracts of {key} because their shared state/interface must be agreed before dependent units. This is **not a coding assignment**. Its implementation is divided into its two native grandchildren, assigned and independently accepted as separate GitHub issues. Preserve all original requirements and integration acceptance when the group closes. No direct code patch, new research protocol or neural training is authorized by this grouping.

## Completion
Both grandchildren must be integrated with compatible records and literal acceptance results, followed by the parent's eventual end-to-end checks. Assign workers to grandchildren rather than to this group.
"""
    owned = "\n".join(f"{i+1}. {s}" for i,s in enumerate(d["clauses"]))
    shared = shared_sections(c["shared"], owned, d["title"])
    # Include full original acceptance to avoid dropping a rare negative invariant;
    # distinguish parent-wide conditions from this child-sized implementation.
    acceptance = c["acceptance"]
    reasoning = "higher reasoning recommended for critical shared-state or numeric invariants" if key in {
        "A08", "B01", "B04", "B09", "B12", "B13", "C05", "C07", "C13", "C15", "C16"
    } else "bounded low/medium-reasoning candidate when its interfaces are frozen"
    return intro + f"""## Exact implementation obligation owned by this child
**Required deliverable:** {d['title']}. Implement the following **verbatim, in-order clauses from the original {key} prescription**. These are not paraphrases and none may be skipped; out-of-scope original clauses belong to sibling issues and finally to the parent integrator.

{owned}

## Authoritative shared contract excerpt for this outcome
The following is directly inherited from original {key}, not a replacement for the complete parent specification.

{shared}

## Acceptance and finish boundary
Child completion requires implementation of every owned clause, a direct API/shape/status witness using the original parent's stated package-local test surface where applicable, and one verifiable commit + issue/PR receipt. No unrelated parent-wide feature is declared complete merely because this packet closes. **The original owner's entire existing acceptance is preserved below** for integration traceability; assign its checks to the actual implementing descendants and require the final parent integrator to reconcile every clause. Avoid running any new speculative research experiments.

### Unmodified original parent acceptance
{acceptance}

## Agent execution and handoff
**Original EGM review:** Use Google EGM pinned at `b3a35956759bf7f024af2ff061b2e0b44b438e4c`. A fresh Goldfish reviews this Elephant implementation (or a cohesive batch of at most three leaves); blockers and majors are resolved or contested with evidence. Without independent review, record `EGM_PENDING` for the integrator. A same-context self-review is not independent.

**Original PR turn-in:** Push and read back the branch SHA, comment on the issue and lane PR, and add the actual GitHub child issue number to the PR Development closing links. The parent remains open until descendants and original acceptance are integrated.

Agent fit: {reasoning}. Read root README.md and AGENTS.md once, this exact child and its direct dependency receipts, then only the assigned source paths. The original technical specifications stay complete. If this work still exceeds one coherent bounded patch, subdivide **this child again** before cutting requirements. Coordinate shared paths through the lane's one writer, maintain source-gold and neural/optimizer custody, use small software checks of already-specified behavior, and record the exact child issue, changed paths, tests, branch/head SHA, and next unblocked child. Do not run the actual student or merge main from this issue.
"""


def read_progress() -> dict:
    if not PROGRESS.exists():
        return {}
    return json.loads(PROGRESS.read_text(encoding="utf-8"))


def save_progress(p: dict) -> None:
    CHILDREN.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(p, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def existing_title(title: str):
    # Issue creation may succeed before a transport error. Reconcile exact
    # titles/markers from all recent issues rather than immediately retrying.
    for page in range(1, 5):
        items = gh("GET", f"{ENDPOINT}/issues?state=all&sort=created&direction=desc&per_page=100&page={page}")
        found = [i for i in items if i.get("title") == title and not i.get("pull_request")]
        if found:
            return found[0]
        if len(items) < 100:
            break
    return None


def publish_issue(d: dict, parent_key: str, parent_num: int, full_parent: str,
                  identifiers: dict[str, int], progress: dict) -> dict:
    k = d["key"]
    title = f"BAMF-0.2 {k} | {d['title']}"
    if k in identifiers:
        issue = gh("GET", f"{ENDPOINT}/issues/{identifiers[k]}")
        if issue["title"] != title:
            raise RuntimeError(f"{k}: issue title mismatch, refuse accidental overwrite")
    else:
        issue = existing_title(title)
        if issue is None:
            issue = gh("POST", f"{ENDPOINT}/issues", {
                "title": title,
                "body": child_body(parent_key, d, identifiers, full_parent, parent_num)
            })
        if f"<!-- BAMF02:WORK-PACKET:{k} -->" not in (issue.get("body") or ""):
            raise RuntimeError(f"{k}: matching issue title lacks provenance marker")
        identifiers[k] = int(issue["number"])
        progress[k] = identifiers[k]
        save_progress(progress)
    parent_id = parent_num if d["parent"] == parent_key else identifiers[d["parent"]]
    linked = gh("GET", f"{ENDPOINT}/issues/{parent_id}/sub_issues")
    if identifiers[k] not in [x["number"] for x in linked]:
        gh("POST", f"{ENDPOINT}/issues/{parent_id}/sub_issues", {"sub_issue_id":issue["id"]})
    return issue


def append_parent_navigation(key: str, full: str, descendants: list[dict], identifiers: dict[str,int]) -> str:
    marker = MARKER + key + " -->"
    if marker in full:
        return full
    lines = [marker, "## Lossless recursive implementation routing | 27 October 2026", "",
             "**The complete technical specification and acceptance below remain unchanged.** This issue is an integration/ownership parent, not one low-tier coding assignment. Assign the deepest dependency-ready implementation child; group nodes are not coding tasks. Every child inherits the original source, safety, engineering and acceptance contracts. Close this parent only when all child outcomes and all original owner acceptance conditions are satisfied.", ""]
    for d in descendants:
        child_key = d["key"]
        num = identifiers[child_key]
        label = "intermediate group (assign grandchildren)" if d["group"] else "bounded implementable leaf"
        lines.append(f"- [{child_key} #{num}](https://github.com/{REPO}/issues/{num}) | {d['title']} | {label}; parent {d['parent']}.")
    lines.append("")
    lines.append("Source semantics, grades, privacy, optimizer custody, independent gold and implementation acceptance are not relaxed. This planning/decomposition pass runs no live learner, BAV crosswalk or new research experiment.")
    lines.extend(["", ""])
    anchor = "## Direct dependencies and existing owners\n"
    if full.count(anchor)!=1:
        raise RuntimeError(f"{key}: nonunique safe insertion anchor")
    return full.replace(anchor, "\n".join(lines)+anchor, 1)


def publish_lane(lane: str) -> None:
    # Continue the existing worktree and exact planning branch, never main.
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    if branch != "codex/bamf02-specification-20261027":
        raise RuntimeError(f"unsafe branch: {branch}")
    ws = json.loads((TASKS / "workstack.json").read_text(encoding="utf-8"))
    mapping = json.loads((TASKS / "issue-map.json").read_text(encoding="utf-8"))
    progress = read_progress()
    for item in [x for x in ws["items"] if x["lane"] == lane]:
        key = item["key"]
        if key == "A09":
            print("SKIP A09: earlier native #389-#395 subtree preserved", flush=True)
            continue
        # Existing native children outside this plan should cause explicit
        # reconciliation rather than competing ownership.
        number = item["number"]
        original = (TASKS / "issues" / f"{key}.md").read_text(encoding="utf-8")
        live = gh("GET", f"{ENDPOINT}/issues/{number}")
        current = live.get("body") or ""
        if current != original and MARKER + key not in current:
            raise RuntimeError(f"{key}: live parent has unexpected drift; reconcile first")
        descendants = plan_for(key, original, number, item["deps"])
        identifiers = dict(mapping)
        identifiers.update({k:int(v) for k,v in progress.items()})
        # Mark existing full parent spec in the local Git history before edits.
        if not any(d["key"] in identifiers for d in descendants):
            preexisting = gh("GET", f"{ENDPOINT}/issues/{number}/sub_issues")
            if preexisting:
                raise RuntimeError(f"{key}: unindexed live child already exists")
        for d in descendants:
            created = publish_issue(d, key, number, original, identifiers, progress)
            print(f"{lane} {key} {d['key']} #{created['number']} linked", flush=True)
        # Rewrite final child refs only after all siblings have stable IDs.
        for d in descendants:
            k = d["key"]
            body = child_body(key, d, identifiers, original, number)
            live_child = gh("GET", f"{ENDPOINT}/issues/{identifiers[k]}")
            if live_child.get("body") != body:
                gh("PATCH", f"{ENDPOINT}/issues/{identifiers[k]}", {"body": body})
            actual = gh("GET", f"{ENDPOINT}/issues/{identifiers[k]}")
            if actual.get("body") != body:
                raise RuntimeError(f"{k}: child readback failed")
            (CHILDREN / f"{k}.md").write_text(body, encoding="utf-8")
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
        (TASKS / "workstack.json").write_text(json.dumps(ws, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        (TASKS / "issue-map.json").write_text(json.dumps(mapping,indent=2)+"\n",encoding="utf-8")
        refresh_registry()
        print(f"DONE OWNER {key} #{number} children={len(descendants)}; full original preserved",flush=True)


def refresh_registry() -> None:
    ws=json.loads((TASKS/"workstack.json").read_text(encoding="utf-8"))
    mp=json.loads((TASKS/"issue-map.json").read_text(encoding="utf-8"))
    old=json.loads((CHILDREN/"index.json").read_text(encoding="utf-8"))["entries"]
    all_entries={e["key"]:e for e in old}
    for item in ws["items"]:
        key=item["key"]
        if key=="A09" or not item.get("children"):
            continue
        original=(TASKS/"issues"/f"{key}.md").read_text(encoding="utf-8")
        # Reconstruct the original prescription; appended navigation does not
        # affect its Implementation prescription section.
        plan=plan_for(key,original,item["number"],item["deps"])
        for d in plan:
            k=d["key"]
            if k not in mp:
                continue
            path=CHILDREN/f"{k}.md"
            if not path.exists():
                continue
            c=path.read_text(encoding="utf-8")
            par=d["parent"]
            all_entries[k]=dict(key=k,number=mp[k],parent_key=par,
                                parent_number=mp[par],deps=d["deps"],
                                kind="group" if d["group"] else "leaf",
                                title=f"BAMF-0.2 {k} | {d['title']}",body_sha256=sha(c),
                                clause_span=d["owned"],source_parent_sha256=item["body_sha256"])
    entries=sorted(all_entries.values(),key=lambda e:(e["key"][0],int(e["key"].split(".")[0][1:]),e["key"].split(".")[1] if "." in e["key"] else ""))
    registry=dict(schema="bilqis.bamf.all-child-registry/v1",program="BAMF-0.2",
                  original_owners=43,entries=entries)
    (CHILDREN/"registry.json").write_text(json.dumps(registry,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    lines=["# BAMF-0.2 recursively decomposed implementation issues", "",
           "The original 43 owner contracts stay authoritative and unabridged. Agents take the deepest ready child. See `registry.json` for exact stable identities, parent links, dependency graph, source-clause spans and body hashes.", ""]
    for e in entries:
        lines.append(f"- [{e['key']} #{e['number']}](https://github.com/{REPO}/issues/{e['number']}): {e['title'].split(' | ',1)[-1]} ({e['kind']}; parent {e['parent_key']})")
    (CHILDREN/"README.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


def audit() -> None:
    ws=json.loads((TASKS/"workstack.json").read_text(encoding="utf-8"))
    for item in ws["items"]:
        key=item["key"]
        if key=="A09":
            print(key,"existing 7-child subtree")
            continue
        body=(TASKS/"issues"/f"{key}.md").read_text(encoding="utf-8")
        tasks=plan_for(key,body,item["number"],item["deps"])
        c=split_contract(body)
        lines=prescription_sentences(c["prescription"])
        print(key,"issue",item["number"],"clauses",len(lines),"new child nodes",len(tasks),"delivery leaves",sum(not d["group"] for d in tasks),"|", "; ".join(d["title"] for d in tasks))


def verify() -> None:
    registry=json.loads((CHILDREN/"registry.json").read_text(encoding="utf-8"))
    ws=json.loads((TASKS/"workstack.json").read_text(encoding="utf-8"))
    mp=json.loads((TASKS/"issue-map.json").read_text(encoding="utf-8"))
    entries=registry["entries"]
    bykey={e["key"]:e for e in entries}
    if len(bykey)!=len(entries):raise RuntimeError("duplicate child issue key")
    for e in entries:
        k=e["key"]
        body=(CHILDREN/f"{k}.md").read_text(encoding="utf-8")
        if sha(body)!=e["body_sha256"]:raise RuntimeError(f"{k}: SHA drift")
        if mp.get(k)!=e["number"]:raise RuntimeError(f"{k}: issue map drift")
        par=e["parent_key"]
        if mp.get(par)!=e["parent_number"]:raise RuntimeError(f"{k}: wrong parent")
        for dep in e["deps"]:
            if dep not in bykey and dep not in [i["key"] for i in ws["items"]]:
                raise RuntimeError(f"{k}: missing dependency {dep}")
    for item in ws["items"]:
        k=item["key"]
        if k not in SLICES:continue
        if not item.get("children"):
            raise RuntimeError(f"{k}: un-groomed original parent")
        plan=plan_for(k,(TASKS/"issues"/f"{k}.md").read_text(encoding="utf-8"),item["number"],item["deps"])
        if set(d["key"] for d in plan)-set(bykey):
            raise RuntimeError(f"{k}: missing child issue")
    print(f"PASS: all 43 originals retained, {len(entries)} recursive child indexes, no missing mapped clause or parent")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--audit",action="store_true")
    group.add_argument("--publish",choices=["A","B","C"])
    group.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    if args.audit:audit()
    elif args.publish:publish_lane(args.publish)
    else:verify()
