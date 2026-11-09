# BAMF-0.2 execution workstack

The owner selected one atlas-native architecture. Read the [architecture contract](../../architecture/BAMF_0_2.md), then execute one ready leaf at a time. The full issue repeats the relevant contracts so a fresh worker can continue without this conversation.

## Lossless recursive decomposition | 27 October 2026

The 43 original owner issues retain their **entire** engineering specifications and acceptance requirements. To lower the cost and reasoning load of execution, recursively divide large owners into smaller, independently deliverable native GitHub sub-issues, not weaker requirements. Agents take the **deepest ready implementable child**; group/parent issues remain integration and acceptance contracts. If a child is still too broad, divide it again. Every child specifies inputs, output, dependencies, owned files, behavior and completion, without requiring the whole program to be re-reasoned. Do not add new research experiments or live neural-run gates during planning.

The first full hierarchy is [A09 #360](https://github.com/Entif-AI/Bilqis-MLX/issues/360), including its A09.1 grandchildren. See [child index](children/README.md) and [machine-readable tree](children/index.json). `workstack.json` retains all 43 original owners and records the direct children of a decomposed owner; the approved Blueprint and SPEC remain the normative design.

<!-- BAMF02:ALL-LANES-GROOMED-20261027 -->
## Current native issue-tree routing | 27 October 2026

43 original complete owner contracts across three lanes; 172 native recursively linked child nodes (A 52, B 58, C 62). Assign an agent **only to a deepest ready implementable child**, never to an intermediate group or an original integration parent. If a child remains too large, recursively subdivide it without dropping source clauses, technical details or original acceptance. See [full native child registry](children/README.md), [machine-readable tree](children/registry.json) and updated [complete parent book](ISSUE_BOOK.md).

First ready child candidates: A [A01.1 #396](https://github.com/Entif-AI/Bilqis-MLX/issues/396), B [B01.1a #434](https://github.com/Entif-AI/Bilqis-MLX/issues/434), C [C01.1 #486](https://github.com/Entif-AI/Bilqis-MLX/issues/486). Readiness still depends on actual upstream branch/receipt state and existing one-writer rules.

## Parallel start

- Lane A: [Semantics and curricula](https://github.com/Entif-AI/Bilqis-MLX/issues/342), branch `codex/bamf02-a-semantics`, start [A01 #345](https://github.com/Entif-AI/Bilqis-MLX/issues/345). [Launch instructions](EXECUTION_LANE_A.md).
- Lane B: [Neural architecture](https://github.com/Entif-AI/Bilqis-MLX/issues/343), branch `codex/bamf02-b-neural`, start [B01 #346](https://github.com/Entif-AI/Bilqis-MLX/issues/346). [Launch instructions](EXECUTION_LANE_B.md).
- Lane C: [Training and integration](https://github.com/Entif-AI/Bilqis-MLX/issues/344), branch `codex/bamf02-c-runtime`, start [C01 #347](https://github.com/Entif-AI/Bilqis-MLX/issues/347). [Launch instructions](EXECUTION_LANE_C.md).

The common integration trunk is `codex/bamf-unified-base-20261028`. It is a living
reviewed branch: each independently owned issue may use its own branch/worktree;
each final integration candidate consumes current unified before the review/merge
gate. Multiple issue PRs per lane may coexist. Do not merge `main` or a sibling
lane directly. Lane C still owns shared trainer/CLI/runtime surfaces; this
ownership rule prevents races but does not make Lane C the integration trunk.
CPU source/fixture work
proceeds concurrently. MLX evaluation and neural updates use one serialized M3
Ultra lane. The first durable student gate is [C16](issues/C16.md); full delivery
is [C15](issues/C15.md).

## Latest legacy trainer source

Any issue that needs to adapt behavior from the latest legacy trainer uses the
preserved Factory replay at
`/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`,
not the Prometheus training run. See
[`LEGACY_TRAINER_AUTHORITY.md`](LEGACY_TRAINER_AUTHORITY.md) and run
`python3 -B scripts/check_legacy_trainer_authority.py --live` before relying on
legacy behavior in implementation or review. Prometheus remains historical lineage
evidence only.

## Flow control and parked PR discipline

**Compaction recovery:** Resume the same issue and preserved branch/worktree when
context compacts. An `ACTIVE` lane entry, checkpoint, previous worker label, or
historical worktree is not a live exclusive lease. Inspect actual Git status,
remote head and any concurrently writing process before declaring contention.
No new permission or issue re-assignment is necessary when the same logical
worker continues on unchanged state. If an actual competing writer exists,
coordinate the shared path or use an independent issue branch; do not force-push
or mutate the competitor's uncommitted work. Every planned handoff/compaction
should carry JSON from `python3 -B scripts/bamf/writer_handoff.py emit --issue
<ISSUE> --epoch <STABLE-EPOCH> --worktree <WORKTREE>`. The successor saves that
JSON and runs `python3 -B scripts/bamf/writer_handoff.py verify --payload
<HANDOFF-JSON-FILE> --worktree <WORKTREE>`. `CONTINUATION_MATCH` removes the
false issue-ownership hold; an actual branch/remote/dirty-state mismatch must be
reconciled. This verifies continuity, not exclusive distributed ownership.
See `AGENTS.md` and ADR-128.

### Reuse passing verification until invalidated

Passing verification is durable evidence, not a ritual to repeat at every PR or
agent boundary. Before rerunning an expensive suite, compare the candidate against
the exact head that last passed it. Reuse that receipt when no intervening change
touches the suite's production inputs, tests/fixtures, generators, dependencies,
runtime configuration, or harness. Record the tested head and comparison range as
`TEST_EVIDENCE_REUSED`. Governance/docs/flow-control/handoff-only changes should
run only their cheap structural checks and must not trigger semantic, custody,
neural, or exhaustive profile suites. A later merge invalidates a prior run only
when the merged delta intersects the suite's dependency surface.

Hosted `quality.yml` follows this rule: it classifies the PR/push diff first and
skips broad semantic/custody test suites when no expensive-test dependency surface
changed. Manual dispatch remains an explicit request for fresh verification.

### Decompose freely; gate only net-new scope

Issue/branch creation is not the waste target. A strict subset of already-required
parent acceptance may be decomposed into its own issue, branch/worktree, and PR
whenever that improves parallelism, faster turn-in/failure, review isolation, or
earlier information. Record the parent and inherited clauses; do not add acceptance.

Apply the root `AGENTS.md` gate only to obligations that do **not** trace to existing
required scope. Those expansions must be justified as needed for current delivery,
parked, or dropped. If a child grows past 3 commits, 3 files, or 250 net changed
lines, audit traceability: split again if the work is still inherited; gate only
the untraceable delta. EGM is downstream of scope authority, never its source.

Expensive diagnostics obey the same spend discipline. Do not repeatedly rebuild a
live Factory/model/bundle stack in separate ad hoc Python invocations while varying
one seed or hypothesis. Reuse identical results, parameterize repeated experiments
inside one process, and after two failed full-cost witness attempts switch to a
smaller staged/profiled proof before another end-to-end run.

The lane is not a conveyor belt that must keep every open PR warm. The normal limit
is **six `ACTIVE` implementation leaves per lane** under the 2026-11-04 owner
amendment. Prefer finishing near-to-merge leaves while allowing independent
agents to work on other dependency-ready leaves. `READY`, `WAITING`,
`BLOCKED` and `TURNED_IN` are not implementation WIP.

Machine-readable policy and lane state live in [`flow-control/`](flow-control/).
Before branch mutation:

1. run `python3 -B scripts/check_bamf_flow_control.py`;
2. confirm the target leaf is represented in the correct lane file;
3. if it is parked, verify its recorded resume trigger has actually occurred;
4. if parked, change it to `ACTIVE` after the trigger; if already `ACTIVE`,
   a compacted continuation retains that state without another issue claim;
5. keep the lane at or below six active leaves unless the lane file contains
   an explicit exception with reason, authority and expiry.

A `WAITING` or `BLOCKED` PR is frozen. Do not merge-forward it, rebase it, rerun
full exact-head validation, request fresh review or otherwise churn it merely
because unified moved. When its real trigger fires, activate it and perform the one
refresh/revalidation required by its contract. This keeps external review and
dependency queues from masquerading as implementation throughput.

### Integration inventory and DRAIN mode

ADR-126 adds a separate integration-inventory gate. ACTIVE WIP remains governed by
ADR-124, but open BAMF implementation PRs are now capped at **twelve total**,
up from three, by explicit owner direction on 2026-11-04. Multiple independent
integration candidates may coexist in any lane; the former one-PR-per-lane
restriction is retired. The unified integration PR into `main` does not consume
an implementation slot.

A completed leaf can remain on a durable branch. Before PR creation, inspect
live PR inventory using a functioning GitHub interface; the optional command
`python3 -B scripts/check_bamf_flow_control.py --live` is advisory. If its
network/TLS/authentication path is unavailable or the ledger is briefly stale,
record the discrepancy and continue with independent issue/head, proof and
conflict checks rather than blocking all agents. Hosted CI
validates static policy and tests only so independently opened PRs cannot make
otherwise valid CI runs fail because of ledger update timing.

When open implementation inventory is above the ceiling, the program is in
**DRAIN** mode. Avoid additional implementation PRs without an explicit owner
exception. The existing implementation
PRs present at ADR-126 adoption are grandfathered only for this drain epoch.

**Drain through EGM, repair and merge, not summary closure.** A PR awaiting required
pinned EGM or other merge-readiness evidence remains an actionable integration
candidate. EGM pending is not a reason to close it. Keep existing candidates open
while their authorized review/repair/merge path is active. Do not close PRs solely
to lower the inventory count or make the checker report NORMAL.

The first attempt to close all 17 ledger-declared WAITING PRs was erroneous and was
reversed. All 17 were reopened at their original exact heads. The live
implementation inventory is again the 19 candidates present at adoption. The
one-time grandfather list is limited to those existing PRs; reopening or creating
other PRs does not inherit grandfather status.

Close a candidate only when it is genuinely superseded, duplicate, no longer
selected for integration, materially blocked with no active EGM/merge path, or
explicitly directed by the project owner. Preserve branch, exact head, owning
issue and resume trigger before closure.

A non-grandfathered open `WAITING` or `BLOCKED` PR requires an explicit
`open_pr_exception` with reason, authority and expiry.


## Artifacts

- `workstack.json`: exact issue IDs, dependencies, paths and acceptance prescriptions.
- `flow-control/`: current per-lane ACTIVE/READY/WAITING/BLOCKED/TURNED_IN state plus resume triggers and WIP policy.
- `waves.json`: dependency-ready sets, not a requirement to serialize independent work.
- `issues/`: complete standalone implementation specifications.
- `ISSUE_BOOK.md`: searchable concatenation of those specifications.
- `../../evidence/bamf/0.2-planning/`: publication/readback and EGM records.

## Turn-in

Keep one mutating writer per branch/shared path, **not per lane or issue across
compactions**. At final turn-in, sync the current unified trunk into the issue
branch and record the consumed unified SHA. Push coherent commits, record exact proof
on the issue, then open a PR from the issue branch into
`codex/bamf-unified-base-20261028` and add the issue closing keyword to the PR
Development section. Human sign-off is required before that PR merges. Main merge
and a durable live student launch remain operator actions. Context is a cache; the
issue, committed source and receipts carry continuation.
