# B13.2 #479 completion receipt — 2026-11-07

Issue: #479 — `BAMF-0.2 B13.2 | Validate complete generation and cold-resume exact training state`

Completion branch: `codex/bamf02-b13-2-479-complete-20261107`

Reviewed unified consumed: `9301e41ef215b9d035449c3260c7cd0f8ee0b5a7`

Exact semantic/test head: `62237b4666513f7555d142d0b25fb0e001f87f81`

## Dependency closure

The two explicit resume conditions recorded for #479 are now satisfied.

1. B13.1 #478 is accepted and consumable. PR #885 was human-merged into reviewed
   unified as `9301e41ef215b9d035449c3260c7cd0f8ee0b5a7`, and issue #478 is closed
   `EGM-Passed`.
2. Remediation #709 is closed `EGM-Passed`, and its accepted pointer/lock cold-resume,
   Factory next-visit, one controlled next optimizer step, source-qualified execution
   and cross-backend continuation implementation is already in this candidate's
   reviewed-unified ancestry.

The prior #479 PR #677 remains historical provenance. Its useful complete numerical
custody witness was restored as tests only. Its stale EGM result and stale custody
implementation were not revived or treated as current acceptance evidence.

## Complete generation custody

The restored full-custody witness exercises the actual complete B01/B12 numerical
tree rather than the small synthetic helper shape:

- 214 named parameter tensors;
- 79,469,798 scalar parameters;
- weight, first-moment, second-moment and update-count trees;
- optimizer hyperparameters and optimizer step;
- row-establishment policy and motif allocation state;
- teacher cursor/seed and teacher state;
- topology/extents, semantic ABI, compiler features and correction frontier;
- provenance, evaluation contract, transition and outbox payload identity;
- all three unadmitted numerical backbone groups in a clean CPU process.

The witness freezes the expected in-memory observation before save, writes a complete
bundle through the current B13 codec, reads it in-process and in a fresh Python
process, and checks byte/dtype/shape and numerical-output equivalence. It also hashes
the bundle before and after both reads, so first read cannot silently mutate custody.

Detached exact-head result at `62237b46`:

- `BILQIS_BAMF_FULL_WITNESS=1 python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle/test_full_resume.py`
- **1 passed / 0 failed / 0 skipped / 0 errors**;
- detached receipt: `/private/tmp/bamf-479/full-resume.receipt.json`;
- source snapshot digest before/after: `72b29b1a07a8a59022ea64efd371783a8974798036adcfec42895eaedc838443`;
- `source_mutated=false`.

The adjacent mutation controls passed **3/3** on the same candidate lineage.

## Accepted-generation cold resume and next controlled step

The current accepted-custody continuation suite passed **8/8** on `62237b46`. It
loads through the published B13 generation pointer/lock path, preserves the accepted
generation identity, reconstructs Factory next-visit state, runs exactly one
controlled next optimizer step, compares uninterrupted and cold successor custody,
reissues accepted execution cache authority for the successor and rejects stale or
corrupt predecessor cache authority. A direct synthetic save/load cannot satisfy the
accepted-generation path.

## Source-qualified cross-backend continuation

The required source-qualified continuation was run detached against the accepted A01
artifact and the exact `62237b46` branch/remote head. The source arm executed on
Apple Metal and the destination cold-resume arm executed on CPU.

Exact result:

- test: `FactoryRetentionOwnerLiveTests.test_source_qualified_candidate_can_publish_then_continue`;
- **1 passed / 0 failed**;
- source backend: `APPLE_METAL`, MLX `0.31.1`, FP32;
- destination backend: `CPU`, MLX `0.31.1`, FP32;
- committed semantic output match: `true`;
- maximum observed cross-backend absolute divergence: `2.35140323638916e-05`;
- declared FP32 tolerance: `0.002`;
- accepted parent unchanged: `true`;
- no generation 2 publication: `true`;
- branch HEAD before/after and remote HEAD: `62237b4666513f7555d142d0b25fb0e001f87f81`;
- worktree clean before/after;
- detached receipt: `/private/tmp/bamf-479/source-continuation.receipt.json`.

The controlled continuation begins from accepted generation 1, preserves the
Factory release and natural next-selection evidence, executes one controlled
optimizer comparison from the same committed parent, and holds publication of the
comparison successor. No durable learner or own AdamW is started or mutated.

## Genuine historical-v1 witness

#479 consumes the genuine historical-v1 compatibility proof already accepted and
merged through #754 / PR #902 rather than substituting a synthetic archive.

That accepted exact-head proof used canonical Prometheus bundle
`best-19300-6a12407cdcad`, manifest SHA-256
`dbcddbe9647a3dba55bc5b48f67275563f288216773e9ca677f1268ce1b78ac6`, and passed
**1/1**. It verified read-only historical-v1 loading, byte preservation and typed
rejection before any v2 allocation. #754 then passed independent EGM and was merged
into reviewed unified via PR #902 at
`bd3657e170c8bdc046a7bb28524c0fb829ca7ce9`; both that merge commit and the reviewed
#754 head `beae73a57df182fd478856a340b0685d861095b1` are ancestors of this #479 candidate.

The original #434 proof remains historical corroboration. Its protected fixture
locator is no longer present in the live worktrees, so this completion does not
pretend to rerun that older private locator or relabel an unavailable archive as a
fresh local test.

## Acceptance disposition before final EGM

The implementation queue known from the prior #479 EGM is now closed on this
candidate:

- stale B13 custody/run-root defects are superseded by accepted #478 custody;
- complete-generation numerical custody is freshly measured;
- accepted pointer/lock cold resume is freshly measured;
- Factory next-visit state and one controlled next optimizer step are measured;
- the source-qualified continuation path is freshly measured;
- Metal-to-CPU FP32 continuation parity is freshly measured;
- genuine historical-v1 compatibility is consumed from accepted merged #754 proof.

Fresh pinned Goldfish remains the merge-readiness gate. This receipt does not call
#479 `EGM-Passed` before that review, and it does not authorize self-merge or a live
student start.

