# B09 parent acceptance | 2026-11-11

Issue: #368 / B09, `Provision fast adapters and explicit multi-timescale plasticity`.

Lane: B.

Reviewed integration base: `edb004e8d7dd982c5761533ef017128db0144d53`.

Exact semantic/test proof head: `f2d0dab40ede4f7f3ad5b3af473b79a90a34e5cb`.

Turn-in branch: `codex/368-b09-parent-acceptance-20261111`.

## Design authority and integrated ownership

The governing BAMF lifecycle now treats pinned EGM as the pre-implementation design
gate and post-implementation acceptance as `VERIFY -> DRIFT -> PREMERGE -> HUMAN
REVIEW`. The approved design provenance is
`docs/evidence/bamf/0.2-planning/EGM_FINAL_STATUS.md`: the BAMF-0.2 implementation
contracts passed independent Google EGM review pinned at
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`. The final B09 correction R2 passed in
`docs/evidence/bamf/0.2-planning/closure.md`.

All direct B09 implementation descendants and the external owners consumed by the
parent are closed and integrated:

- B09.1a #463: accepted implementation/receipt `baf859c86e292ab5f1099cd574219f8faf0c29fb`;
- B09.1b #464: accepted cadence implementation `0a04c3c7a38f8d6a7cbae3c2f9635f2778c8edcd`;
- B09.2 #465: production-authority remediation consumed as reviewed-unified merge
  `b16941114dee33247ee9a9e6c013797b9d82af27`;
- B09.3 #466: promotion-transition merge `066c08028f1f8b6c8f7ccc36c285df0ea3c6cfba`
  plus exact policy-preservation repair `039fbcab999e290dcb3dcd9722924678a460bc4a`;
- B09.1 #462, B05 #355, and B08 #366: CLOSED / COMPLETED.

Each named implementation/repair SHA above is an ancestor of the reviewed base.

## Parent-only proof delta

The current B09 production implementation already contained the required behavior.
Fresh parent reconciliation found two test-proof fidelity gaps, both in literal parent
acceptance rather than production semantics:

1. ADR-BAMF02-004 required a real grade-ID relabel discriminator followed by the same
   B09-authoritative foundation/promotion evidence and accepted-candidate history,
   ending in byte-identical parameter-group eligibility, consolidation clocks, and
   cold policy state.
2. BAMF-REQ-016/017 required one accepted candidate containing eight internal
   optimizer steps to age each participating identity row exactly once, with an
   equivalent rejected candidate aging zero.

The exact proof head adds one 157-line test-only file and changes no production code:
`bilqis_mlx/runtime/tests/capability/factory/retention/test_b09_parent_acceptance.py`.
The narrower historical B09.3 grade-neutrality test is unchanged from reviewed
unified.

### Literal grade-ID relabel witness

The new parent witness recompiles the same synthetic Boolean course after changing
the actual grade identifiers `A -> C` and `B -> D`. It proves that the capability
cohort is unchanged while the capability-to-grade mapping and executable-release
identity are genuinely different, so the setup cannot collapse into a visit-order
test.

At the B09 ownership boundary, grade labels are not transition authority. The test
therefore holds the accepted C05 promotion receipt, immutable foundation capability
scope, retained candidate, and accepted-candidate history fixed. From that identical
B09-authoritative state it applies the same three accepted FAST candidates,
cold-round-trips the exact `PlasticityPolicy`, derives `GroupEligibility` from the
real B01 parameter census, and compares canonical bytes for:

1. B01-derived `GroupEligibility`;
2. `accepted_fast_since_full` plus retained row-establishment ages;
3. the complete cold policy record, including the accepted `ModeTransition`.

This composes with the existing owner-level grade relabel discriminators: Factory
structure selection, A09 semantic closure, capability progression, C03 teacher/
delivery semantics, and training compilation all prove that grade names do not mint
or remove semantic, scheduling, training, or progression authority.

### Eight-internal-step maturation witness

The second parent witness uses the real `CandidateTransaction` and `candidate_step`
path with B01 decay reconciliation and owner-issued execution provenance. One
candidate executes eight internal loss-bearing optimizer steps with alternating row
participation masks. The accepted candidate advances optimizer step by eight but each
participating row's establishment age by exactly one; the rejected eight-step
candidate returns the exact parent object and advances no row age. A bounded finite
gradient is used because the inherited two-step adversary's intentionally enormous
inactive-row gradient is designed for clipping/mask stress rather than repeated
training arithmetic.

## Exact-current-unified behavioral proof

All commands below ran on the branch synchronized to reviewed unified `edb004e8`.
The tests are small synthetic/authority fixtures; no live student or full model was
started.

- New literal B09 parent file: **2/2 PASS**, 0 skipped, 0 failed, 0 errors. Peak RSS
  121,323,520 bytes.
- C05 -> B09 promotion-authority ring plus the new parent file: **14/14 PASS**, 0
  skipped, 0 failed, 0 errors. Peak RSS 133,414,912 bytes.
- Candidate-transaction owner file: **14/14 PASS**, 0 skipped, 0 failed, 0 errors.
  Peak RSS 94,420,992 bytes.
- Core B09 adapter/cadence/participation/B12 ring: **26/26 PASS**, 0 skipped, 0
  failed, 0 errors. This reusable proof covers zero-B adapter identity, literal
  rank-8 arithmetic, B01 FAST/SLOW grouping, accepted/rejected row ages, eight
  accepted FAST candidates scheduling FULL across cold readback, teacher-requested
  FULL, two distinct per-step masks, active/admitted intersection,
  mask-before-clipping, numerical-zero participant count/decay, huge masked-gradient
  removal, no-loss skip, and the production B12 participation transaction. The
  repaired proof head changes none of those production/test surfaces.
- B09 production execution-authority subset: **8/8 PASS**. The production binder
  accepts no caller-authored execution/motif facts, refuses forged FAST-over-SLOW
  reclassification, requires the exact B11 execution owner, derives group eligibility
  from the B01/policy owners, rejects caller participation facts, and prevents
  provenance replay onto another candidate/step.
- True grade-label owner discriminators: Factory structural relabel, A09 semantic
  closure relabel, and training-adapter relabel each PASS; the capability-authority
  owner file is **7/7 PASS**, including reciprocal unfinished-grade labels. C03's
  existing parent witness independently recompiles the same delivered capability
  under multiple actual grade IDs and preserves the non-diagnostic teacher/delivery
  semantics.

## Static and hosted integration proof

- parent proof file: 157 lines;
- module-size structure check: PASS, 0 violations;
- semantic boundaries: PASS;
- BAMF flow control: PASS;
- BAMF contract mirrors: **43/43 PASS**;
- Python compile and `git diff --check`: PASS;
- PR #991 hosted `portable-core`: PASS at exact semantic/test head;
- PR #991 hosted `portable`: PASS at exact semantic/test head;
- PR #991 hosted `semantic-abi-integrity`: PASS at exact semantic/test head;
- PR #991: CLEAN / MERGEABLE at exact semantic/test head.

## Inherited diagnostic outside B09

An exploratory adjacent B13 authority run produced **15 PASS / 2 ERROR**. The five
B09 execution-binder tests in that run passed. The two errors are:

1. accepted-cache fixture reload: `BAMF_BUNDLE_MISSING_OR_EXTRA_TENSORS`;
2. accepted-correction fixture publication: source-authority successor-inheritance
   rejection.

Both exact errors reproduce on pristine reviewed predecessor
`766ac5f1a94202ce1048bcda0c1a2c5cbefec642`, before the #368 branch exists. The #368
candidate has zero diff in the failing B13 test/helper/publication/custody paths. The
clean B09 production-authority subset above directly requalifies the authority seam
owned by this parent. These inherited B13 fixture diagnostics are therefore recorded
but are not represented as B09 candidate regressions or silently counted green.

## Design fidelity

Bounded post-implementation EGM drift analysis against
`docs/tasks/bamf-0.2/issues/B09.md` reports `NO_DRIFT`. The durable drift artifact is
`docs/evidence/bamf/B09/2026-11-11_DRIFT_REPORT.md`.

## Independent engineering review

A fresh independent exact-head engineering/test-fidelity review of the prior proof
head found **0 Blockers / 2 Majors / 0 Nits**, both literal proof gaps described
above, and classified production semantics as `NO_DRIFT`. Both Majors were repaired
at `f2d0dab40ede4f7f3ad5b3af473b79a90a34e5cb`.

Targeted read-only re-audit at that exact head independently verified that the
candidate diff against reviewed unified is exactly the one 157-line parent proof
file, confirmed the actual `A -> C` / `B -> D` grade-ID relabel and B09 ownership
boundary comparison, and traced the real eight-step `CandidateTransaction` through
both reject and accept. Final disposition: **0 Blockers / 0 Majors / 0 Nits**,
`NO_DRIFT`, **TURN_IN YES**. No tests were rerun by the reviewer; execution evidence
is the prime-owned exact-head proof recorded above.

## Safety / authority boundary

No live student, durable optimizer lineage, teacher, checkpoint, source state, or
neural parameter was started or mutated. No self-merge was performed. Human review
and merge remain external authority.
