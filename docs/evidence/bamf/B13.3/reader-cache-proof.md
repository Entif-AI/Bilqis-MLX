# B13.3 disposable-cache and historical-v1 custody proof

Issue #480 / B13.3. Parent #372. Authority: IPR-0220.

This receipt supersedes the 2026-11-02 proof staged on the preserved branch
`codex/bamf02-b13-3-480-cache-custody-20261102`. The old branch remains
provenance. It is not the current implementation base.

## Current basis

The replacement candidate consumes reviewed unified
`210b29c275dd912801cc85b2bc0aeb7e01c9e7f9`.

The dependencies that previously kept #480 waiting are now integrated:

- #754 / PR #902 supplies the production cache-transition proof and is
  EGM-Passed. Unified merge: `bd3657e170c8bdc046a7bb28524c0fb829ca7ce9`.
- #479 / PR #909 supplies complete-generation and cold-resume custody and is
  EGM-Passed. Unified merge: `cc48ac40d875f0c2ae8ffbdc70001dbfc4815334`.
- #709 is closed EGM-Passed and is consumed by #479.

The old #480 cache fixture is obsolete. It created an unrelated file beside a
bundle, then deleted it. It did not exercise a production inference cache or a
generation transition. #754 replaced that proof with the real accepted-generation
cache path.

The historical-v1 test itself remains valid. Its archive selection is external and
digest-pinned. The 2026-11-02 receipt used Prometheus, which is now historical-only
for BAMF compatibility. Current compatibility authority is Microspenics.

## Disposable inference cache

`bilqis_mlx/runtime/tests/custody/bamf_bundle/test_cache_separation.py` now
exercises accepted-generation publication and the production attention cache.

The parameter-extension case:

1. publishes an accepted generation;
2. creates an `AttentionCache` from the accepted execution authority;
3. publishes a successor classified as `PARAMETER_EXTENSION`;
4. verifies the predecessor cache is rejected under the successor generation;
5. rebuilds the cache and compares the chunked result with fresh full-prefix
   inference.

The model-swap case repeats the same custody path for a production
`MODEL_SWAP` transition with a changed topology identity and query tensor.

Fresh execution on the M3 Ultra at candidate
`9d1bc1c8c753031f0642c60b0f85c8e2d0edb812`:

- `test_published_model_swap_invalidates_real_cache_and_rebuilds`: PASS;
- `test_published_parameter_extension_invalidates_real_cache_and_rebuilds`:
  PASS;
- result: **2 passed / 0 failed / 0 skipped / 0 errors**.

No inference cache is part of the accepted-generation bundle. A transition issues
new execution authority and rejects predecessor cache state.

The current B13.2 cold-continuation suite was also executed at the same candidate.
It includes
`test_cold_continuation_reissues_cache_and_rejects_stale_or_corrupt_cache`,
which cold-loads accepted custody, reissues execution-cache authority, and rejects
stale or corrupt cache identity. The complete file passed **8/8**, with zero
failures, skips, or errors.

## Historical-v1 reader and immutable bytes

Repository authority was checked before the witness:

- `scripts/check_legacy_trainer_authority.py --live`: PASS;
- branch: `codex/337-replay-349-20261026`;
- observed source head:
  `d84d2ab9e2d79817c131ef7e0d4ec0d574e57b32`;
- run: `runs/microspenics-349-replay` under that preserved worktree;
- observed generation: `24254`;
- state schema: `bilqis.state-head/v1`.

The current Microspenics state resolves its `model_bundle` to
`bundles/best-18601-70d09abe56ca`.

The selected historical bundle has:

- schema `bilqis.mlx.fp32-adamw-bundle/v1`;
- optimizer step `135208`;
- topology schema `bilqis.mlx.model-topology/v1`;
- six layers, width 384, 24 heads and context 96;
- manifest SHA-256
  `70cb9169b8bcae85cd4ea6db81c4e88eb9c423d82888af1f6b4e00c26419315d`.

`test_frozen_v1.py` hashes every source file before the read. It loads the real
v1 student and matching AdamW through the historical reader, validates the v1
geometry, and then requires typed rejection from the BAMF-v2 paths before v2
tensor or optimizer construction. It hashes the archive again after the witness.

Fresh execution on the same exact candidate:

- **1 passed / 0 failed / 0 skipped / 0 errors**.

The source bytes were read only. No archive copy, checkpoint publication, cache
repair, optimizer step, or neural update occurred.

The fresh neural/custody witnesses are bound to semantic/test head
`9d1bc1c8c753031f0642c60b0f85c8e2d0edb812`. Later changes in this #480
reconciliation branch are limited to this evidence receipt and Lane-B flow-control
bookkeeping. They do not change production code, tests, fixtures, dependencies, or
the Microspenics source input, so the passing evidence is reused under the
repository's `TEST_EVIDENCE_REUSED` rule.

## Acceptance disposition

The two B13.3 owned clauses are measured on current reviewed code:

- inference caches are disposable across accepted `MODEL_SWAP` and
  `PARAMETER_EXTENSION` transitions;
- historical v1 bundles retain their reader, remain immutable, and fail closed
  before BAMF-v2 construction.

The current proof also consumes #479's accepted-generation and cold-resume custody
instead of treating a synthetic direct save/load as production authority.

No live Bilqis student, own AdamW, teacher, source release, or human-run state was
mutated. Parent #372 retains its broader integration acceptance.

Fresh whole-candidate pinned EGM and the repository pre-merge gate remain before
#480 turn-in.
