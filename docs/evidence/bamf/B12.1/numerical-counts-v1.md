# B12.1 numerical participation counts

Issue #474 remains open. This cut implements a private numerical AdamW seam;
actual B11 model/candidate binding and retained-generation custody are pending.

Consumed reviewed unified `da0431bee37c0e4f766f05cc94ceb6b23ac7d054`, merged
into Lane B at `7907889358bdbb7a324be5f427ce85d03d07e76a`. Existing reviewed
B06/B07/B09 lane commits were preserved by fast-forward first.

`AdamWStateTree` uses schema `bilqis.mlx.adamw-count-state/provisional-v1`.
FP32 parameter/moment trees have exact matching keys and shapes. Counts are
uint64 scalars for whole tensors or uint64 leading-row vectors for tables.
Masks are explicit Boolean arrays of the count shape. Native MLX AdamW
`apply_single` receives each participating entry's next local count, preserving
native equations and supplied hyperparameters. Only gathered participating
rows enter moment/decay arithmetic. Zero numerical gradients still participate.
No-loss and fully frozen calls preserve the original state object.

Preflight rejects nonfinite state/gradients, malformed masks/trees, negative
second moments and selected count overflow before producing an update.
Unselected maximum counts remain unchanged. The native uint64 boundary is
constructed through NumPy because direct Python-integer conversion fails in
this MLX build. Parameter/moment updates use copied MLX arrays and indexed
assignment; counts use a Boolean increment to avoid unsupported GPU uint64
scatter. Parent arrays are unchanged by the update operation.

Focused disposable proof: **10/10 passed, zero skips**, using
`.local/bamf-lane-b/.venv/bin/python -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_atlas_optimizer.py` through the validation runner.
Tests compare dense/row updates against independent native AdamW, two FAST
masks then FULL, zero-gradient participation, frozen bytes, no-loss identity,
invalid inputs, overflow and parent preservation. Intentional red failures
were retained in local validation logs. Merge-boundary topology/frame/features
checks: **49 passed, zero failed, two optional skips**.

Independent EGM at pin `b3a35956759bf7f024af2ff061b2e0b44b438e4c`: scoped
PASS after bounded re-review, 10/10 independently reproduced. Review found
preflight reconstruction replaced parent mapping identities. Construction now
freezes mappings once; pure validation preserves mapping identity on no-loss
and rejected calls. New regressions failed 2/10 before repair and pass after.
Nonzero-moment zero-gradient and scalar uint64 overflow cases also pass.
PM-2026-10-29-006 was filed at discovery and read back from the native ledger.

Actual candidate_step, B01 manifest-derived mask/decay ownership, clipping,
allocation/admission authority, per-candidate row ages, serialization and
accepted-generation publication remain with their existing B11/B12/B13 owners.
This helper has no production caller or durable-student entrypoint. No closing
link or full #474/parent acceptance is claimed.

IPR-0220 remains open. PM-2026-10-29-001/002/003/004 controls remain applicable.
No durable student, own AdamW, teacher, champion or original artifact changed.
Actual learning and retention remain unmeasured. Human integration and durable
training initiation remain separate gates.


## Completion addendum — 2026-11-06

This addendum supersedes the historical “Issue #474 remains open” and
“no production caller” status above without rewriting the evidence that was true
when the numerical seam was first staged.

The original B12.1 numerical owner was implemented at
`7080d6445404411c7d64ee26680d73cff06ce11f` and independently reviewed by
pinned Goldfish after the pure-validation repair. Its core B12.1 invariants were
already demonstrated there: exact native MLX AdamW arithmetic with supplied
learning rate/betas/epsilon/weight decay, scalar and per-row uint64 update
counts, selected-row-only moment/count/decay advancement, selected
zero-gradient participation, and byte/identity preservation for frozen and
no-loss paths.

Since that receipt was written, the missing production integration has landed.
The reviewed-unified runtime now routes owner-issued B11 gradient execution
through B09 participation/provenance and into B12 candidate custody:

- `runtime/_batch/atlas_candidate_step.py` requires B11
  `BamfGradientExecution`, validates accepted B13 custody and generation
  binding, and passes no caller-authored participation facts;
- `learning/_retention/_atlas_candidate/transaction.py` materializes the B09
  owner mask against the current B12 update-count geometry and calls the same
  native `_adamw_update(...)` owner;
- rejected candidates return the exact retained parent, so weights, m/v,
  update counts, optimizer step, row ages and cadence clocks do not publish;
- accepted candidates advance optimizer steps per actual candidate step and
  row establishment only once per accepted candidate;
- the B09 production binder derives participation from actual B11 execution,
  including semantic denominators and retained B08 motif reads, so B12.1 no
  longer depends on an untrusted caller mask.

The numerical owner itself was later extended only through the separately
reviewed B12 sibling seams: mask-before-global-clipping support and the B01
unbound optimizer constructor. The four B12.1 obligations remain the same.
The current optimizer owner is at
`bilqis_mlx/runtime/_model/atlas_optimizer.py` (blob
`87782a3b78623bd4bb916e219ff39ea1fbb76a96`); the structural move from
`runtime/atlas_optimizer.py` preserved that blob byte-for-byte at the move
boundary.

Current literal witnesses include:

- whole-tensor native AdamW parity with teacher-supplied hyperparameters;
- divergent per-row counts matching independent native row optimizers;
- two FAST updates followed by FULL preserving local bias-correction history;
- first participating row update advancing from local count zero to one;
- frozen rows preserving parameter, m, v and count bytes;
- selected zero-gradient rows advancing count/moments and applicable decay while
  never-participating rows do not;
- uint64 overflow and nonfinite gradients failing before parent mutation;
- huge frozen gradients having no effect on the active clipping factor;
- multi-step candidate rejection returning the exact retained parent;
- owner-issued production execution provenance being required before an actual
  candidate optimizer step.

The production authority/custody integration was independently reviewed as part
of consolidated PR #809. Pinned Goldfish checkout
`b3a35956759bf7f024af2ff061b2e0b44b438e4c` passed semantic candidate
`93233f86849f374ce5026291d4fd5cfa902a2e31` with **0 Blockers / 0 Majors /
0 Nits** after the sole initial mirror-policy Major was repaired and re-audited.
PR #809 then passed fresh hosted `portable-core`, `portable`, and
`semantic-abi-integrity` checks and merged into reviewed unified as
`b16941114dee33247ee9a9e6c013797b9d82af27`.

The current reviewed-unified head consumed by this closeout is
`2fa5e875aacf18b2d26fd7354053ec2904818546`. Its only change after the #809
integration lineage is the documentation-only #465 closeout merge; no B12
optimizer or candidate semantics changed.

### Final B12.1 acceptance ledger

- Issue: #474 / B12.1.
- Original numerical implementation:
  `7080d6445404411c7d64ee26680d73cff06ce11f`.
- Original scoped pinned EGM: PASS after repair and bounded re-review.
- Numerical seam integration: human-merged PR #552.
- Production execution/candidate authority integration: human-merged PR #809.
- Current reviewed-unified head:
  `2fa5e875aacf18b2d26fd7354053ec2904818546`.
- Whole-candidate pinned semantic EGM: PASS, 0 Blockers / 0 Majors / 0 Nits.
- Hosted integration checks: portable-core PASS; portable PASS;
  semantic-abi-integrity PASS.
- Direct prerequisite B11/#369 remains an open integration parent, but B12.1's
  required production B11 execution owner is present and consumed on reviewed
  unified; the child contract explicitly permits this when an exact usable
  dependency receipt exists.
- No live human-owned student, optimizer lineage, checkpoint, teacher, champion
  or durable neural run was started or mutated by this closeout.

This closeout branch is documentation-only. It does not create a second optimizer
implementation or alter the accepted B12 authority path.
