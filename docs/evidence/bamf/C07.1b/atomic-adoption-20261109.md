# C07.1b typed A02 atomic adoption qualification — 2026-11-09

Issue #510. Branch `codex/510-c07-atomic-adoption-20261107`.
Reviewed unified consumed: `f8f4bbafaa87056bda8665599f81c1c5284dcfd0` (A02/#399 PR #943 merged).
Exact semantic head: `04f4fc3f6e63fb316ebb02004ae57f60973dcebf`.

Status: **IMPLEMENTATION_AND_COMPOSED_PROOF_COMPLETE; INDEPENDENT_EXACT_HEAD_REVIEW_PENDING**.

## Closed production seams

1. **Real A02 handoff.** Native C07 no longer accepts a duck-typed candidate plus caller-supplied digests. It requires the owner-issued `A02StagedVocabularyExtension` and replays `require_issued_a02_staged_vocabulary_extension(...)` before admission.
2. **One current-Factory authority plane.** Native C07 no longer uses the legacy operator admission receipt as current Factory authority. `read_accepted_atlas_factory_release(...)` resolves the founding Factory release from B13 `BamfRunIdentity`, a C07 successor from accepted `AtlasAdmissionBinding`, and retained descendants through the acceptance-bound parent chain.
3. **Generic publication remains closed.** Vocabulary/active-set growth through ordinary C05/B13 retention acceptance still fails with `BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED`; only live C07 `AtlasAdmissionBinding` can cross that boundary.
4. **Precommit revalidation.** The persisted lease, exact A02 parent/feature anchors, current accepted Factory release, saved school checkpoint, frontier/proposal, and source/answer implementation descriptors are all revalidated before successor Factory artifact persistence and B13 publication.
5. **Atomic authority handoff.** The selected `ExecutableFactoryRelease` is durably persisted first, its digest is bound into the C07 admission capability, and accepted B13 publication remains the live generation commit point.
6. **Exact retry convergence.** Retry compares canonical candidate authority rather than Python equality over MLX arrays, verifies B13-normalized accepted custody and deterministic outbox event lineage, reuses the exact accepted pointer, and performs no duplicate B13 allocation.
7. **No legacy state writer.** The native composed witness proves `bamf-state.json` is the accepted generation pointer and no legacy `state.json` is created.

## Composed production-path witness

`test_factory_persist_b13_publish_cold_read_and_exact_retry` uses real B13 generation-zero publication, real Factory artifact persistence, an owner-issued A02 staged successor, real C07 binding issuance, real B13 C07 publication, cold accepted-Factory readback, and an exact retry of the same staged handoff.

The witness proves:

- Factory successor artifact exists before B13 publication completes;
- accepted generation advances exactly once to generation 1;
- cold Factory resolution returns the exact successor bound by accepted C07/B13 authority;
- the retry returns the exact same pointer;
- the BAMF bundle inventory is unchanged by retry;
- accepted candidate state survives B13 custody normalization with exact numerical authority, policy/allocation/proof authority, accepted custody identity, and deterministic outbox lineage;
- `bamf-state.json` exists and legacy `state.json` does not.

The composed witness exposed two real retry defects during qualification: unsafe dataclass equality over rehydrated MLX tensors, and false drift against B13-normalized custody/outbox state. Both were repaired and remain covered by the exact witness.

## Verification

```text
reviewed-unified conflict reconciliation ring: 16/16 PASS
expanded C07/A02/B13/custody affected ring:     55/55 PASS
composed atomic adoption/retry witness:          PASS
quality:changed structure/governance:            PASS
changed-file smell audit:                        0 findings
legacy-trainer authority + tests:                PASS
BAMF flow-control + tests:                       PASS
BAMF workstack/issue contract verifier:           43/43 PASS
git diff --check:                                PASS
```

The 55-test affected ring covers typed A02 issuance, generic B13 refusal, C07 publication, persisted-lease policy, source/answer drift refusal, JIT proposal stability, accepted Factory cold resolution, tensor CAS, cache invalidation, accepted feature authority, and cold checkpoint import behavior.

## Disposition

The former A02 dependency blocker and the legacy current-Factory preflight Major are closed at semantic head `04f4fc3f`. The requested composed Factory-persist -> B13-publish -> cold-read -> exact-retry proof is present and green.

Fresh independent exact-head review remains required before normal human-review PR turn-in. No self-merge is authorized. No live learner, shared AdamW update, or neural workload was started by this qualification.
