# BAMF-0.2 execution workstack

The owner selected one atlas-native architecture. Read the [architecture contract](../../architecture/BAMF_0_2.md), then execute one ready leaf at a time. The full issue repeats the relevant contracts so a fresh worker can continue without this conversation.

## Lossless recursive decomposition | 27 October 2026

The 43 original owner issues retain their **entire** engineering specifications and acceptance requirements. To lower the cost and reasoning load of execution, recursively divide large owners into smaller, independently deliverable native GitHub sub-issues, not weaker requirements. Agents take the **deepest ready implementable child**; group/parent issues remain integration and acceptance contracts. If a child is still too broad, divide it again. Every child specifies inputs, output, dependencies, owned files, behavior and completion, without requiring the whole program to be re-reasoned. Do not add new research experiments or live neural-run gates during planning.

The first full hierarchy is [A09 #360](https://github.com/Entif-AI/Bilqis-MLX/issues/360), including its A09.1 grandchildren. See [child index](children/README.md) and [machine-readable tree](children/index.json). `workstack.json` retains all 43 original owners and records the direct children of a decomposed owner; the approved Blueprint and SPEC remain the normative design.

<!-- BAMF02:ALL-LANES-GROOMED-20261027 -->
## Current native issue-tree routing | 27 October 2026

43 original complete owner contracts across three lanes; 157 native recursively linked child nodes (A 44, B 53, C 60). Assign an agent **only to a deepest ready implementable child**, never to an intermediate group or an original integration parent. If a child remains too large, recursively subdivide it without dropping source clauses, technical details or original acceptance. See [full native child registry](children/README.md), [machine-readable tree](children/registry.json) and updated [complete parent book](ISSUE_BOOK.md).

First ready child candidates: A [A01.1 #396](https://github.com/Entif-AI/Bilqis-MLX/issues/396), B [B01.1a #434](https://github.com/Entif-AI/Bilqis-MLX/issues/434), C [C01.1 #486](https://github.com/Entif-AI/Bilqis-MLX/issues/486). Readiness still depends on actual upstream branch/receipt state and existing one-writer rules.

## Parallel start

- Lane A: [Semantics and curricula](https://github.com/Entif-AI/Bilqis-MLX/issues/342), branch `codex/bamf02-a-semantics`, start [A01 #345](https://github.com/Entif-AI/Bilqis-MLX/issues/345). [Launch instructions](EXECUTION_LANE_A.md).
- Lane B: [Neural architecture](https://github.com/Entif-AI/Bilqis-MLX/issues/343), branch `codex/bamf02-b-neural`, start [B01 #346](https://github.com/Entif-AI/Bilqis-MLX/issues/346). [Launch instructions](EXECUTION_LANE_B.md).
- Lane C: [Training and integration](https://github.com/Entif-AI/Bilqis-MLX/issues/344), branch `codex/bamf02-c-runtime`, start [C01 #347](https://github.com/Entif-AI/Bilqis-MLX/issues/347). [Launch instructions](EXECUTION_LANE_C.md).

The common integration trunk is `codex/bamf-unified-base-20261028`. It is a living
reviewed branch: every implementing issue first merges the current unified trunk
into its assigned lane, and every completed issue returns by PR from that lane
into unified for human sign-off. Do not merge `main` or a sibling lane directly.
Lane C still owns shared trainer/CLI/runtime surfaces; this ownership rule prevents
races but does not make Lane C the integration trunk. CPU source/fixture work
proceeds concurrently. MLX evaluation and neural updates use one serialized M3
Ultra lane. The first durable student gate is [C16](issues/C16.md); full delivery
is [C15](issues/C15.md).

## Flow control and parked PR discipline

The lane is not a conveyor belt that must keep every open PR warm. The normal limit
is **two `ACTIVE` implementation leaves per lane**, and the default preference is to
finish the nearest-to-merge active leaf before taking another. `READY`, `WAITING`,
`BLOCKED` and `TURNED_IN` are not implementation WIP.

Machine-readable policy and lane state live in [`flow-control/`](flow-control/).
Before branch mutation:

1. run `python3 -B scripts/check_bamf_flow_control.py`;
2. confirm the target leaf is represented in the correct lane file;
3. if it is parked, verify its recorded resume trigger has actually occurred;
4. change it to `ACTIVE` before refreshing/syncing/reviewing its branch;
5. keep the lane at or below the normal active limit unless the lane file contains
   an explicit exception with reason, authority and expiry.

A `WAITING` or `BLOCKED` PR is frozen. Do not merge-forward it, rebase it, rerun
full exact-head validation, request fresh review or otherwise churn it merely
because unified moved. When its real trigger fires, activate it and perform the one
refresh/revalidation required by its contract. This keeps external review and
dependency queues from masquerading as implementation throughput.

### Integration inventory and DRAIN mode

ADR-126 adds a separate integration-inventory gate. ACTIVE WIP remains governed by
ADR-124, but open BAMF implementation PRs are capped at **three total**, normally one
current integration candidate per lane. The unified integration PR into `main`
does not consume an implementation slot.

A completed leaf can remain on a durable branch. Before PR creation, run
`python3 -B scripts/check_bamf_flow_control.py --live`. The live gate reconciles
GitHub against the lane ledgers and checks PR admission.

When open implementation inventory is above the ceiling, the program is in
**DRAIN** mode. No new implementation PRs are admitted. The existing implementation
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

Keep one writer per lane. At issue start, sync the current unified trunk into the
lane and record the consumed unified SHA. Push coherent commits, record exact proof
on the issue, then open a PR from the lane branch into
`codex/bamf-unified-base-20261028` and add the issue closing keyword to the PR
Development section. Human sign-off is required before that PR merges. Main merge
and a durable live student launch remain operator actions. Context is a cache; the
issue, committed source and receipts carry continuation.
