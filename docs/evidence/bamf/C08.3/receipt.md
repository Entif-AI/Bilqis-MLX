# C08.3 | Immutable CPU source packets and complete disk reserve

Issue #515, direct predecessor C08.2 #514, parent C08 #374.
Lane C `codex/bamf02-c-runtime` consumed reviewed unified
`6e83c0f6618f81a6d41f82503f16a80b8e14164f`.
Implementation commit:
`3209c1f033630b903f00d82aa78bb96cb50e2d5e`.
Draft PR #550 remains human-controlled.

## Exact owned behavior

- The existing source-preparation process pool is now explicitly
  bounded to one or two CPU workers. The new
  `bilqis.mlx.source-prefetch-immutable/v1` packet recursively
  freezes source data into picklable tuples with canonical digest,
  exact source identity and no neural/optimizer/checkpoint/
  network-client authority. Legitimate nested source provenance
  receipts remain permitted; a top-level run receipt is forbidden.
- `prepare_immutable_step_sources` is a separate BAMF CPU-worker
  entrypoint. The historical mutable packet contract remains
  unchanged for legacy callers; no hidden live trainer migration
  is claimed. Two spawned CPU workers produced byte-identical
  frozen packets to serial preparation in a synthetic fixture.
- `bilqis.c08.next-bundle-budget/v1` calculates complete next
  checkpoint demand from B01's parameter census, FP32 weights,
  AdamW moments and **explicit** manifest/publication overhead.
  `assert_bundle_headroom` preserves the existing **100 GiB**
  disk reserve and reports `required_next_bundle_bytes`,
  `weights_bytes`, `optimizer_moments_bytes`,
  `manifest_bytes` and `publication_overhead_bytes` before
  permitting any write. Below the reserve, it fails at the
  existing safe `DISK_BUDGET_EXHAUSTED` boundary.
- No SSH, graph or network call was introduced into the neural
  step. Existing tunnel infrastructure remains optional
  source/graph readback only; no model-state transport path
  was added.

## Verification and limitations

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_atlas_resources.py
bilqis_mlx/runtime/tests/test_source_prefetch.py`:
**21 passed, 0 failed, 1 optional original-source test skipped**.
The spawned-worker equality test, forbidden model-state adversary,
source-receipt preservation and disk headroom failure fixture
all passed. The original source corpus was not mounted for the
optional real-source spawned-process test.

Static error-control scan showed no new C08.3-specific findings.
The module-size checker still reports three inherited unrelated
regressions. This is a pure/fixture-level C08.3 candidate; actual
source-compiler delivery, optional SSH graph readback and live
checkpoint publication remain later integration gates.
Independent EGM and C08 parent acceptance are pending.
No live MLX model, optimizer, checkpoint, private source or
network transport was changed.
