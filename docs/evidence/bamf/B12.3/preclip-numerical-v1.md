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

## Completion candidate — 2026-11-06

The historical numerical evidence above remains valid, but its open-gap list is
now stale. This completion pass consumed reviewed unified
`aef69dae9179bb09f85f955b8a494f6582eac942`, including the accepted #465,
#474, #475 and consolidated #809 authority/custody work, then reconciled every
B12.3-owned clause against the live production path instead of treating those
upstream closeouts as proof by themselves.

The one genuine remaining implementation gap was the historical scalar-step
migration rule. `runtime/_model/mlx_parity.py` now exposes
`native_uniform_step_counts(...)`. It first routes through the existing native
optimizer mapper, which requires a bijective parameter identity and rejects any
historical AdamW state whose per-parameter steps disagree. Only after that proof
does it expand the historical step into the target B12 count geometry: scalar
counts for whole tensors and leading-row counts for table-like parameters. The
target geometry must itself be bijective and either scalar or the parameter's
exact leading extent. The migration therefore cannot be authorized by elapsed
time, a caller-provided scalar, or a nonuniform historical optimizer history.
The historical-v1 bundle reader remains read-only and is not silently coerced
into BAMF v2 custody.

### Owned-clause reconciliation

1. **Historical scalar step:** implemented by the new uniform-step mapper above.
   Red/green proof demonstrates exact expansion to scalar and row counts and
   fail-closed rejection when native parameter steps disagree.
2. **Global optimizer step:** accepted B12 candidate custody increments the
   retained `optimizer_step` by the number of actual candidate optimizer steps
   only when the candidate is accepted. Rejection returns the exact retained
   parent, so rejected speculative steps never advance the run clock.
3. **Preclip participation mask:** the accepted #465 production authority now
   derives the B09 mask from B11 execution, and B12 `_adamw_update(max_norm=...)`
   zeroes unparticipating rows before the global norm clip and before any AdamW
   moment or decay arithmetic. Huge frozen gradients therefore cannot change
   the active clipping factor.
4. **Separate optimizer counts versus row age:** B12 counts advance on each
   participating candidate step. B09 establishment age advances once per
   accepted candidate from the union of rows whose optimizer counts actually
   advanced. B13 v2 custody persists the count tensors, retained policy/row ages
   and accepted global optimizer step separately and cold-resume restores them
   independently.

The direct prerequisite #475 is CLOSED / COMPLETED / EGM-Passed and its
documentation closeout PR #882 is merged. #465 and #474 are likewise completed;
their accepted behavior is consumed here without reopening either issue. B11
#369 remains an integration parent, but the exact B11 gradient-execution owner
required by B12.3 is already present on reviewed unified through the accepted
#809 lineage. The child contract explicitly permits consuming such an exact
usable dependency receipt without treating an open integration parent as an
automatic blocker.

### Verification at implementation head

Implementation commit:
`e4ab53d0ce3ccbd9f1e5fed9685c3dfbc6ef8074`.

TDD for the missing migration seam:

- red: four pre-existing parity tests passed; two new B12.3 tests failed only
  because `native_uniform_step_counts` did not exist;
- green: parity suite **6/6 passed, 0 skipped, 0 failed**;
- malformed row geometry is rejected, and a deliberately divergent historical
  parameter step fails with `MLX_NATIVE_ADAMW_STEPS_DISAGREE`.

Affected behavioral/integration matrix: **64/64 passed, 0 skipped, 0 failed**.
It covers native AdamW and preclip arithmetic, B09-derived row participation,
zero-gradient versus never-participating clocks, candidate acceptance/rejection,
multi-step row-age unioning, B13 count/policy persistence, historical-v1
non-coercion and production execution authority.

Mechanical checks at this boundary: `git diff --check` PASS; changed module-size
PASS; governance-integrity PASS; BAMF flow-control PASS; checked-in BAMF contract
mirrors **43/43** PASS and recursive issue contract validation PASS. The workstack
validator remains intentionally `held` by eight pre-existing dependency-
normalization holds (`A03.4`, `A05.4`, `A05.5`, `A08.1b.2`, `A08.1b.5`,
`B02.4`, `B11.1a`, `C14.4`); this is recorded baseline inventory, not a new
#476 behavioral failure, and the exact B11 execution authority consumed here is
already accepted on unified.

No live student, durable optimizer lineage, checkpoint, teacher, champion or
human-owned neural run was started or mutated. Merge-readiness EGM, the leaf
turn-in gate and PR-hosted checks remain required before this receipt may be
promoted from completion candidate to final accepted closeout.
