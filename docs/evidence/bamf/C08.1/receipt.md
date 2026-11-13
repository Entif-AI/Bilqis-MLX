# C08.1 | Topology-aware activation and deterministic microbatch planning

Issue #513, parent C08 #374. Lane C
`codex/bamf02-c-runtime`, reviewed unified baseline
`6e83c0f6618f81a6d41f82503f16a80b8e14164f` consumed
without no-op merge. Implementation commit:
`df8fd4fd6d9e0d2638740f7ba4acc10719e06aa0`.
Draft human-review PR #550 remains unmerged.

## Implemented pure resource contract

- `bilqis.c08.frame-stats/v1` carries actual compiled neural
  positions, raw frame lengths, constituent expansions and depth
  summaries. `bilqis.c08.resource-row/v1` binds exact C02 delivery
  row ID, optimizer step seed, target decision budget and generation
  identity; a typed C02 conversion rejects forged generation binding.
- `bilqis.c08.memory-budget/v1` uses B01's immutable topology and
  parameter census, explicit FP32 weights/AdamW moments/candidate
  copies, analytical per-layer activation terms and a conservative
  safety factor. The default trainer envelope is **48 GiB**;
  the 100 GiB disk reserve remains owned by C08.3.
- `plan_microbatches` preserves one complete ordered logical
  teacher batch, choosing deterministically among
  **32/16/8/4/2/1** by resident/activation bytes and compiled
  position budget. Full raw 1024-frame examples with 1022 input
  positions plus two answer decisions start at four rows.
  Exhaustion at batch one fails before backend writes.
- `bilqis.c08.accumulated-gradient/v1` weights each microbatch's
  mean gradient by its actual row count, averages over the original
  logical batch, then applies global norm clipping once. A single
  `apply_one_adamw_step` call passes the clipped gradient to B11's
  sole optimizer-owner callback and requires one exact
  `bilqis.c08.backend-step-receipt/v1`.

## Verification and outstanding gates

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_atlas_resources.py
bilqis_mlx/runtime/tests/test_atlas_training_adapter.py`:
**46 passed, 0 failed, 0 skipped** (7 C08.1 tests plus 39
C02 adapter tests). Tests verify every fallback size, exact
logical row coverage, context/decision limits, 1024-frame
partitioning, deterministic resource estimates, weighted split
versus unsplit gradient equivalence, clipping, one backend
invocation and rejection of mismatched seed/generation/groups.
No live MLX allocation or optimizer step occurred.

Static scans found no new C08-specific error-control or
module-size findings beyond inherited debt.

This is a provisional source-compiler/B11 integration seam:
actual A05 frame statistics, B11 MLX gradient execution,
real peak-memory calibration and human-owned live trainer
acceptance are not yet integrated. C08.2 owns OOM retry,
C08.3 owns CPU workers and disk reserve. Independent EGM
is pending. No neural state, private source, retained
generation or checkpoint was modified.
