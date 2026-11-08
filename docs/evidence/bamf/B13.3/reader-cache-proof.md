# B13.3 disposable-cache and historical-v1 custody proof

Issue #480 / B13.3. Parent #372. Authority: IPR-0220.

This receipt supersedes the 2026-11-02 proof staged on the preserved branch
`codex/bamf02-b13-3-480-cache-custody-20261102`. The old branch remains
provenance. It is not the current implementation base.

## Current basis

The replacement candidate now consumes reviewed unified
`9795a3edff705ff6e44eec29dc60fed74d2abc74`. The B13.3 candidate was
merge-forwarded after its clean round-3 EGM because reviewed unified advanced
through #516. That merge changes C09/context-correction authority and Lane-A
flow metadata; it does not change the B13.3 cache, publication, historical-v1
reader, focused-test, or Microspenics source surfaces named below.

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

The model-swap case repeats the same custody path through the production
`MODEL_SWAP` classifier, accepted-runtime authority and `AttentionCache`
validation with a controlled alternate topology identity and changed query
tensor. BAMF-0.2 currently admits one frozen `ModelTopologySpecV2`, so the test
uses an identity-only test variant to exercise the fail-closed transition
contract. It does not claim that a second production topology is currently
admitted.

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

After merge-forwarding reviewed unified `9795a3ed...`, the exact candidate
`5eb62d5e5e16fbdf15ac0d715b17fe29ec545c34` was rerun on the M3 Ultra with the
repository's dependency-complete Python environment. The combined current
`test_cache_separation.py` + `test_cold_resume_continuation.py` surface passed
**10/10**, with zero failures, skips, or errors. That exact rerun includes both
transition/cache tests and all eight cold-continuation tests.

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

The canonical Microspenics witness was rerun after the final unified merge-forward
at `5eb62d5e5e16fbdf15ac0d715b17fe29ec545c34`: **1/1 PASS**, zero failures,
skips, or errors. Live legacy-authority verification at the same head reports
branch `codex/337-replay-349-20261026`, source head
`d84d2ab9e2d79817c131ef7e0d4ec0d574e57b32`, generation `24254`, and state
schema `bilqis.state-head/v1`.

The source bytes were read only. No archive copy, checkpoint publication, cache
repair, optimizer step, or neural update occurred.

The original fresh neural/custody witnesses are bound to semantic/test head
`9d1bc1c8c753031f0642c60b0f85c8e2d0edb812`. Later changes in this #480
reconciliation branch are limited to this evidence receipt and Lane-B flow-control
bookkeeping until the merge-forward to reviewed unified `9795a3ed...`. The
merge-forward changes no B13.3 production/test path or Microspenics source input.
The focused B13.3 witnesses are therefore rerun on the merge-forwarded candidate;
the earlier proof remains historical evidence rather than a substitute for that
exact-head rerun.

## Acceptance disposition

The two B13.3 owned clauses are measured on current reviewed code:

- inference caches are disposable across accepted `PARAMETER_EXTENSION`
  transitions, and the production `MODEL_SWAP` classifier/cache contract
  rejects predecessor cache state under a controlled alternate topology
  identity;
- historical v1 bundles retain their reader, remain immutable, and fail closed
  before BAMF-v2 construction.

The current proof also consumes #479's accepted-generation and cold-resume custody
instead of treating a synthetic direct save/load as production authority.

No live Bilqis student, own AdamW, teacher, source release, or human-run state was
mutated. Parent #372 retains its broader integration acceptance.

Round-3 whole-candidate EGM passed at `248b30e70d52964363ed01d6fedf4ca15dacc0dd`
with 0 Blockers / 0 Majors / 0 Nits from both required fresh Goldfish personas.
Because reviewed unified subsequently advanced and was merge-forwarded, the final
merge-forwarded candidate receives a new exact-head focused witness and Goldfish
round before #480 turn-in.

## Current owner and verification map

The original B13.3 packet preserves pre-refactor paths as historical ownership
provenance. Current reviewed-unified ownership is:

- historical v1 bundle reader:
  `bilqis_mlx/runtime/_custody/mlx_checkpoint.py:load_bundle`;
- generation transition classification/publication:
  `bilqis_mlx/runtime/_custody/bamf_bundle/publication.py`;
- transition and sidecar contracts:
  `bilqis_mlx/runtime/_custody/bamf_bundle/records.py`;
- accepted execution-cache reissue:
  `bilqis_mlx/runtime/_custody/bamf_bundle/accepted_runtime.py` and
  `execution_cache.py`;
- accepted BAMF generation pointer lock/read/atomic promotion:
  `bilqis_mlx/runtime/_custody/bamf_bundle/_publication_storage.py`,
  consumed by `bilqis_mlx/runtime/_custody/bamf_bundle/publication.py`;
- focused tests:
  `bilqis_mlx/runtime/tests/custody/bamf_bundle/test_cache_separation.py`,
  `test_cold_resume_continuation.py`, and `test_frozen_v1.py`.

The broader predecessor checkpoint boundary owner remains
`bilqis_mlx/runtime/_custody/boundary_commit.py`; B13.3's accepted-generation
pointer publication does not route through that module.

The current first verification command is:

`python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle/test_cache_separation.py bilqis_mlx/runtime/tests/custody/bamf_bundle/test_cold_resume_continuation.py`

The historical-v1 witness is run separately with the explicit canonical
Microspenics bundle path and manifest digest. This remaps current ownership and
test entrypoints only; it does not change the inherited B13.3 requirements or
acceptance contract.

Exact M3 Ultra witness command:

`BILQIS_FROZEN_V1_BUNDLE=/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay/bundles/best-18601-70d09abe56ca BILQIS_FROZEN_V1_MANIFEST_SHA256=70cb9169b8bcae85cd4ea6db81c4e88eb9c423d82888af1f6b4e00c26419315d python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle/test_frozen_v1.py`
