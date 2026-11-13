# Factory ticket navigation: issue pages are the runner

**Status:** execution-navigation contract for issue #150.
**Original:** 2026-10-23; **revised:** 2026-10-24.
**Scope:** page-local navigation only. Leaf invariants, frozen issue bodies and
spec hashes, read/write allowlists, compatibility contracts, and neural
authority remain unchanged.

## Decision

Issue #150 does not need a separate orchestration runner during ordinary leaf
execution. The GitHub issue pages and their local gates provide the navigation:

- one leaf issue is one page;
- the current issue number is the durable bookmark;
- each page names its direct prerequisites and one next page;
- Git commits and GitHub receipts are the durable implementation record;
- model context is a cache, not execution authority.

The dependency manifest remains useful for grooming and architecture maintenance.
An ordinary leaf executor does not hydrate it, scan every receipt, or reconstruct
the global ready set.

## Why this contract exists

The micro-specs bound implementation, but a global bootstrap, manifest hydration,
receipt sweep, and readiness reconstruction would still load the entire 77-leaf
control plane before a small page could execute. That defeats the point of the
decomposition. The issue page is the navigation surface; the next page supplies
the next local context.

## Fresh-session bootstrap

Each fresh execution session reads the root `README.md` and `AGENTS.md` once
before source mutation, confirms its branch/worktree and writer state, and reads
the broad authorities required for the current bounded task. It does not repeat
that bootstrap for every leaf.

After bootstrap, ordinary execution reads only:

1. the bookmarked leaf issue and its current page gate;
2. later amendments on that same issue;
3. direct prerequisites named by the gate, using their latest local state;
4. the leaf spec and its declared read/write files.

Do not read parent issue #150, hydrate the full workstack manifest, inspect
unrelated leaf specs, or sweep all execution receipts during ordinary leaf work.

## Local navigation algorithm

On the bookmarked page:

1. `FACTORY_LEAF_DONE` is terminal; follow `next_page` without rerunning it.
2. `BLOCKED_SPEC_GAP` is terminal unless a newer same-page
   `FACTORY_SPEC_AMENDMENT_V1` says `reopen: true`.
3. `FACTORY_DEPENDENCY_BLOCKED` is a staleable observation. Recheck only the
   named direct prerequisites; a same-page amendment is not required just to
   reevaluate dependency state.
4. If a direct prerequisite is itself dependency-blocked, follow only that
   prerequisite's own gate and named dependencies. An unresolved prerequisite
   keeps the current page blocked; do not duplicate an identical blocker receipt.
5. Execute only when the direct prerequisites satisfy the live gate, and only
   under the frozen leaf contract plus any later same-page reopening amendment.
6. After completion or an unresolved blocker, follow the page's explicit
   `next_page`.

Issue bodies remain unchanged so frozen body hashes stay valid. Amendments are
append-only issue comments. A reopening amendment corrects only the page where
it appears and does not rewrite the underlying frozen spec.

## Warm sessions and cold page boundaries

Keep a healthy model session warm while turning to a cold issue page. Read the
new page's local authority and do not rely on prior-page details unless the new
page names their commit or receipt. Retaining a healthy session is a cache
efficiency choice, not a transfer of authority between leaves. Do not start a
new expensive session solely to simulate isolation; start fresh only after real
context failure or compaction pressure.

The current issue number belongs in the active handoff or issue checkpoint. Do
not hard-code a transient current-page bookmark into durable architecture prose.

## Grooming acceptance test

A leaf is sufficiently groomed when an executor given the current issue page can:

1. determine whether the page is complete, gap-blocked, dependency-blocked, or executable;
2. identify exactly which direct prerequisite pages to inspect;
3. execute within the declared read/write and proof surfaces without global search;
4. leave a remote-verified commit and a durable local issue receipt;
5. follow exactly one declared next page.

If execution requires reloading the epic, hydrating every manifest entry,
searching all receipts, or rebuilding the global ready set, the page contract is
missing a navigation fact.

## Non-goals

This navigation contract does not change factory semantics, leaf invariants,
design-time dependency validation, issue-body hashes, or the human-only
optimizer boundary. The workstack remains available for grooming and planned
maintenance; it is not ordinary leaf-execution input.
