# Issue #324 qualification preparation | 2026-10-26

**QUALIFICATION_MANIFEST_FROZEN_AND_READY_FOR_HUMAN_INITIATION**
**NO NEURAL RUN EXECUTED.** Do not launch either arm without deliberate human initiation.

- Preparation branch: `codex/324-learning-qualification-20261026`.
- Parent: #333 / PR #335 at `35cf2b8ccb6c7d0e9f195d7e65e4ef990bfe5994`.
- Exact executable commit: `59fa6bbfd1765df45277637430acf2a00d9e1e91`.
- Frozen execution checkout: `/Users/emilie/Code/.worktrees/bilqis-mlx/324-frozen-execution-20261026`.
- Source proof: Portable CI40321841155 and Semantic ABI CI40321841144 succeed.
- Current native proof: 122 passed, one existing source-dependent skip, 141 subtests.
  Qualification-only: 14 passed, 11 subtests; minimal no-pip host12 passed, two native skips.
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

Active manifest: `docs/evidence/qualification/issue324-20261026-v2.json`.
Canonical digest: `167c308831e95a1aa13a18b04608957b786281a030022ef6de3e2d0634cd964a`.
The v1 object folder is immutable provenance shared by v2; only v2 is active.
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

Both real dry-run commands passed with no neural authority and zero optimizer
updates. Seven altered manifest/identity cases fail closed. No experiment run
folder was created. Production byte hashes, source identities and code head are
pinned independently of review-only documentation commits.

## Next permitted action

Human reviews the packet and may explicitly initiate the two proposed commands,
sequentially. Neither command has run. No QUALIFIED/NOT_QUALIFIED learner result
exists. Do not extend budgets, widen semantics, use ordinary resume to refund an
interrupted experiment, or introduce Grade D/SKOS/historical migration. A changed
prerequisite or implementation requires a revalidated manifest. Real student,
original native AdamW, teacher, champions and historical checkpoints remain under
human custody; this lane performed only source/disposable checks and metadata writes.
