# Issue #324 qualification preparation | 2026-10-26

**QUALIFICATION_MANIFEST_FROZEN_AND_READY_FOR_HUMAN_INITIATION**
**NO OFFICIAL V3 QUALIFICATION ARM HAS BEEN EXECUTED.** Do not launch either arm without deliberate human initiation.

- Preparation branch: `codex/324-learning-qualification-20261026`.
- Parent: #333 / PR #335 at `35cf2b8ccb6c7d0e9f195d7e65e4ef990bfe5994`.
- Exact executable commit: `2e5ee21a97a66c683c61f74419da03500c30d2c4`.
- Frozen execution checkout: `/Users/emilie/Code/.worktrees/bilqis-mlx/324-frozen-execution-v3-20261026`.
- Qualification-only suite: 15 tests pass, including a regression that terminal
  evaluation restores the school against the currently admitted staged release.
- One exact one-visit qualification-path repair validation completes end to end
  and emits the expected `FULL_WORKLOAD_NOT_YET_INTRODUCED` result instead of
  crashing. It is a disposable debug epoch and is not #324 baseline evidence.
- Governing issue #324 comment6412618439 explicitly accepts exact-head engineering
  evidence. #150/#320/#333 may remain open, draft and unmerged. Do not merge,
  retarget or modify their frozen branches to alter lifecycle state.
- IPR-0220 remains OPEN; protected checkpoint carries its private location. Public
  projections use only this opaque identifier.
- Current incident: PM-2026-10-26-007 / RC-135 / PAT-096, native ledger readback
  verified. Earlier #333 incident PM-2026-10-26-003 remains separate history.

## Frozen review packet

See `docs/evidence/qualification/ISSUE324_REVIEW_PACKET_20261026.md` for exact
commands, resource bounds, remaining acceptance and scientific assumptions.

Active manifest: `docs/evidence/qualification/issue324-20261026-v3.json`.
Canonical digest: `7f1968f38b2a062df7dbaae586ccecc3327ff5885a72cb7c368938ecec92aea1`.
V1/v2 remain immutable superseded provenance. V3 is the single active manifest.
The workload is A6/B8/C7, numeric inputs0..8, frozen from live source generation44238.
Future ceiling10 is excluded. Same-ABI A/A+B/A+B+C releases preserve prerequisite
admission; no untaught B/C examination occurs at initialization.

Baseline:6 layers/24 heads/width384/FFN1536/context96.
Capacity:8 layers/32 heads/width512/FFN2048/context96.
Both use fresh FP32 weights, native zero AdamW, initialization seed324, training
seed3240, identical pinned teacher/runtime policy and finite per-arm budget:
1000 visits, at most16000 attempted steps,90 minutes at safe boundaries,100 GiB reserve.
Acquisition seed32401; post seeds32403/32405/32407. Existing mean proficiency rules
apply. Fresh-probe scope/overlap/missingness remain explicit; no teaching embargo.

Both v3 arm dry-runs pass with no neural authority and zero optimizer updates.
Seven altered manifest/identity cases fail closed. The official v3 baseline and
capacity run folders do not exist. Production byte hashes, source identities and
the executable head are pinned independently of review-only documentation commits.

The user's first v2 launch exposed two runtime defects after preparation had
passed: lesson methodology received scheduler-only `ScheduleCapability` objects,
and terminal evaluation reconstructed an early staged school against the final
A+B+C schedule. Commits `1edba645…` and `b4e535c5…`, with regression lock
`6c815d4f…`, repair those seams. `895a1532…` satisfies the repository error-control
plane without changing the valid semantic-authority path, and `2e5ee21a…` defers
the native MLX import until full-workload inference is actually required so early
staged terminal evaluation remains portable. The aborted v2 run is preserved and MUST NOT be
resumed or counted. The live source run has advanced since generation44238, so v3
intentionally carries forward the already-frozen workload/policy/fixtures instead
of silently refreezing today's source state.

## Next permitted action

Human reviews the v3 packet and may explicitly initiate the two official commands,
sequentially. Neither official v3 arm has run. No scientifically valid
QUALIFIED/NOT_QUALIFIED #324 result exists. Do not extend budgets, widen semantics,
resume the aborted v2 epoch, or introduce Grade D/SKOS/historical migration. A
changed prerequisite or implementation requires another revalidated manifest.
