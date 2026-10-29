# C08.2 | Installed MLX telemetry and bounded OOM recovery

Issue #514, direct predecessor C08.1 #513, parent C08 #374.
Lane C `codex/bamf02-c-runtime` consumed reviewed unified
`6e83c0f6618f81a6d41f82503f16a80b8e14164f`.
Implementation commit:
`198fbe6d75aebb7c61b125faac778fe64b498393`.
Draft PR #550 remains human-controlled and unmerged.

## Installed MLX memory API witness (M3 Ultra)

Read-only inspection on 2026-10-29 observed installed
`mlx.core.__version__ == "0.31.1"`.
Available callable APIs:
`get_active_memory() -> int`,
`get_cache_memory() -> int`,
`get_peak_memory() -> int`,
`reset_peak_memory() -> None`,
`set_memory_limit(limit: int) -> int`,
`set_cache_limit(limit: int) -> int`,
`clear_cache() -> None`.
`get_memory_limit` and `get_cache_limit` were absent.
The three read-only getters returned active=8, cache=0,
peak=8 bytes in the isolated inspection process. No setter,
peak reset, MLX allocation or trainer mutation was invoked.

## Exact owned behavior

- `bilqis.c08.memory-telemetry/v1` captures active, cache and
  peak memory without resetting MLX's global telemetry.
- `bilqis.c08.oom-receipt/v1` binds the failed microbatch size,
  source content digest, optimizer seed, generation, observed peak,
  cache and failure identity.
- `bilqis.c08.retry-state/v1` preserves immutable original
  logical plan, retained candidate and optimizer snapshot digests,
  plus exact failure/restoration history.
- `handle_oom` restores the retained candidate and optimizer
  snapshot **before** attempting source replay checks. The first
  OOM retries exactly once at the next smaller declared size
  with the same delivered rows, source digest, generation and
  step seed. A second OOM, or OOM at batch one, restores the
  candidate and returns EXHAUSTED at a safe boundary without
  speculative further retries.
- Forged restoration receipts or changed source/seed/generation
  reject; even a source-drift rejection occurs after restoration.

## Verification and integration limits

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_atlas_resources.py
bilqis_mlx/runtime/tests/test_atlas_training_adapter.py`:
**49 passed, 0 failed, 0 skipped** (10 C08 tests, 39 C02
adapter tests). Synthetic OOM fixtures prove one retry,
batch-one exhaustion, exact row/seed identity, restoration
precedence and no peak reset. Static checks found no new
C08-specific error-control or module-size debt.

The restoration callback belongs to B11/C checkpoint custody.
This candidate does not itself restore real MLX tensors,
recreate AdamW moments, reset peak counters or start a
learner. Live MLX OOM calibration, C08.3 source-worker/disk
proof, independent EGM and C08 parent integration remain
pending. No private source, checkpoint or neural state was
changed.
