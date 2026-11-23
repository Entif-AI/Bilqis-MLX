# Issue #1576 MLX compile qualification

Issue #1576 qualifies `mx.compile` for the stable ordinary BAMF route-training
kernel. The production default is enabled only for the qualified boundary.
Strict evidence execution and salience-supervised execution remain uncompiled.

## Boundary

`bilqis_mlx/runtime/_model/backbone/microbatch/compiled_route.py` owns the
compiled function and its process-local cache. The compiled closure contains
only route tensor math. Authority mutation, currentness checks, evidence
construction, optimizer admission, and Python persistence stay outside it.

The cache key binds semantic release, topology digest, generation extents,
concrete route shapes, and route semantics. Tests prove reuse for compatible
steps and invalidation when release, topology, extents, shape, or route changes.

## Numerical parity

Focused M3 Ultra verification at feature head
`e4ee756109ea2fa9193ebb1969d29ea12e43c300` passed 23 tests in 14.07 seconds
with compilation forced on. The set includes direct bitwise comparison of
compiled and uncompiled route loss and gradients, host-synchronization checks,
learning-first execution checks, and the uncached row-preparation regression.

The representative qualification used 32 logical rows and eight consecutive
optimizer steps per arm. Compiled and uncompiled runs produced the same:

- eight-step loss sequence;
- optimizer-state digest `db7285fd29bc1247505651ca026519d2c86426491ee19ee7589b52b27ef1f947`;
- optimizer-participation digest `a99fd74cd31afff43eb2f43ed9d4fe0a8f42850b8ca8df17a1cfc11ac5b032f5`;
- retained candidate identity `118111101bcaef3b339f742f1062b6cf4bc7c10a5b1367082f9c48a821294dd3`;
- optimizer step 8; and
- training-source coordinates.

The compiled arm recorded one cache miss followed by seven hits. The
uncompiled arm recorded no compile-cache activity.

## Performance

The matched 32-row witness reported these medians and totals:

| Metric | Uncompiled | Compiled | Difference |
| --- | ---: | ---: | ---: |
| Median candidate-step wall | 3.8216 s | 3.7026 s | 3.1% faster |
| Warm candidate-step wall | 3.8373 s | 3.6973 s | 3.6% faster |
| Warm B11 materialization wall | 1.9934 s | 1.8113 s | 9.1% faster |
| Eight-step total wall | 31.3123 s | 30.9213 s | 1.2% faster |
| MLX peak memory | 9,574,252,537 B | 9,639,709,113 B | +62.4 MiB (+0.7%) |

MLX pays compilation lazily at materialization. The first compiled
materialization took 1.7249 seconds, below the compiled warm median of 1.8113
seconds. This run therefore found no measurable positive cold-compile overhead
above run-to-run noise. Route dispatch itself remained sub-millisecond in both
arms and was not the source of the gain.

The detached run passed with source mutation protection enabled. Receipt:
`/private/tmp/bilqis-1576-qual-e4ee/run/receipt.json`. Immutable source snapshot:
`02910bf5c414e2e52355f7739316f8d143bfca296d2856f3169f3cb08aff7f45`.

## Disposition

The representative production evidence shows a small but repeatable useful
throughput gain with low memory cost and exact retained-state parity. The
qualified ordinary route-training compile boundary is therefore enabled by
default. Set `BILQIS_MLX_COMPILE_STABLE_KERNEL=0` to disable it for diagnosis or
comparison.

## Differential gate baseline

The repository differential leaf gate selected 235 test files when compared
with `origin/main`. After 41 minutes it completed with 1,088 passed, 93 skipped,
99 failed, and 28 errors. The failures are not unique to this branch.

The first collection blocker was a stale mainline test import of
`_target_source_count` from `factory_training_bridge`; pristine
`origin/main@256501bd5fa49c7497c1fec4c5e97eba7880ef61` reproduces that ImportError.
The test now imports the helper from its current owner,
`factory_training_preparation`; the repaired rehearsal module passes 8 tests.

After that repair, a representative cluster nearest the changed B11/C08 owners
was run on both pristine `origin/main` and this branch:

- `test_atlas_model_microbatch.py`
- `test_factory_training_microbatch.py`
- `test_distributed_candidate_step.py`
- `test_atlas_candidate_step_custody.py`

Both trees produced the same result: 6 failed, 6 passed, 4 skipped, and 10
subtests passed, with matching failure traces. These failures therefore predate
#1576. The branch-specific focused suite remains green, and the qualification
witness exercises the production 32-row compiled path directly.
