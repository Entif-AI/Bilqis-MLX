# A02.1 production staging and admission-boundary correction — 2026-11-07

## Scope

- Issue: #399 — A02.1 | Allocate stable semantic banks and activate admitted identity rows
- Branch: `codex/bamf02-a-399-production-admission-20261106`
- Draft PR: #887 into `codex/bamf-unified-base-20261028`
- Reviewed integration trunk consumed: `3899649586b105b075e92f0ee3c51e80c379b473`
- Dependency authority consumed: reviewed B13 accepted-generation feature authority from #708/#809.
- Additional B13 integration repair in this branch: recursive predecessor-bearing feature lineage is rederived through the same accepted source authority so A02 does not mint a parallel factor-map authority.
- Rejected historical PR #698 lineage was not revived or used as current authority.

## Correct ownership boundary

A02 owns deterministic append-only allocation and preparation. C07 owns admission authorization and atomic adoption.

The public A02 path therefore now returns an exact `A02StagedVocabularyExtension` containing the complete `BamfBundleCandidate` plus immutable `A02VocabularyStagingReceipt`. It does **not** mint a publication capability and does **not** advance the accepted generation pointer.

The staged candidate binds:

- stable `bank * 8192 + row` ABI allocation;
- exact accepted parent generation and B13 predecessor-feature receipt;
- source-allocation digest, complete plan digest and admitted IDs;
- exact prepared extents and active-mask identity;
- zero moments/counts for newly staged identity rows;
- exact preservation of all pre-existing parameter, moment and count bytes;
- source-derived Registry mirror and conservative bank resource estimate;
- accepted active semantic ABI separately from immutable source feature-map authority.

B13 publication now fails closed with `BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED` whenever a candidate attempts to change semantic-bank count or active-set digest through ordinary retention publication. No A02-owned parameter-extension publication token remains.

## Material findings and repairs

Preflight review found material defects in the earlier turn-in. They were accepted rather than contested away:

1. **C07 authority bypass — Blocker.** The earlier `admit_vocabulary_extension()` directly minted A02 acceptance and called `publish_bamf_generation()`. C07 #380/#510 explicitly owns persisted lease authorization and atomic adoption for subsequent source-valid additions. The A02-owned publication path and its live token issuer were removed.
2. **Admission evidence replay.** The earlier acceptance design did not initially bind the entire plan payload. The staging receipt now binds the complete canonical plan digest; C07 will need to consume this exact staged evidence when its executor becomes available.
3. **Existing optimizer mutation.** Parameter-extension state issuance now rejects changes to all pre-existing parameter/moment/count rows and requires zero moments/counts for new identity rows.
4. **Generic retention bypass.** Ordinary C05 retention acceptance cannot publish a semantic-bank or active-set change; publication requires the missing C07 adoption executor instead.
5. **Recursive B13 predecessor lineage.** Reviewed B13 source-rederivation authority existed through #708/#809, but the accepted reader could not recursively reconstruct predecessor-bearing feature lineage. This branch repairs that projection while preserving source ownership.
6. **Successive A02 parent state.** The earlier path rebuilt the active set from immutable source `entry.active` flags. Accepted BAMF `PlasticityPolicy.row_ages` now supplies the admitted identity-row set, while the source snapshot remains the immutable semantic-ID/index authority. Active semantic ABI and feature-map authority remain distinct identities.

The previous claim that C07 governed only new Atlas releases was incorrect and is withdrawn. C07 explicitly governs subsequent source-valid additions under a persisted lease.

## Verification

Current cheap verification after the ownership correction:

```text
A02 staging/authority regressions: 3 passed, 0 failed, 0 skipped
A02 semantic owner suites:         11 passed, 0 failed, 2 explicit opt-in skips
changed-file smell audit:          0 findings
error-control new debt:            0
flow-control checker:              pass
git diff --check:                  pass
```

Historical note: an earlier full-topology witness completed 1/1 PASS in 336.214s after repairing a duplicate Python module identity. That witness exercised direct A02 pointer publication and therefore is **not current admission acceptance evidence** after the C07 boundary correction. It remains diagnostic history only.

The current full-topology staging witness is `test_production_staging.py`. It was run through the repository detached long-run protocol from an immutable source snapshot and passed:

```text
snapshot/source/final sha256: 83ea978691054b0eb25912f31cda9d9af8d3af805e41e3ab330ac8c113a9243f
command: env BILQIS_BAMF_FULL_WITNESS=1 python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/vocabulary/test_production_staging.py
Ran 1 test in 169.561s
OK
TEST_TOTALS total=1 passed=1 failed=0 skipped=0 errors=0
detached receipt status: PASS
returncode: 0
source_mutated: false
```

Receipt: `/private/tmp/bamf-a02-399-full-staging-20261107.receipt.json`; log: `/private/tmp/bamf-a02-399-full-staging-20261107.log`. This proves the corrected A02 staging path and fail-closed publication boundary. It does **not** prove or authorize C07 admission.

## Dependency and disposition

- #399 is **WAITING**, not complete.
- C07.1b/#510 is the required downstream owner for persisted-lease validation plus atomic adoption of the exact A02 staged candidate.
- #510 is not presently completion-ready because A09.5/#395 still lacks its required three genuinely new source-qualified candidate-to-staged-successor realizations; #395 records that as its explicit resume trigger.
- C05 leaves #501-#503 and C06 leaves #504-#507 are closed accepted; A12 is closed. The unresolved A09.5 realization breadth is the material current blocker for the C07 acceptance chain.
- PR #887 is closed unmerged under the BAMF WAITING issue/branch queue; the implementation branch remains preserved.
- Official merge-readiness EGM has **not** begun. The earlier fresh reviewers were preflight only because hosted checks were not yet green when they were launched.
- No self-merge or issue closure is authorized.
- #478 / PR #885 remains waiting on a genuinely accepted A02/C07 production receipt, not this staging receipt.
