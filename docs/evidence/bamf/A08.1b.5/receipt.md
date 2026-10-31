# A08.1b.5 Factory family integration candidate

- Issue: #557; parent A08.1b #418; Lane A
- Replacement PR: #657; supersedes historical stacked PR #642
- Consumed unified: `4bac5323701d198a6782b424cd5e24633b337b56`
- Feature/proof head before this receipt-only refresh: `f59a105a7f8c96e3eb582121735ccf2d15b7307b`
- Learning state: `LEARNING_UNVERIFIED`
- Independent review outcome is recorded on the PR review/comment surface and is not asserted by this static candidate receipt.

## Owned integration

The current-base replacement keeps `skos_curriculum.registry` behavior-only: it
binds a constructive family to an already-existing `CapabilityDefinition`,
`ConstructionProgram`, and exact source adapter/oracle. It does not derive a
capability ID from semantic ID, family, source row, operator, root, or grade;
A08.2 retains stable capability/release identity. Missing identity bindings remain
`IMPLEMENTATION_UNCOVERED`, preserving the complete A08.1a denominator and
separate source-held rows. A successful binding remains `LEARNING_UNVERIFIED`.

The executable Factory boundary revalidates current A08 authority before
execution. Boolean capability bindings cannot execute numeric or foreign Boolean
operators. World-family programs execute against the exact supplied source
registry and released adapter identity.

Source-backed positive-identity lessons retain the A03/A13 bridge: exact tracked
CSV rows are verified against the canonical extraction frontier, preserve the A01
`(domain, table, key)` identity and row/file hashes, and are checked against the
pinned A01 concept before grants are issued. A13 frame/member grants are merged
into the current `SourceFrontier`; revoked contrast authority cannot be silently
resurrected. Source-row evidence stays atomic, source-local, and non-admitting.

The replacement deliberately does **not** reintroduce the historical
`bilqis_mlx/errors/catalog.py` edits that caused the first current-base hosted
structure failure. Newly introduced family/source-row failures use the existing
local typed error pathways instead.

## Current-base proof

The code at `f59a105a7f8c96e3eb582121735ccf2d15b7307b` is the current-base feature
state consumed by this receipt refresh. It differs from the preceding feature
proof only by merging unified's shared Semantic ABI workflow repair; no A08 feature
code changed in that merge.

- Focused A08/source-authority union: **24 passed / 6 explicit pinned-A01 skips / 0 failures**.
- The six skips are tests that require the real pinned A01 artifact through
  `BILQIS_A01_ATLAS_BUNDLE`; no fixture or substitute authority was introduced.
- Operator-contract ratchet: **0 new debt**.
- Development structure: **0 violations**.
- Changed-file hygiene: **0 new findings**.
- Factory architecture: **PASS**.
- Governance integrity: **0 violations**.
- Docs and `git diff --check`: **PASS**.
- Hosted full sharded semantic-profile run `#41240739990`: **SUCCESS** on all
  eight semantic shards plus portable-core/final portable jobs.

## Acceptance boundary

This leaf claims only the A08.1b.5 family/source-authority execution seam. It does
not claim capability admission, A08.2 identity allocation, learner/optimizer or
checkpoint mutation, graph mutation, parent A08 closure, or neural training.
Parent #418/#358 and downstream A08.2 remain separate acceptance surfaces.
