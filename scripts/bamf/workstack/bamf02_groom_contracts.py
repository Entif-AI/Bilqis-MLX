"""Pure contract parsing and child-body construction for BAMF-0.2 grooming."""
from __future__ import annotations

import hashlib
import re

from bamf02_bind_lane_branches import lifecycle_block
from bamf02_grooming_slices import GROUP_TITLES, NESTED_FIRST_TWO, SLICES

REPO = "Entif-AI/Bilqis-MLX"


def sha(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


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
    del original_num
    contract = split_contract(body)
    sentences = prescription_sentences(contract["prescription"])
    sliced = SLICES[key]
    if not sliced or sliced[-1][1] != len(sentences):
        raise ValueError(f"{key}: expected final sentence index {len(sentences)}; got {sliced[-1][1]}")
    items: list[dict] = []
    prev = 0
    if key in NESTED_FIRST_TWO:
        items.append(dict(key=f"{key}.1", parent=key, group=True,
                          title=GROUP_TITLES[key], owned=[], deps=list(original_deps),
                          clauses=[], external=list(original_deps)))
    for i, (title, end) in enumerate(sliced):
        if end <= prev or end > len(sentences):
            raise ValueError(f"{key} slice #{i+1} invalid [{prev},{end})")
        if key in NESTED_FIRST_TWO:
            child_key = f"{key}.1a" if i == 0 else f"{key}.1b" if i == 1 else f"{key}.{i}"
            parent = f"{key}.1" if i <= 1 else key
        else:
            child_key = f"{key}.{i+1}"
            parent = key
        deps = list(original_deps) if i == 0 else [items[-1]["key"]]
        items.append(dict(key=child_key, parent=parent, group=False, title=title,
                          owned=[prev, end], deps=deps, clauses=sentences[prev:end],
                          external=list(original_deps)))
        prev = end
    covered = [clause for item in items if not item["group"] for clause in item["clauses"]]
    if covered != sentences:
        raise ValueError(f"{key} source clauses missing/duplicated")
    return items


def shared_sections(whole: str, owned_text: str, title: str) -> str:
    headings = re.split(r"(?m)^### ", whole)
    chunks = []
    for heading in headings[1:]:
        name, _, rest = heading.partition("\n")
        chunks.append((name.strip(), rest.strip()))
    if not chunks:
        return whole[:3500]

    def words(value: str) -> set[str]:
        return set(re.findall(r"[a-z]{4,}", value.lower())) - {
            "existing", "contract", "section", "source", "qualified", "version",
            "original", "their", "exact", "this", "that", "with", "from", "into",
            "under", "current", "which", "while",
        }

    target = words(title + " " + owned_text)
    ranked = sorted(chunks, key=lambda item: (-len(words(item[0] + " " + item[1]) & target), item[0]))
    return "\n\n".join(f"### {name}\n{text}" for name, text in ranked[:2])


def child_body(key: str, d: dict, byid: dict[str, int], parent_text: str, owner_num: int) -> str:
    contract = split_contract(parent_text)
    parent = d["parent"]
    parent_id = owner_num if parent == key else byid.get(parent)
    parent_link = (
        f"[{parent} #{parent_id}](https://github.com/{REPO}/issues/{parent_id})"
        if parent_id else f"{parent} (linked by this publishing batch)"
    )
    dep_links = ", ".join(
        f"[{dep} #{byid[dep]}](https://github.com/{REPO}/issues/{byid[dep]})"
        if dep in byid else f"{dep} (original workstack dependency)"
        for dep in d["deps"]
    ) or "No additional BAMF dependency; preserve the original parent's external prerequisites."
    intro = f"""<!-- BAMF02:WORK-PACKET:{d['key']} -->
# {d['key']} | {d['title']}

**BAMF-0.2 implementation packet. Lane {key[0]}.** Full original owner: [{key} #{owner_num}](https://github.com/{REPO}/issues/{owner_num}); direct native parent: {parent_link}. **This issue is {'a non-implementing group' if d['group'] else 'an implementable leaf'}**, not an amendment to the approved design.

{lifecycle_block(key[0]).rstrip()}

## Authority and lossless scope
The two approved BAMF-0.2 native Docs, the original complete [{key} issue #{owner_num}](https://github.com/{REPO}/issues/{owner_num}), root #341, ADR-BAMF02-004 and existing source/Factory rights remain controlling. No original algorithm, schema, acceptance, correctness constraint or workload is waived, simplified or removed. The parent's full acceptance remains with its eventual integration. Prior BAV/Grade-B exceptions and the rejected alternate design do not become current policy. All grades use the same functional recursive Factory/teacher/retention machinery with typed source-family-specific rule subsets, not grade-based branches. Live optimizer starts remain human-owned.

## Direct prerequisites
{dep_links}. Original {key} external dependency contract is preserved exactly: {contract['deps'][:1700]}

## Original owner API and allowed edit surface
{contract['interface']}

{contract['paths']}

"""
    if d["group"]:
        return intro + f"""## Group outcome and recursive boundaries
This node groups the first two contracts of {key} because their shared state/interface must be agreed before dependent units. This is **not a coding assignment**. Its implementation is divided into its two native grandchildren, assigned and independently accepted as separate GitHub issues. Preserve all original requirements and integration acceptance when the group closes. No direct code patch, new research protocol or neural training is authorized by this grouping.

## Completion
Both grandchildren must be integrated with compatible records and literal acceptance results, followed by the parent's eventual end-to-end checks. Assign workers to grandchildren rather than to this group.
"""
    owned = "\n".join(f"{i+1}. {sentence}" for i, sentence in enumerate(d["clauses"]))
    shared = shared_sections(contract["shared"], owned, d["title"])
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
{contract['acceptance']}

## Agent execution and handoff
**Original EGM review:** Use Google EGM pinned at `b3a35956759bf7f024af2ff061b2e0b44b438e4c`. A fresh Goldfish reviews this Elephant implementation (or a cohesive batch of at most three leaves); blockers and majors are resolved or contested with evidence. Without independent review, record `EGM_PENDING` for the integrator. A same-context self-review is not independent.

**Original PR turn-in:** Push and read back the branch SHA, comment on the issue and lane PR, and add the actual GitHub child issue number to the PR Development closing links. The parent remains open until descendants and original acceptance are integrated.

Agent fit: {reasoning}. Read root README.md and AGENTS.md once, this exact child and its direct dependency receipts, then only the assigned source paths. The original technical specifications stay complete. If this work still exceeds one coherent bounded patch, subdivide **this child again** before cutting requirements. Coordinate shared paths through the lane's one writer, maintain source-gold and neural/optimizer custody, use small software checks of already-specified behavior, and record the exact child issue, changed paths, tests, branch/head SHA, and next unblocked child. Do not run the actual student or merge main from this issue.
"""
