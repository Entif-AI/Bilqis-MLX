# BAMF-0.2 Lane A: executable launch

Continue the BAMF-0.2 program in Entif-AI/Bilqis-MLX. Root #341; lane #342; start #345 (A01).

## Owner-authorized Lane A batch | 28 October 2026

For this execution run, follow [the batch authorization](LANE_A_BATCH_AUTHORIZATION_20261028.md)
and its dated amendment on GitHub #342. Verified same-lane leaves may accumulate
as separate commits and receipts in one cumulative lane-to-unified PR while human
integration review is pending. Continue with dependency-ready work rather than
waiting after every leaf. Sync from current unified at every issue boundary;
human merge approval, independent review, full acceptance and all custody rules
remain unchanged. The per-issue PR wording below describes the default lifecycle;
this scoped amendment permits batching its return path only.

<!-- BAMF02:LANE-A-DEEP-ENTRYPOINT -->
**Current low-burn launch:** start with the deepest ready child [A01.1 #396](https://github.com/Entif-AI/Bilqis-MLX/issues/396), not the original broad [A01 #345](https://github.com/Entif-AI/Bilqis-MLX/issues/345). Follow `children/registry.json` for child prerequisites and native parents. Original parent remains the complete integration/acceptance contract; all technical requirements and existing EGM guardrails are unchanged. No live training starts from issue planning.

## Bootstrap once

Read root README.md, AGENTS.md, the root successor amendment and this lane's live issue. Read `docs/architecture/BAMF_0_2.md` for shared contract orientation once. Confirm the actual branch and worktree. Lane A works on `codex/bamf02-a-semantics`; `codex/bamf-unified-base-20261028` is the living reviewed integration trunk. Before each implementing issue begins, fetch `origin`, merge the current `origin/codex/bamf-unified-base-20261028` into the lane branch, record the consumed unified SHA, resolve any conflict, and verify the affected seam before issue-owned edits. Do not rebuild the baseline from `main` or the historical replay/SKOS refs.

## Work selection and isolation

**Recursive owner dispatch:** A09 #360 now has a native sub-issue tree. The A09.1 node is also a group with two grandchildren. When A09 becomes ready, select the deepest dependency-ready implementable issue from `children/index.json` rather than taking the complete A09 or A09.1 group as one coding task. The full A09 engineering specification and acceptance remain unchanged. Child completion does not automatically close its parents. Decompose any other oversized issue using the same lossless rule.


Use `docs/tasks/bamf-0.2/workstack.json` and the latest direct dependency receipts. Take the earliest ready leaf in this lane. Recheck only its named prerequisites. Read its allowed files and current amendments. Commit each coherent outcome. One lane writer owns the lane branch. Lane C owns shared trainer/CLI/ADR implementation surfaces; Lane A does not race those files. Reviewed Lane C or Lane B changes arrive through unified at the next issue-boundary sync, never by direct sibling merge.

Lane keys: A01, A02, A03, A04, A05, A06, A07, A08, A09, A10, A11, A12, A13.

## Flow-control preflight

Before taking or refreshing a leaf, run
`python3 -B scripts/check_bamf_flow_control.py` and read
`flow-control/lane-a.json`. Only `ACTIVE` counts as implementation
WIP and permits substantive branch mutation. The normal lane ceiling is two active
leaves, but prefer draining the nearest-to-merge active leaf before opening another.
A `WAITING` or `BLOCKED` PR remains frozen until its recorded resume trigger occurs;
a newer unified head by itself is not a resume trigger. Update the lane state to
`ACTIVE` before the one sync/revalidation pass required on resumption. Any
over-limit exception must name its reason, authority and expiry in the lane file.

## Implementation posture

Read root README.md and AGENTS.md once per fresh execution session, this issue plus its live amendments, direct dependency receipts and the listed source files. Work on the assigned lane branch with one writer; shared-file edits go through the integration owner. Preserve unrelated work. Use package-local unit tests and one smallest real integration witness; run the repository aggregate checks at an integration boundary, not after every tiny edit. Change only what the prescribed outcome needs. Any stale dependency label is rechecked against its exact branch/commit receipt. On completion commit and push the feature branch, read back its SHA, comment on this issue and the lane PR, and add `Closes #<this issue>` to that PR's Development section. Include changed paths, commands/results, design-review disposition, exact dependencies and next ready leaf. Keep branch work alive across page boundaries; checkpoint instead of stopping solely because quota is low. Live training is operator-started; disposable finite test students are permitted. No main merge is delegated by this issue.

Treat the selected shape, source authority, whole-system capability policy, plasticity and generated curriculum as settled. Implement the specified behavior. Where a small non-contract detail is unspecified, choose the smallest locally consistent implementation, record it in the leaf receipt and proceed. Escalate only an actual incompatible contract or unavailable permission; keep independent work moving.

## EGM and verification

Follow the canonical lifecycle in `docs/tasks/bamf-0.2/EGM_EXECUTION.md`.

EGM review happens before substantive implementation and targets the issue,
specification, or implementation plan. Reuse an approved design review unless the
design meaning changes. During implementation, use claim-first differential
verification and reuse passing evidence whose assumptions remain unchanged. When the
implementation is stable, run bounded design-to-code drift analysis, then the
applicable premerge gate before PR turn-in.

Use fresh Goldfish context only for the design-review work defined by the selected EGM
persona and standard. Do not use a post-implementation Goldfish code review as a
substitute for differential tests, drift analysis, or premerge verification.

Record the design-review disposition, exact verification receipts, drift disposition,
and next ready leaf in the closeout.

## Machine resources

M3 Ultra owns real MLX work. The second workstation may perform source generation, CPU tests and document/code preparation. Use the existing `m3-ultra` SSH alias when remote access is needed. A local-only SSH tunnel can expose the existing Falkor service after discovering its actual listener; it does not grant data or mutation authority. Pinned graph features and the local outbox keep neural steps independent of a live tunnel. Keep the existing disk reserve and resource limits in the leaf contract.

## Finish a leaf, continue

Push and read back the SHA. Open a PR from `codex/bamf02-a-semantics` into `codex/bamf-unified-base-20261028` for this completed issue, add `Closes #<leaf>` to the PR Development section, and comment on the leaf with the PR and exact branch/head receipt. Human sign-off is required; do not self-merge. Include exact changed paths, test commands and totals, design-review disposition and next ready leaf. After accepted work lands on unified, the next leaf starts by syncing unified again. Checkpoint every coherent unit and continue until the lane has no executable independent work. A low quota warning alone is not a blocker.
