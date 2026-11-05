# A09.5 resumed acceptance receipt — 2026-11-05

Owner issue: #395 (`BAMF-0.2 A09.5`)

## Authority consumed

- Reviewed unified base: `6e12e5a077183713241bb9b2b0d0762d8d95fa47`.
- Lane A integration base: `8019bf5d945a1d9f8f5a11983ef43fbb008a365f`.
- A08.3 #420 is closed `EGM-Passed`; its accepted rule registry supplies grade-neutral Boolean, numeric, and source-qualified world-family authority.
- The previously reviewed A09.5 implementation head `639ae85d0026c8d9e8a2cf9613944a9d78bf07f6` is consumed by this branch rather than reimplemented.

## Behavioral acceptance

The resumed acceptance uses the exact pinned A01 Atlas bundle at bundle ID
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
and source release
`58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`.

Qualified command:

```sh
BILQIS_A01_ATLAS_BUNDLE=/Users/cr8s/Code/b11-586-refresh-20261101/.local/a05-5-atlas/5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7 \
  .venv/bin/python -B scripts/run_tests.py \
  bilqis_mlx/factory/tests/curriculum/frontier/test_atlas_frontier.py \
  bilqis_mlx/factory/tests/curriculum/test_rule_registry.py \
  bilqis_mlx/factory/skos_curriculum/programs/tests/test_formal_execution.py \
  bilqis_mlx/factory/skos_curriculum/programs/tests/test_world_execution.py \
  bilqis_mlx/factory/tests/curriculum/test_world_capability_identity.py \
  tests/system/test_factory_multi_successor.py
```

Result: `17 passed, 0 failed, 1 skipped`.

Observed acceptance witnesses include:

- Boolean and numeric family rules are keyed by typed semantic identity, not grade labels.
- The qualified-world family binds its source-owned adapter and stable typed identity.
- Released Boolean and numeric programs execute under their exact pinned semantics.
- The source-qualified world program checks every row of its real batch and produces the same semantic result under another grade label.
- Six precompiled C→H successors preserve the same checkpoint across cold admission/resume, accumulate protected debt, and reach `WHOLE_SCHOOL_MASTERED` only after that debt is actually cleared.
- The A09 frontier/adapter suite separately verifies deterministic selection, staged restart custody, prerequisite-local blocking, explicit `IMPLEMENTATION_UNCOVERED`, and held/fixed-point termination.

The single skip is `test_real_pinned_a01_a08_snapshot_if_supplied`, which requires the raw precompiled source corpus through `BILQIS_ATLAS_REAL_CORPUS`; the pinned release bundle used by the executable A08.3 tests is present and was exercised. No raw-corpus substitute was invented.

## Environment

The disposable issue-worktree `.venv` contains the CI-declared semantic dependency set plus `numpy==2.4.4`; it is ignored and is not part of the candidate diff.

## Disposition

A09.5 behavioral acceptance is satisfied on the current candidate lineage. No neural training or live student mutation occurred. Fresh exact-head EGM remains required before PR creation because the accepted A08.3 dependency and current unified have changed since the prior A09.5 review.
