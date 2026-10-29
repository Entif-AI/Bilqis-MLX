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
