"""Bind every BAMF-0.2 work packet to its long-lived lane branch.

The unified BAMF branch is a living integration trunk. Each issue starts by
merging the current unified trunk into its lane branch and finishes by opening a
human-reviewed lane -> unified pull request. Direct main or sibling-lane merges
are not part of the issue lifecycle.

Modes:
  python3 -B scripts/bamf02_bind_lane_branches.py --local
  python3 -B scripts/bamf02_bind_lane_branches.py --publish
  python3 -B scripts/bamf02_bind_lane_branches.py --verify

`--publish` is intentionally preservation-gated: for the 200 owner/child issue
mirrors, the live GitHub body must equal either the current checked-in HEAD body
or the newly generated local body. Unexpected live drift aborts the batch rather
than being overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "docs/tasks/bamf-0.2"
ISSUES = TASKS / "issues"
CHILDREN = TASKS / "children"
REPO = "Entif-AI/Bilqis-MLX"
INTEGRATION = "codex/bamf-unified-base-20261028"
BRANCHES = {
    "A": "codex/bamf02-a-semantics",
    "B": "codex/bamf02-b-neural",
    "C": "codex/bamf02-c-runtime",
}
OLD_BASELINE = (
    "Baseline replay `d21797e72365bf93ea7cad3a4ef9020ec9817f23`; "
    "SKOS merge `175cdf6778b4eeaea23a5bd36ad7dc6664df3ae8`. "
    "Re-read current branch equivalents before patching. Listed new files are "
    "prescribed additions, not claims of existing implementation."
)
MARKER = "<!-- BAMF02:LANE-BRANCH-LIFECYCLE:{lane} -->"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def gh(method: str, path: str, payload: dict | None = None):
    cmd = ["gh", "api", "-X", method, path]
    if payload is not None:
        cmd.extend(["--input", "-"])
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        input=json.dumps(payload) if payload is not None else None,
        text=True,
        capture_output=True,
    )
    if proc.returncode:
        raise RuntimeError(f"GitHub {method} {path}: {proc.stderr[:1200]}")
    return json.loads(proc.stdout) if proc.stdout else None


def lifecycle_block(lane: str) -> str:
    branch = BRANCHES[lane]
    return f"""{MARKER.format(lane=lane)}
## Lane branch and integration lifecycle

**Working branch:** `{branch}`. **Reviewed integration trunk:** `{INTEGRATION}`.

Before beginning implementation on this issue, fetch `origin` and, while on
`{branch}`, merge the current `origin/{INTEGRATION}` into the lane branch. If the
lane already equals the current unified head, record that exact unified SHA and
proceed without manufacturing a no-op merge. Resolve any real conflicts and run
the smallest affected verification before issue-owned edits. Record the consumed
unified SHA in the issue receipt. Do **not** merge `main` or a sibling lane branch
directly; reviewed cross-lane work arrives through the unified trunk.

After this issue's owned acceptance is satisfied, commit and push `{branch}` and
open a pull request from `{branch}` into `{INTEGRATION}` for human review and
sign-off. This issue does not authorize self-merging that PR. After accepted work
lands on unified, the next issue in the lane repeats the sync-in step. A
non-implementing group/integration parent does not create a bookkeeping code PR;
its implementing descendants follow this lifecycle and the parent closes only at
its existing integration gate.
"""


def transformed_body(body: str, lane: str) -> str:
    marker = MARKER.format(lane=lane)
    if marker not in body:
        anchor = "\n## "
        pos = body.find(anchor)
        if pos < 0:
            raise RuntimeError(f"lane {lane}: cannot locate first section heading")
        body = body[:pos] + "\n\n" + lifecycle_block(lane).rstrip() + body[pos:]
    historical = (
        "Historical baseline provenance: replay "
        "`d21797e72365bf93ea7cad3a4ef9020ec9817f23`; SKOS merge "
        "`175cdf6778b4eeaea23a5bd36ad7dc6664df3ae8`. The operational baseline is "
        f"the current `{INTEGRATION}` synchronized into `{BRANCHES[lane]}` under "
        "the lane lifecycle above; do not reconstruct the working baseline from "
        "`main` or those historical refs. Listed new files are prescribed "
        "additions, not claims of existing implementation."
    )
    return body.replace(OLD_BASELINE, historical)


def spec_paths() -> list[Path]:
    return sorted(ISSUES.glob("[ABC]*.md")) + sorted(
        p for p in CHILDREN.glob("[ABC]*.md") if p.name != "README.md"
    )


def owner_sha_map() -> dict[str, str]:
    return {
        p.stem: sha(p.read_text(encoding="utf-8"))
        for p in sorted(ISSUES.glob("[ABC]*.md"))
    }


def refresh_hashes() -> None:
    owner_sha = owner_sha_map()
    workstack_path = TASKS / "workstack.json"
    workstack = json.loads(workstack_path.read_text(encoding="utf-8"))
    for item in workstack["items"]:
        item["body_sha256"] = owner_sha[item["key"]]
    workstack_path.write_text(
        json.dumps(workstack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    index_path = CHILDREN / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for entry in index["entries"]:
        key = entry["key"]
        entry["body_sha256"] = sha((CHILDREN / f"{key}.md").read_text(encoding="utf-8"))
        entry["source_parent_sha256"] = owner_sha[key.split(".", 1)[0]]
    index_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    registry_path = CHILDREN / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for entry in registry["entries"]:
        key = entry["key"]
        entry["body_sha256"] = sha((CHILDREN / f"{key}.md").read_text(encoding="utf-8"))
        entry["source_parent_sha256"] = owner_sha[key.split(".", 1)[0]]
    registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def rebuild_issue_book() -> None:
    workstack = json.loads((TASKS / "workstack.json").read_text(encoding="utf-8"))
    note = (
        "<!-- BAMF02:LIVE-DECOMPOSITION-DIRECTIVE -->\n"
        "> Active implementation starts at the deepest dependency-ready native GitHub child, "
        "not the original broad owner. All 43 original specifications, engineering "
        "constraints and acceptance contracts remain intact. The exact complete "
        "child tree is `children/registry.json`. Lane branch synchronization and "
        "reviewed return-to-unified rules are embedded in every checked-in issue mirror.\n"
    )
    texts = [
        (ISSUES / f"{item['key']}.md").read_text(encoding="utf-8").rstrip("\n")
        for item in workstack["items"]
    ]
    (TASKS / "ISSUE_BOOK.md").write_text(
        "# BAMF-0.2 complete implementation issue book\n\n"
        + note
        + "\n"
        + "\n\n---\n\n".join(texts)
        + "\n",
        encoding="utf-8",
    )


def local_update() -> None:
    paths = spec_paths()
    if len(paths) != 200:
        raise RuntimeError(f"expected 200 owner/child specs, found {len(paths)}")
    for path in paths:
        lane = path.stem[0]
        before = path.read_text(encoding="utf-8")
        after = transformed_body(before, lane)
        if after != before:
            path.write_text(after, encoding="utf-8")
    refresh_hashes()
    rebuild_issue_book()
    print(f"UPDATED: {len(paths)} BAMF owner/child specs; branch/hash metadata refreshed")


def checked_in_body(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel}"], cwd=ROOT, text=True, capture_output=True
    )
    if proc.returncode:
        raise RuntimeError(f"cannot read checked-in baseline for {rel}: {proc.stderr[:500]}")
    return proc.stdout


def publish_specs() -> None:
    issue_map = json.loads((TASKS / "issue-map.json").read_text(encoding="utf-8"))
    changed = 0
    for path in spec_paths():
        key = path.stem
        number = int(issue_map[key])
        desired = path.read_text(encoding="utf-8")
        old = checked_in_body(path)
        live = gh("GET", f"repos/{REPO}/issues/{number}")
        current = live.get("body") or ""
        if current == desired:
            continue
        if current != old:
            raise RuntimeError(
                f"{key} #{number}: unexpected live drift; refuse overwrite"
            )
        gh("PATCH", f"repos/{REPO}/issues/{number}", {"body": desired})
        readback = gh("GET", f"repos/{REPO}/issues/{number}")
        if (readback.get("body") or "") != desired:
            raise RuntimeError(f"{key} #{number}: live readback mismatch")
        changed += 1
        print(f"UPDATED {key} #{number}", flush=True)
    print(f"PUBLISHED: {changed} owner/child issue bodies updated")


def root_lane_amendment(issue: int, lane: str | None) -> str:
    if lane is None:
        return f"""<!-- BAMF02:BRANCH-LIFECYCLE:ROOT -->
## BAMF lane integration lifecycle | 28 October 2026

`{INTEGRATION}` is the living reviewed integration trunk for BAMF-0.2. Lane A
works on `{BRANCHES['A']}`, Lane B on `{BRANCHES['B']}`, and Lane C on
`{BRANCHES['C']}`. Each implementing issue synchronizes the current unified trunk
into its lane before issue-owned edits. Completed issue work returns by a lane ->
unified pull request and requires human sign-off; no issue authorizes self-merge.
Lanes do not merge `main` or sibling lanes directly. Accepted cross-lane work is
shared by landing on unified and being consumed at the next issue boundary.
"""
    return f"""<!-- BAMF02:BRANCH-LIFECYCLE:LANE-{lane} -->
## Lane {lane} branch lifecycle | 28 October 2026

Lane {lane} works on `{BRANCHES[lane]}` and integrates through
`{INTEGRATION}`. Before each implementing issue begins, fetch `origin` and merge
the current `origin/{INTEGRATION}` into the lane branch, recording the unified
SHA consumed. Do not merge `main` or another lane directly. After the issue's
owned acceptance passes, push the lane branch and open a PR from
`{BRANCHES[lane]}` into `{INTEGRATION}` for human review/sign-off. The issue does
not authorize self-merging the PR. The next issue repeats the sync-in step after
accepted unified changes land.
"""


def publish_root_lanes() -> None:
    for number, lane in ((341, None), (342, "A"), (343, "B"), (344, "C")):
        live = gh("GET", f"repos/{REPO}/issues/{number}")
        body = live.get("body") or ""
        marker = (
            "<!-- BAMF02:BRANCH-LIFECYCLE:ROOT -->"
            if lane is None
            else f"<!-- BAMF02:BRANCH-LIFECYCLE:LANE-{lane} -->"
        )
        amendment = root_lane_amendment(number, lane).rstrip()
        if marker in body:
            print(f"SKIP #{number}: branch lifecycle already present")
            continue
        desired = body.rstrip() + "\n\n" + amendment + "\n"
        gh("PATCH", f"repos/{REPO}/issues/{number}", {"body": desired})
        readback = gh("GET", f"repos/{REPO}/issues/{number}")
        if (readback.get("body") or "") != desired:
            raise RuntimeError(f"#{number}: branch lifecycle readback mismatch")
        print(f"UPDATED ROOT/LANE #{number}")


def verify_local() -> None:
    paths = spec_paths()
    if len(paths) != 200:
        raise RuntimeError(f"expected 200 owner/child specs, found {len(paths)}")
    failures: list[str] = []
    for path in paths:
        lane = path.stem[0]
        text = path.read_text(encoding="utf-8")
        marker = MARKER.format(lane=lane)
        if marker not in text:
            failures.append(f"{path}: missing lifecycle marker")
        if f"`{BRANCHES[lane]}`" not in text or f"`{INTEGRATION}`" not in text:
            failures.append(f"{path}: missing exact lane/integration branch")
        if OLD_BASELINE in text:
            failures.append(f"{path}: stale operational baseline")
    if failures:
        raise RuntimeError("\n".join(failures[:40]))
    print("PASS: all 200 BAMF owner/child specs bind exact lane branches and unified lifecycle")


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local", action="store_true")
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.local:
        local_update()
    elif args.publish:
        publish_specs()
        publish_root_lanes()
    else:
        verify_local()


if __name__ == "__main__":
    main()
