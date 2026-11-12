# C08 parent acceptance receipt | 2026-11-11

## Scope and release boundary

- Issue: `#374`, `BAMF-0.2 C08 | Make batch preparation and resource budgets topology-aware`.
- Lane: C runtime/integration.
- Reviewed integration base consumed: `f9aa79b6cececdedd28a0e80db1256f8a70a9d7f` from `origin/codex/bamf-unified-base-20261028`.
- Direct dependency implementation already present in that base:
  - C02: `0a5d0343` (`fix(bamf): align C02 with optimizer manifest authority`).
  - B11: `8899f7d2` (`feat(bamf): assemble atlas-native forward and refinement`).
- C08.1 `#513`, C08.2 `#514`, and C08.3 `#515` are closed.
- C08.4 `#558` remains open as a BAMF-0.3 successor and is nonblocking for BAMF-0.2 C08 closeout under the 2026-11-10 release-boundary amendment.

## Implemented behavior

The parent integration binds the topology-aware `BatchPlan` to one logical teacher batch and carries that exact plan through Factory preparation, B11 row execution, candidate admission, grouped proof, C05/C09 provenance, B09 participation, and motif staging.

The implementation provides deterministic split plans, row-count-weighted logical gradient accumulation, one later clip/AdamW application, exact plan/custody drift rejection before admission, grouped training authority/proof support, multi-row motif staging, and canonical runtime ownership for the moved batch-training modules. Review-driven repairs also close fail-closed proof, structural, and regression gaps discovered during parent turn-in.

Primary implementation sequence:

- `add82428` `C08: bind logical batch accumulation to resource plan (#374)`
- `7f953ee7` `fix(bamf): close C08 review gaps`
- `96159c09` `test(bamf): strengthen C08 drift proofs`
- `f25edba4` `test(bamf): split C08 candidate-step proofs`
- `9b170cbf` `fix(bamf): validate Factory delivery observations`
- `64b85e7a` `test(bamf): preflight C08 Factory witness`
- `42297298` `docs(bamf): require staged expensive-test preflight`
- `8cd10943` `test(bamf): harden staged C08 verification`

## Verification before the real witness

The repaired candidate passed the bounded exact-head verification ring:

- Core C08/resource/authority ring: `56 passed`, `18 subtests passed`.
- Engram and B08 source-owner ring: `32 passed`, `33 skipped`, `14 subtests passed`.
- Runtime batch-training ring: `75 passed`, `8 skipped`, `10 subtests passed`.
- Teacher-observation package after the observation-boundary repair: `10 passed`.
- Focused observation/delivery package: `23 passed`, `5 subtests passed`.
- BAMF flow-control check: `BAMF_FLOW_CONTROL_OK`.
- Development structure check: `0 violations`.
- Changed-file smell audit: `0 new findings`.
- Error-control-plane check: `new debt 0`.
- `git diff --check`: clean.

Independent review found and repaired:

- three long-function code-smell blockers;
- incomplete non-identity B09 logical-batch union coverage;
- plan-drift tests that originally rejected too early on digest mismatch;
- C09 duplicate-proof fixtures that originally failed before reaching duplicate registration;
- nested `_batch/training` canonical-path audit coverage;
- a malformed observation fixture that could survive until post-training bookkeeping;
- an impossible prepared-versus-execution authority-digest equality assertion.

The final implementation/custody re-audits before the real witness reported no remaining blocker, major, or minor finding. A final tooling-only review of the post-PASS preflight hardening is recorded separately at turn-in and does not change production semantics.

## Expensive-witness failure history

The full history is retained because each failure narrowed the problem without mutating accepted source state.

1. Initial real-Factory witness: killed by the artificial 240-second wall guard. Peak RSS was about 8 GiB. No source mutation or semantic assertion surfaced.
2. Detached timing diagnostic: its 180-second alarm fired during accepted-artifact validation after publication consumed about 129 seconds. It never reached row gradients.
3. 720-second real-Factory witness: wall guard only, about 8 GiB peak RSS, no source mutation or semantic assertion.
4. R2 with a 1800-second wall guard: ran 1538.12 seconds and then failed after the expensive candidate path because the test supplied an unprepared `ObservationCapture` without `selected_option`. The fixture and fail-fast boundary were repaired with a cheap regression.
5. R3: ran 1613.33 seconds and then failed on a stale postcondition that required the execution-time training-authority digest to equal the pre-forward digest. B11 lawfully extends execution-observed dependencies, so the correct invariant is stable authority identity plus monotonic dependency extension. A cheap contract regression now proves that rule.

These failures motivated ADR-139 and the staged fail-fast verification contract in `AGENTS.md`.

## Terminal real-Factory witness

Detached label: `C08-374-64b85e7a-staged-real-factory-r4`.

- Tested immutable Git head: `64b85e7a2ebc2a64efb177e58de959e4b8950e41`.
- Source/snapshot SHA-256: `659a1fa5f50ab60a22adacc2668d0fa3081a21d976358266333b1acde812fcd7`.
- Receipt: `/private/tmp/bamf-c08-374-64b85e7a-staged-r4-receipt.json`.
- Log: `/private/tmp/bamf-c08-374-64b85e7a-staged-r4.log`.
- Detached runner result: `PASS`, return code `0`, `source_mutated=false`.
- Fast contracts: `6 passed`, `6 subtests passed`, `0.88s`.
- Real-fixture preflight: `1 passed`, `337.82s`.
- Exact two-row real-Factory MLX witness: `1 passed`, `1597.21s`.
- Resource guard: `GUARD=NONE`.
- Peak RSS: `8,467,872 KiB`, about `8.076 GiB`.

The real witness proves the C08 parent integration on the actual Factory/A01 artifact path: two delivered real rows are planned as one logical teacher batch split into deterministic microbatches, both row-scoped B11 executions contribute to one logical gradient result, the candidate advances exactly one optimizer step, grouped training authority/proof is retained, motif staging remains present, and realized cost reports one optimizer step.

## Evidence reuse after the terminal PASS

The branch subsequently received documentation and verification-tooling changes only: ADR-139/`AGENTS.md` staged-verification doctrine plus hardening of the C08 preflight/runner and structural relocation of BAMF workstack/grooming scripts. These changes do not alter C08 production runtime, model, optimizer, Factory execution, resource planning, custody, or the full witness assertion path. Under ADR-129, the r4 real-Factory PASS therefore remains valid production acceptance evidence; only the newly changed tooling receives fresh lightweight verification and review.

## Current unified reconciliation | 2026-11-11

The feature branch later consumed current reviewed unified head
`c42362ced0309a24f2f95391257df8f4ef3588cc` in merge commit
`d54b0703f66beda6e60f12c1de58c07885e28026`.

- The upstream `ADR-138` resource-containment decision is preserved. This branch's
  staged fail-fast verification decision was mechanically renumbered to `ADR-139`;
  its accepted doctrine is unchanged.
- The runtime package path exports now include both C08 `_batch/training` ownership
  and unified `_admission/v2` ownership.
- Current-base cheap verification is green: the BAMF contract verifier passed,
  `git diff --check` is clean, the focused C08 seam ring passed `14` tests with
  `9` skips and `9` subtests, and `npm run quality:check` passed with
  `BILQIS_QUALITY_BASE_REF=origin/codex/bamf-unified-base-20261028` and
  serialized test workers.
- The first premerge r2 attempt before this merge failed only because the older
  branch lacked four legacy-trainer evidence updates already present on current
  unified. Current-base `quality:check` confirms that integration mismatch is closed.

Legacy-trainer adaptation authority remains the preserved Factory replay
`/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`.

Current unified also refactored Factory source-frame preparation through
`source_frame_inventory(...)`, which lies on the real C08 pre-gradient path.
Therefore the historical r4 PASS remains valid evidence for its tested immutable
head, but it is not silently promoted into current-base integration proof under
ADR-129. A current-base real-fixture/full witness and aggregate premerge gate remain
the final turn-in evidence.

Two independent read-only turn-in reviews were then collected against the reconciled
current-base branch. The implementation/custody reviewer reported no blocker, major,
or minor correctness or integration defect across C08 resource planning, row-weighted
gradient accumulation, grouped training authority/proof, participation unions, motif
staging, canonical owner-path relocation, or the current-unified source-frame lineage
changes. The evidence reviewer independently confirmed that the r4 PASS remains valid
for its immutable tested head, that `ADR-139` renumbering is internally consistent,
and that the minimum remaining current-base evidence is exactly one staged mounted
real-fixture/full witness followed by the aggregate premerge gate. That reviewer also
confirmed the PR must not be presented as ready for human review until those gates are
green or validly reusable.

## Current-base staged witness r3 | 2026-11-11

The operator subsequently clarified that bounded MLX/full-model jobs on the M3 Ultra
may run concurrently; another bounded MLX job is not, by itself, a reason to wait.
The C08 witness retained its own explicit RSS and wall guards.

Detached current-base run `C08-374-1d9866b5-current-base-turnin-r3` executed from
immutable head `1d9866b5c93cefa08c2fcb790261ccf2716a5e38` with source/snapshot SHA-256
`a16fc56a41c6a1a396b42031295fd1cc3e5cdb46486c21b4da08c26ffff852b1`.

- Fast contracts: `6 passed`, `6 subtests`, `0.81s`.
- Mounted real-fixture preflight: `1 passed`, `1135.32s`.
- Exact two-row real-Factory MLX witness: `1 passed`, `1496.89s`.
- Full-witness guard: `GUARD=NONE`.
- Peak witness RSS: `9,802,960 KiB`, about `9.349 GiB`.
- Detached snapshot remained unchanged: `source_mutated=false`.

The C08 current-base production acceptance path is therefore green. The detached
pipeline failed only afterward, when `quality:check` reached the static
legacy-trainer authority scanner and this receipt mentioned `legacy-trainer` without
also naming the canonical replay path. That is a cheap evidence-document defect,
not a C08 semantic, Factory, gradient, optimizer, custody, or MLX failure.

This failure also exposed an ordering defect in the turn-in harness: applicable
neural-inert quality/static checks must run before mounted real-fixture or full-model
execution. Future C08 turn-in runs reuse the green current-base witness under ADR-129
unless a dependency on its production path changes; they do not repay the expensive
witness merely because a later documentation/static gate failed.

The first premerge-only aggregate attempt after that repair was intentionally stopped
once it recorded a test error and then began executing the already-accepted C08
real-Factory witness again. The root harness defect was default aggregate discovery:
`scripts/run_tests.py` did not honor the existing `DETACHED_ONLY` policy used by the
differential gate. A focused regression failed before repair by showing a detached-only
test file present in default discovery. The runner now excludes such files by default,
while explicit targeted execution remains available. The C08 real-execution module is
declared `DETACHED_ONLY`, as is the pre-existing Factory retention live witness. The
focused runner/gate suite passes `27/27`, and direct discovery confirms both files are
absent from the aggregate set.

## Final turn-in qualification | 2026-11-11

Turn-in identity:

- issue: `#374` / `C08`, Lane C;
- reviewed unified: `c42362ced0309a24f2f95391257df8f4ef3588cc`;
- final reviewed code/test/governance tip before the evidence-only commit:
  `3e0a02a3d34bc1fb06c1096519e9f0d78377f5a3`;
- consumed C02 receipt: `0a5d0343`; consumed B11 receipt: `8899f7d2`;
- primary production surfaces: topology-aware resource contracts, logical-batch
  gradient accumulation, candidate-step/binder training authority, grouped proof and
  retention consumers, Factory candidate training, motif/source continuation, and
  runtime training-owner relocation;
- verification/governance surfaces: C08 Factory bridge/execution/preflight tests,
  staged witness scripts, aggregate test discovery, ADR-139/ADR-140, `AGENTS.md`, and
  this acceptance receipt.

The operator clarified the M3 Ultra execution policy after the initial current-base
qualification attempt: independent MLX/full-model jobs may overlap when each job is
explicitly bounded. ADR-140 records that correction. MLX remains single-worker inside
an unbudgeted runner, but another bounded process or high swap occupancy alone is not
a host-wide veto.

The current-base production witness remains the authoritative C08 semantic proof:

- detached head `1d9866b5c93cefa08c2fcb790261ccf2716a5e38`;
- fast contracts: `6 passed`, `6 subtests`;
- mounted real-fixture preflight: `1 passed` in `1135.32s`;
- exact two-row real-Factory MLX witness: `1 passed` in `1496.89s`;
- `GUARD=NONE`, peak RSS about `9.349 GiB`, `source_mutated=false`.

Git inspection from that witness head through final test/governance candidate
`3e0a02a3d34bc1fb06c1096519e9f0d78377f5a3` shows no production-module changes.
The entire later delta is ADR/AGENTS policy, test fixtures, test selection, and this
evidence document. ADR-129 therefore permits reuse of the green production witness.

### Aggregate fail-fast classification

The corrected aggregate r6 ran from `416b4374cd07efabe00dc17004039bd0806e8e7b`
with one Python process, MLX cache disabled, and an explicit 24 GiB memory limit.
Default discovery no longer schedules `DETACHED_ONLY` witnesses. The run was stopped
at its first error rather than collecting redundant failures after the gate was
already red.

The first error was `SchoolNumericAnswersTests.setUpClass`, before any test body ran.
Exact focused replay on both candidate `416b4374` and pristine reviewed unified
`c42362ced0309a24f2f95391257df8f4ef3588cc` produces the same `FileNotFoundError`
for the absent preserved vendor checkpoint
`vendor/legacy-v16/runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt`.
The aggregate result is therefore absolute red and differentially inherited at the
first failing boundary. It is not relabelled green. No #374-owned aggregate regression
was identified before that inherited boundary.

### Correction-hold fixture repair

The earlier aggregate attempt also exposed a stale C09 correction-hold fixture. The
exact pristine-unified version is itself red before correction handling because its
old generation-zero publication path now rejects with
`BAMF_INITIAL_GENERATION_BOOTSTRAP_REQUIRED`. C08 correctly modernized that fixture
to `publish_initial_generation`, which exposed two candidate-side test defects:

1. `FactoryTrainingBridgeFixture` installed the export-clearance host registry while
   the correction event was signed by the fixture's separate synthetic `AUTHORITY`.
   A cheap RED regression showed `host_source_authority_patch(AUTHORITY)` was
   unsupported. The helper now accepts an optional registry while preserving its
   existing default, and the Factory fixture binds its actual authority.
2. The disposable Factory fixture reused the workstation-wide data plane with fixed
   run identity `factory-training-live`. Genesis trust is keyed by run ID, so prior
   test state could trigger `BAMF_INITIAL_GENERATION_TRUST_ROOT_DRIFT`. The fixture
   now uses a temporary per-test `BILQIS_DATA_PLANE`; production trust-root checks are
   unchanged.

Cheap verification at final reviewed test/governance tip `3e0a02a3` is green: runner/gate regressions `27/27`, BAMF
contract mirrors `43/43`, full `quality:check`, explicit/default source-authority helper contracts, nine focused data-plane/helper
contracts, governance, docs, Factory architecture, error-control, flow-control,
changed-file smell audit, and `git diff --check` all pass. The final two-line cleanup
closes cached per-test data-plane connections before environment restoration and temp
directory removal.

Exact repaired correction-hold witness `C08-374-d50fb77f-correction-hold-r3`
ran from immutable test/governance head
`d50fb77f9a116446d2f7a6462e97d606b9c3c455` with the mounted A01 artifact,
MLX cache disabled, and a 24 GiB memory limit. It returned `PASS`, return code `0`,
with `source_mutated=false`; `1 passed in 1344.83s (0:22:24)`. The test proves that a persisted
C09 source correction holds the prepared Factory training batch with
`BAMF_C09_ARTIFACT_HELD` before gradient read. Final tip `3e0a02a3` differs only by
post-test data-plane connection cleanup, so this result remains valid there.

A final independent read-only review of the post-witness test/governance delta reported
`PASS - 0 Blockers / 0 Majors / 0 Minors` after the final data-plane cleanup repair.

## Disposition

C08 BAMF-0.2 owned acceptance is satisfied. The current-base production witness is
green and reusable under ADR-129. Aggregate premerge remains absolute red only at a
first failing boundary reproduced on exact reviewed unified. Candidate-owned fixture
regressions discovered during turn-in are repaired and independently qualified.
The feature is ready for a human-reviewed pull request into
`codex/bamf-unified-base-20261028`. This receipt does not authorize self-merge or
issue closure before that PR is merged and read back.
