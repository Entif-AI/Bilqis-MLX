# A02.1 production successor allocation/admission receipt — 2026-11-07

## Scope

- Issue: #399 — A02.1 | Allocate stable semantic banks and activate admitted identity rows
- Branch: `codex/bamf02-a-399-production-admission-20261106`
- Reviewed integration trunk consumed: `3899649586b105b075e92f0ee3c51e80c379b473`
- Implementation commit: `f77a37ea` (`feat(bamf): complete A02 production vocabulary admission`)
- Post-sync integrated code head before this receipt: `9dac486a06ea8a5ae70a1ec6b93afa20a2aa7bdb`
- Dependency authority consumed: reviewed B13 accepted-generation predecessor-feature authority from #708/#809, already present in reviewed unified.
- Rejected historical PR #698 lineage was not revived or used as current authority.

## Implemented outcome

A02.1 now consumes accepted B13 feature lineage to authenticate a predecessor-bearing `AtlasFeatures/v2` map before successor allocation. The production path derives and publishes an append-only vocabulary successor with:

- stable `bank * 8192 + row` ABI allocation;
- exact predecessor generation, source-allocation digest, admitted IDs and feature-map binding;
- zero moments/counts for newly admitted identity rows;
- exact preservation of all pre-existing parameter, moment and count bytes;
- source-derived Registry mirror and conservative bank resource estimate;
- immutable A02 admission decision/evidence bound to the publication capability;
- fail-closed publication so ordinary C05 retention authority cannot activate semantic rows;
- cold-readback A02 production receipt derived from accepted B13 custody.

The public predecessor guard remains fail-closed. Caller-supplied coherent digests cannot satisfy `BAMF_VOCABULARY_PREDECESSOR_FEATURE_AUTHORITY_REQUIRED`; the production owner path must supply the authenticated B13 predecessor feature context.

## Authority repairs discovered during implementation

Independent read-only review found four material authority/custody defects in the in-progress implementation. All were repaired before turn-in:

1. Replayed or mutated admission-plan evidence could ride a previously valid acceptance binding. Publication now rebinds the decision, plan, Registry mirror and resource estimate.
2. Parameter-extension issuance could preserve policy clocks while mutating existing optimizer rows. The owner-private issuer now enforces append-only optimizer state and zero new moments/counts.
3. Live `VocabularyAdmissionDecision` authority could be minted from free-form caller values. Live issuance now requires an opaque owner evaluation derived from exact A02/B13 objects.
4. Generic C05 acceptance could publish semantic bank-count/active-set changes. Publication now requires `SOURCE_PARAMETER_EXTENSION_ADMITTED` authority for vocabulary extent/active-set changes.

One reviewer proposal to require the C07 Atlas release-admission lease for this operation was contested as an authority-domain conflation. #399/#348 own activation/allocation of identities from the already admitted semantic release bound to the accepted generation and explicitly own the crash-before-pointer-publication acceptance. C07 governs adoption of new Factory/Atlas release deltas. No new C07 dependency was introduced.

## Verification

Full production witness on the pre-sync implementation:

```text
BILQIS_BAMF_FULL_WITNESS=1 python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/vocabulary/test_production_admission.py

Ran 1 test in 336.214s
OK
TEST_TOTALS total=1 passed=1 failed=0 skipped=0 errors=0
```

That witness exercised generation 0/1 source custody, rejection of an unqualified admission, crash before pointer publication, retry, generation-2 `BAMF_A02_VOCABULARY_ADMITTED` publication, and cold receipt readback. The first detached attempt failed only because the implementation imported the physical grouped `CandidateState` module path and therefore created a second Python class identity; the canonical owner-path import repair produced the passing witness. The failed detached receipt remains preserved as diagnostic history.

After merging current reviewed unified `3899649586b105b075e92f0ee3c51e80c379b473`, the smallest affected checks were rerun:

```text
authority/capability regressions: 4 passed, 0 failed, 0 skipped
A02 semantic owner suites:        11 passed, 0 failed, 2 explicit opt-in skips
tensor CAS + cold resume:         14 passed, 0 failed, 0 skipped
git diff --check:                 pass
```

The consumed unified delta refactors optimizer update-count shape selection through `declared_update_count_shape` without changing identity-bank rowwise count geometry; the post-sync focused custody checks pass.

## Turn-in disposition

- Implementation: complete for the #399-owned production successor allocation/admission boundary.
- EGM: `EGM_PENDING` at turn-in. The fresh reviewer should review the immutable final PR head, not an uncommitted worktree.
- Self-merge: not authorized.
- Issue closure: do not close #399 until independent EGM/hosted checks and human/integration acceptance are satisfied.
- Downstream: this receipt is intended to satisfy the A02 production-receipt dependency recorded by #478 / PR #885 once #399 is accepted.
