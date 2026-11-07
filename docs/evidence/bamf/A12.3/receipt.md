# BAMF-0.2 A12.3 data-only successor and held-source receipt

Issue: #429
Parent: #364
Lane: A
Reviewed-unified base consumed: `7e4f92e062299909dd47b547b8b4897a189c3738`
Branch: `codex/bamf02-a12-3-429-20261105`
Disposition: implementation candidate; exact-head review and hosted acceptance required before integration.

## Owned outcome

A12.3 adds no new semantic authority and no grade-specific runtime path. The
existing generic source-grade machinery is exercised with one source-qualified,
inactive semantic identity as a data-only semantic successor. The source
snapshot already contains the identity and its stable ABI address; A02 plans one
append-only activation from that source data, A08 emits its source-constructive
positive-identity lesson, and every previously active ABI index remains
unchanged.

The executable Grade-D-equivalent half of the obligation is proved separately by
the existing generic multi-successor system witness. It compiles declarative
successors including Grade D before learner state exists, verifies ordinary
successor lineage and admission/cold replay, preserves semantic geometry and
catalog state, and performs no optimizer or neural training. Together, these two
witnesses prove that a new source-qualified semantic and a later grade successor
travel through existing generic data contracts rather than a Grade-D code path.

The held-source adversary remains fail-closed. A source-owned `SOURCE_HELD`
identity has no ABI entry, no factor-manifest concept, no active semantic/model
row, and cannot obtain a prospective feature or vocabulary allocation. Factory
lesson compilation omits it while preserving the exact source hold reason and
owner. Even a forged learner frontier claiming the identity as exposed and
qualified does not make it source-eligible or emit it as a lesson. Relabeling a
nearby admitted concept with a plausible matching English gloss does not change
the held disposition.

## Data-only successor witness

The focused A12 authority test builds from the existing source-family fixture,
not a new provider or grade branch. Its initial active set contains only the
pre-existing formal identities. The source-qualified `urn:lex:root` identity
is present in the frozen source release but inactive.

The ordinary `plan_vocabulary_extension` path produces exactly one allocation
at the source-owned ABI index and extends the active-index set by that one index.
The source lesson compiler independently emits the identity's
`positive_identity` lesson from the same frozen source data. No existing active
index changes.

This is a semantic successor witness, not learner admission. The
`VocabularyExtension` remains staged-only and no student, optimizer, checkpoint
or live curriculum state is mutated.

## Held-gloss / trainable-row witness

For the selected held source row:

- the frozen source snapshot contains no ABI entry for the held semantic ID;
- the factor manifest contains no concept row for that ID;
- the predecessor generation's active semantic IDs contain no held ID;
- direct feature lookup fails with `BAMF_FEATURE_CONCEPT_NOT_ADMITTED`;
- prospective factor planning fails with
  `BAMF_FEATURE_PROSPECTIVE_SOURCE_HELD` and preserves the source reason;
- vocabulary extension planning fails with the same source-held reason before
  any allocation can be created;
- source-constructive lessons contain no held semantic;
- Factory source-hold diagnostics preserve the exact reason and owner;
- false exposed/qualified learner claims still cannot place the held semantic
  in the source-eligible census or lesson surface.

Because trainable semantic rows are created only from verified
`VocabularyExtension.allocations`, refusal before allocation already made the
production path fail closed. A post-merge independent review nevertheless found
that #429's acceptance language requires this downstream boundary to be observed
directly rather than inferred. The follow-up boundary witness therefore forges a
held allocation request into `apply_vocabulary_extension`, proves source replay
rejects it with `BAMF_FEATURE_PROSPECTIVE_SOURCE_HELD`, preserves the exact
source reason, and proves `_stage_extension_rows` is never called.

The same review found that source-lesson omission did not literally exercise the
teacher-target construction boundary. The follow-up teacher witness supplies a
held semantic through the normal released-training adapter while preserving
source lineage and context eligibility. The Atlas feature authority rejects the
held semantic with `BAMF_FEATURE_CONCEPT_NOT_ADMITTED` and the exact
source-owned reason before `BamfTarget` construction. This closes the literal
F17 target-construction clause without modifying the production runtime.

## Reused parent acceptance evidence

A12.1 already supplied the expensive real-producer proof on the same production
chain: two independent A01 source compilations/persistences regenerated the same
release and bundle, then exercised A02 vocabulary allocation and registry mirror,
A03 frame-schema reseal, A08 lessons and the A12 authority audit. One newly
released semantic propagated through lessons and the read-only graph projection
while historical ABI indices remained unchanged.

That real two-regeneration witness passed 1/1 in 83.692 seconds and remains
applicable here. A12.3 changes only test assertions, evidence, and flow-control
custody; it does not change the source compiler, vocabulary planner, frame
schemas, lesson compiler, graph projection, audit implementation, model runtime,
or generator. Re-running the expensive proof would add cost without changing
its semantic applicability.

## Verification

Focused source/Factory/A12 surface:

```text
python3 -B scripts/run_tests.py +  bilqis_mlx/semantics/tests/test_atlas_release_audit.py +  bilqis_mlx/semantics/tests/test_atlas_release_held_gloss.py +  bilqis_mlx/factory/tests/sources/test_skos_curriculum.py +  bilqis_mlx/factory/tests/curriculum/frontier/test_candidate_staging.py +  bilqis_mlx/factory/tests/curriculum/frontier/test_jit_curriculum.py
```

Result: 19 passed, 0 failed, 0 skipped.

Generic executable Grade-D-equivalent successor:

```text
python3 -B scripts/run_tests.py tests/system/test_factory_multi_successor.py
```

Result: 1 passed, 0 failed, 0 skipped.

Post-merge literal held-boundary witnesses:

```text
python3 -B scripts/run_tests.py +  bilqis_mlx/semantics/tests/test_atlas_release_held_boundaries.py
```

Result: 2 passed, 0 failed, 0 skipped.

Additional gates:

- `python3 -B scripts/check_semantic_boundaries.py` ->
  `SEMANTIC_BOUNDARIES_OK`
- `python3 -B scripts/check_factory_architecture.py` ->
  `FACTORY_ARCHITECTURE_OK`
- `python3 -B scripts/check_bamf_flow_control.py` -> green; Lane A has one
  active leaf
- changed test-file smell audit -> 0 findings
- development-structure check -> 0 violations
- error-control plane relative to reviewed unified -> new debt 0
- docs check -> green
- `git diff --check` -> clean

## Existing-owner and parent disposition

- #295 is already CLOSED on the accepted A12.1+A12.2 combined surface.
- #309 remains a separate exact-combined-candidate integration qualification
  owner and is not silently closed by this child.
- Parent A12/#364 remains open until #429 is accepted and merged and the
  parent's complete aggregate acceptance, including any still-applicable
  existing-owner qualification, is reconciled on the resulting unified head.
- No neural training, optimizer mutation, source-gold change, private-source
  disclosure, or historical compatibility deletion occurs in this leaf.
