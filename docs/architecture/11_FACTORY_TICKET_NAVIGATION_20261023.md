# Factory ticket navigation: the tickets are the runner

**Status:** controlling user-directed execution amendment for issue #150.  
**Date:** 2026-10-23.  
**Scope:** execution navigation only. Leaf invariants, frozen issue bodies,
spec hashes, read/write allowlists, compatibility contracts, and neural authority
remain unchanged.

## Decision

Issue #150 does not use a separate orchestration runner.

The durable documentation and process gates are the runner:

- one leaf issue is one page;
- the current issue number is the bookmark;
- each page names only its direct prerequisite page(s);
- each page has one explicit next page;
- Git commits and issue receipts are the durable execution record.

This is deliberately analogous to a choose-your-own-adventure book. The book is
written before execution. The reader does not regenerate pages, reconstruct the
table of contents, or reread the whole book after a break. The reader reopens
the bookmarked page and follows the local instruction at the bottom.

## Why this amendment exists

The original closed-book design decomposed implementation into small leaves but
still told Codex to bootstrap broad authority, hydrate the global manifest,
fetch receipts across the workstack, and recompute readiness. That allowed a
single supposedly bounded run to pull the 77-leaf control plane into scarce
model context before useful leaf execution.

That violates the purpose of the decomposition. Small implementation units are
not enough if navigation itself requires global model context.

## Durable page contract

Every #150 leaf issue receives one additive `FACTORY_PAGE_GATE_V1` comment.
Issue bodies are not rewritten, so the existing frozen body hashes remain
valid.

Each page gate contains:

- current `SPEC-####` and issue number;
- direct prerequisite spec/issue pairs only;
- one explicit `next_page`;
- local terminal-receipt interpretation;
- the dependency-blocked receipt shape;
- the quota/session-reset bookmark rule;
- the global-hydration prohibitions.

The frozen lexical `SPEC-####` sequence was verified once during grooming to
be a topological ordering. That verification belongs to design/grooming, not to
ordinary executor context.

## Local navigation algorithm

Given one bookmarked issue:

1. If the page already has a terminal receipt, follow `next_page`.
2. Otherwise inspect only the direct prerequisite issues named by the gate.
3. If every prerequisite ends in `FACTORY_LEAF_DONE`, execute the page.
4. If any prerequisite ends in `BLOCKED_SPEC_GAP` or
   `FACTORY_DEPENDENCY_BLOCKED`, post `FACTORY_DEPENDENCY_BLOCKED` on this
   page and follow `next_page`.
5. If a direct prerequisite has no terminal receipt, the bookmark is wrong.
   Open only that missing prerequisite page and follow its gate.
6. After this page ends in `FACTORY_LEAF_DONE` or `BLOCKED_SPEC_GAP`, follow
   `next_page`.

No step requires a global ready set.

## Correcting an under-groomed page

A blocked page may later receive a `FACTORY_SPEC_AMENDMENT_V1` comment. This is
the durable errata mechanism for the book.

If the amendment is newer than the page's latest `BLOCKED_SPEC_GAP` or
`FACTORY_DEPENDENCY_BLOCKED` and says `reopen: true`, that block is
superseded for the affected page only. The executor combines the frozen
issue/spec with the amendment and retries that page. A `FACTORY_LEAF_DONE`
receipt remains terminal unless a separately authorized migration explicitly
changes the completed contract.

This mechanism avoids rewriting frozen issue bodies and avoids global
re-grooming. The executor never searches for amendments elsewhere.

## Context and quota boundary

The executor never owns global orchestration memory.

After a context loss or five-hour quota reset, the continuation state is the
bookmarked issue number. Reopening that issue supplies the navigation gate. The
executor does not reload the parent epic, manifest, all receipts, or unrelated
leaf specs.

The prior page's model context is disposable. Durable state lives in Git and
GitHub.

## Grooming acceptance test

A page is not sufficiently groomed unless an amnesiac Codex instance can be
given only that issue and:

1. determine whether it is already terminal;
2. identify exactly which direct prerequisites to inspect;
3. determine whether it may execute without a global search;
4. know the exact local spec/read/write/proof contract;
5. leave a durable terminal receipt;
6. know exactly which issue to open next.

If the executor needs a sidecar coordinator, an outer agent, a local harness, a
manifest hydration, a receipt sweep, or broad architecture research to answer
those questions, the ticket is under-groomed.

## Non-goals

This amendment does not:

- change factory semantics;
- change any leaf's implementation invariant;
- remove design-time DAG validation;
- invalidate the frozen workstack as a planning/index artifact;
- authorize issue-body rewrites;
- authorize neural training.

The manifest may still validate the corpus during grooming and architecture
maintenance. It is not ordinary leaf-execution input.
