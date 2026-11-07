# B12.3 private preclip numerical seam

Issue #476 remains open. This cut implements its numerical mask-before-clip
clause against supplied masks; actual execution provenance and retained-state
integration are still required. Source predecessor is
`0a04c3c7a38f8d6a7cbae3c2f9635f2778c8edcd`, consuming reviewed unified
`da0431bee37c0e4f766f05cc94ceb6b23ac7d054` (unchanged at issue-boundary fetch).

The private `_masked_clipped_gradients` validates exact FP32 gradient keys,
shapes and Boolean scalar/row masks against the numerical state. It uses
selection to zero frozen rows before calling the existing `mlx_parity`
global L2 clipping implementation. Nonfinite gradients and a nonfinite
selected norm reject; masked finite large gradients cannot affect the norm.
`_adamw_update(max_norm=...)` routes through that helper before any native
AdamW moment/decay arithmetic. Without max_norm the already-clipped input
contract remains unchanged. Invalid limits reject before an update.

Red: two missing-API failures with ten existing tests passing. Green:
**12/12 native MLX tests**, zero skips. The adversary changes frozen gradients
from zero to +/-3e38 while the selected row remains [3,4]; both norms equal5
and clipped arrays and resulting parameters/moments/counts match exactly.
Tests also cover invalid limits and overflowing selected norm rejection.

Fresh independent EGM at pin
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`: scoped PASS, zero Blocker/Major;
independently reproduced12/12. Explicit operator audit and diff check pass.

No model-derived participation grant, historical scalar-step migration,
accepted global step, persisted establishment ages or retained-candidate
publication was added. #475's complete transaction and #476's remaining
clauses stay open. No closing links or full B12 acceptance claims.

IPR-0220 remains open; PM-2026-10-29-001/002/003/004/006 controls remain.
No durable student, own AdamW, teacher, champion or original changed.
Learning/retention remain unmeasured. Human owns unified integration and
actual durable training initiation.

## Full-completion reconciliation — 2026-11-06

The historical status above is preserved as the truth of the original numerical
cut. The #476 implementation began from reviewed unified
`0afb12a08848a6f2aba3b83b26f1466ea708d857`, which already contained the
accepted upstream seams that were missing then. Before merge-readiness review it
also consumed current reviewed unified
`aef69dae9179bb09f85f955b8a494f6582eac942` through merge
`540519899454065d9d44331a9809511838d5aee3`; that advance changes only C02.1
real-source tests/evidence and does not overlap B12.3 implementation paths:

- #465 / B09.2 is CLOSED / COMPLETED / `EGM-Passed`; production participation
  and update masks are derived from B11 execution authority rather than caller
  assertions.
- #474 / B12.1 is CLOSED / COMPLETED / `EGM-Passed`; native AdamW owns scalar
  and per-row participation counts, local bias correction, zero-gradient legal
  participation, and byte-identical frozen state.
- #475 / B12.2 is CLOSED / COMPLETED / `EGM-Passed`; PR #882 is merged into
  reviewed unified as `0afb12a08848a6f2aba3b83b26f1466ea708d857`, and
  complete candidate optimizer transactions now accept/reject through owner
  execution provenance and retained-generation custody.

Those accepted ancestors satisfy B12.3 clauses 2–4 but do not, by themselves,
satisfy clause 1. The remaining gap was historical scalar-step migration.

### B12.3 clause-by-clause closure

1. **Historical scalar migration is conditional on a real all-together history.**
   `_mint_historical_bamf_migration_capability` can issue a non-serializable
   `HistoricalAdamWMigrationCapability` only from a code-owned attestation whose
   update contract is
   `bilqis.mlx.historical-full-tree-shared-scalar-static-count-geometry/v1`.
   The capability binds BAMF-v2 architecture identity, exact checkpoint SHA-256,
   exact ordered FP32 model state, exact native AdamW moments/hyperparameters and
   per-parameter steps, exact B01 parameter/count geometry, and the independently
   attested global optimizer step. `_migrate_historical_bamf_optimizer` rechecks
   those numerical digests before filling scalar/per-row B12 counts. Equal terminal
   per-parameter counters alone are explicitly insufficient: two disjoint native
   optimizer calls that end with `[1,1]` cannot satisfy an attested global step 2.
   Divergent steps, altered numerical state, unsupported late-row lineage, unknown
   attestations and caller-constructed capabilities all fail closed.

   The production attestation registry is intentionally empty. The pinned six-layer
   historical v1 student is readable evidence but its vocabulary-growth lineage
   inherited a scalar into newly introduced rows with zero moments, and B01/B13
   already forbid coercing v1 custody into BAMF v2. Therefore this change does not
   fabricate a migration authority for that source. A future BAMF-v2 historical
   scalar state may be migrated only after a repository-owned whole-lineage
   attestation proves the stronger contract above.

2. **Global optimizer step counts accepted optimizer steps.**
   Current `CandidateTransaction` advances retained `optimizer_step` by the number
   of accepted candidate update steps; rejected candidates return the exact parent.
   The two-step acceptance witness moves step 11→13 while rejection preserves 11.

3. **Participation masks precede clipping, decay and moments.**
   The accepted B09→B12 path materializes owner-issued participation against B12
   count geometry. `_masked_clipped_gradients` zeroes ineligible rows before the
   global norm, and `_adamw_update` performs native AdamW/decay/moment arithmetic
   only for selected leaves/rows. Huge frozen gradients therefore cannot change
   the active clipping factor.

4. **Per-step optimizer counts remain separate from retained-candidate row age.**
   Per-parameter/per-row counts advance on each legal optimizer step. On retention,
   `resolve_candidate` derives the union of identity rows whose counts changed and
   advances establishment age once for the accepted candidate, independent of its
   internal step count. B13 bundle records persist `optimizer_step`, the count tree,
   and plasticity policy/row ages separately; cold resume preserves that separation.

### Behavioral and integration evidence

Historical-migration TDD started with **13/15 passing and 2 expected missing-API
errors**. The first implementation reached 15/15, but ordinary adversarial review
found a real authority flaw: equal native terminal counts can arise from disjoint
optimizer calls. The implementation was hardened rather than accepting that false
premise. Ordinary review then found two further authority defects before turn-in:
a frozen capability could still be altered with `object.__setattr__`, and native
fractional step tensors could collide after integer truncation. Migration now
re-resolves the code-owned attestation on use, and native steps must be exact
finite nonnegative integers whose raw dtype/shape/value bytes are bound into the
optimizer-state digest. Final optimizer owner proof is **21/21 passed, zero
skips**, including:

- positive attested static full-tree scalar→B01 count geometry;
- divergent native-step rejection;
- equal-count/disjoint-history rejection;
- exact numerical-state anti-replay rejection;
- mutated-capability rejection against the code-owned attestation;
- fractional native-step rejection without truncation;
- unsupported late-row lineage rejection;
- caller-construction rejection;
- native FULL parity, FAST→FAST→FULL local counts, frozen bytes, count overflow,
  NaN/nonfinite failure, zero-gradient participation and preclip huge-gradient
  adversaries.

Affected optimizer/candidate/participation/parity/custody/topology and production
authority proof is **84 passed / 0 failed / 1 optional skipped**. The skip is the pre-existing
environment-gated frozen-real-v1 bundle witness; the executable v1 isolation test
in the same run passes. A stale cold-resume regression assertion was also corrected
from the superseded `B11_EXECUTION_AUTHORITY_REQUIRED` token to the
accepted #710/#809 production token `B11_GRADIENT_EXECUTION_REQUIRED`; production
behavior was unchanged.

Deterministic branch checks: BAMF flow control PASS; recursive contract mirrors
PASS; changed-file structure PASS; diff hygiene PASS; no new changed-file code-smell
finding. The workstack validator remains globally `held` only by its eight recorded
normalization holds (`A03.4`, `A05.4`, `A05.5`, `A08.1b.2`, `A08.1b.5`, `B02.4`,
`B11.1a`, `C14.4`); it reports no #476-specific issue.

The final physical-owner split is covered by **58/58 focused tests** across native
optimizer/migration, refinement, attention/GQA and backbone owners, plus **5/5**
runtime module-discovery/physical-group tests. A broad differential leaf run also
surfaced unrelated repository debt and missing local historical artifacts. Its six
cache-authority publication errors reproduce unchanged on reviewed unified
`aef69dae9179bb09f85f955b8a494f6582eac942`; the legacy checkpoint-dependent source
tests likewise cannot run in this disposable worktree without their ignored model
artifact. The one candidate-local discovery mismatch exposed by that broad run was
repaired and the dedicated 5/5 owner-identity suite now passes. Those inherited or
environment-gated failures are not used as B12.3 acceptance evidence.

Fresh merge-readiness Goldfish review is still required before #476 can be marked
`EGM-Passed` or closed. No live student, durable optimizer lineage, teacher,
champion, checkpoint or original artifact was mutated by this implementation.
