# B12 parent integration closeout — 2026-11-07

Issue: #370 `BAMF-0.2 B12 | Extend native AdamW custody to masked plastic groups and candidate transactions`

Lane: B

Reviewed integration base consumed at parent-audit start:
`53eba37e5c9dd6ad065b1980fa4850c484aaa624`

Reviewed integration base consumed after EGM round 1:
`58eb36bba1958e0b3ca5d6aa3080260ccac3e9a1`.
That successor contains human-merged PR #895, which removes the stale C02
caller-supplied `decay` argument and restores B01/B12 optimizer-manifest
authority at the top-level Factory candidate-step seam.

## Accepted child and dependency lineage

- B12.1 #474: human-merged PR #883, merge
  `acb47e98b3bdcdd82c8297135fc78b7f6bf5b50c`.
- B12.2 #475: human-merged PR #882, merge
  `0afb12a08848a6f2aba3b83b26f1466ea708d857`.
- B12.3 #476: human-merged PR #886, merge
  `3899649586b105b075e92f0ee3c51e80c379b473`.
- B12.4 #477: human-merged PR #892, merge
  `db7fd553a2e5deac65574851a16f34e8303a1b90`.
- B11 #369 remains an open integration parent, but the exact production B11
  gradient-execution seam consumed by B12 is present on reviewed unified through
  human-merged PR #809, merge
  `b16941114dee33247ee9a9e6c013797b9d82af27`. The B12 child contracts expressly
  permit consumption of an exact usable dependency receipt while the dependency
  integration parent remains open.

## Parent-integration defect found and repaired

The first aggregate B12 run found one stale regression, not a production-authority
failure:

`test_direct_public_step_with_real_b11_authority_still_uses_b01_decay`

failed before reaching B12 because its fixture still called the B11 training
authority issuer with the old two-argument form. The current B11 authority requires
the source delivery provenance object and verifies its source-row content digest,
source-family ID, and episode ID.

The repair updates only that regression fixture. It supplies the canonical
`source_content_digest((source_row,))` in `BamfDeliveryProvenance` and passes the
same provenance to the B11 authority issuer. No production API, validation rule, or
source-authority boundary was weakened.

Failing-before aggregate result: 52 total, 51 passed, 1 error.

Passing-after direct candidate-transaction result: 14/14 passed.

## Original B12 acceptance reconciliation

The original parent acceptance is exercised on the current integrated owners as
follows:

| Parent acceptance | Current executable witness |
| --- | --- |
| FULL step matches existing native AdamW on identical arrays | `test_whole_tensor_step_is_exact_native_mlx_adamw` |
| Two FAST steps followed by FULL preserve local bias-correction counts | `test_two_fast_then_full_preserves_row_local_history` |
| Frozen rows remain bit-identical | `test_divergent_row_counts_match_independent_native_rows_and_freeze_others`; `test_frozen_max_count_and_parent_moments_preserved` |
| First update of a new row uses count 1 | `test_b09_bridge_drives_b12_zero_gradient_count_and_decay`; parent denominator witness below |
| Rejection restores all hashes/clocks | `test_rejection_returns_exact_parent_with_all_custody` |
| Nonfinite/NaN gradient rejects without partial publication | `test_invalid_masks_nonfinite_gradient_and_count_overflow_fail_without_mutation` |
| Unused motif row is byte-identical after an update | `test_unused_motif_row_is_byte_identical_after_b12_update`; production witness `test_output_denominator_and_motif_read_reach_real_transaction` |
| Output-only semantic row receives denominator update | `test_loss_owner_records_denominators_feedback_and_role_reads`; `test_output_only_semantic_denominator_row_updates_through_b12`; production witness `test_output_denominator_and_motif_read_reach_real_transaction` |
| Huge frozen gradients cannot alter active clipping factor | `test_mask_precedes_global_clip_even_for_huge_frozen_gradients`; `test_mask_is_applied_before_clipping_and_huge_inactive_gradient_vanishes` |
| Zero-gradient participating and never-participating rows have distinct clocks/decay | `test_zero_gradient_participates_but_frozen_and_no_loss_preserve_objects`; `test_b09_bridge_drives_b12_zero_gradient_count_and_decay` |
| Multi-step rejection preserves all ages/counts | `test_rejection_returns_exact_parent_with_all_custody`; `test_acceptance_moves_entire_state_and_ages_once_for_two_steps` provides the accepted contrast |

Two parent-level numerical witnesses were added because the prior leaf/component
tests proved their ingredients separately but did not assert the combined B09/B12
observable outcomes required by the parent text:

1. an identity row present only in the legal semantic denominator receives the
   optimizer update/count while an unrelated identity row remains unchanged; and
2. a motif row that was not actually read remains byte-identical in parameters,
   first/second moments, and update count while another motif row is updated.

EGM round 1 correctly found that those two witnesses stopped one ownership layer
too low: they manually composed participation/mask/AdamW primitives, so they could
remain green if the production B11 -> B09 -> B12 seam dropped execution facts.
The repair therefore adds
`test_output_denominator_and_motif_read_reach_real_transaction`, which
uses a B11-owner-issued loss/gradient execution, the real
`production_candidate_step`, the real B09 execution-provenance binder, and the
real B12 candidate transaction. It proves in one executable path that an
output-only denominator identity row and an actually-read motif row update/count,
while an unrelated identity row and unread motif row remain byte-identical even
when their supplied gradients are enormous.

## EGM round 1 | failed candidate and full repair set

Exact reviewed candidate:
`54e0b07eb1beafbfea712a476140d45e2b937344` against reviewed unified
`53eba37e5c9dd6ad065b1980fa4850c484aaa624`.

Three independent Studio reviewers returned **FAIL** with **0 Blockers / 1 Major
/ 0 Nits each**. Their reports collapsed to two unique integration defects:

1. The top-level C02 Factory candidate-step caller still supplied the now-retired
   `decay` argument to `admit_uninterrupted_candidate_step`, violating B01/B12
   optimizer-manifest authority and causing a real `TypeError` on the production
   path. While the review was running, the independently governed C02 repair PR
   #895 landed on reviewed unified. This branch consumed that reviewed successor
   through `58eb36bba1958e0b3ca5d6aa3080260ccac3e9a1`; no sibling branch was merged
   directly.
2. The new parent acceptance witnesses did not traverse the actual B11 execution
   authority and production B09 binder before B12. The production-boundary witness
   described above closes that gap without weakening any owner.

Issue #370 was moved from `EGM-Pending` to `EGM-Failed` immediately after the
round. It returns to `EGM-Pending` only after this complete known Major set is
verified and a new exact candidate is frozen.

## Verification so far

Focused parent matrix:

`python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/model/optimization/test_atlas_optimizer.py bilqis_mlx/learning/_retention/tests/test_atlas_candidate.py bilqis_mlx/runtime/tests/model/training/test_atlas_participation.py bilqis_mlx/runtime/tests/model/training/test_b12_parent_acceptance.py bilqis_mlx/runtime/tests/model/test_atlas_model_participation.py bilqis_mlx/runtime/tests/batch/test_atlas_candidate_step.py bilqis_mlx/learning/_retention/tests/test_atlas_execution_provenance.py`

Original pre-EGM result: **56/56 PASS, zero skips/errors**. The repaired candidate
reran the same matrix with the added production-boundary witness: **57/57 PASS,
zero skips/errors**.

Top-level affected boundary check:

`python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/batch/test_atlas_candidate_step.py bilqis_mlx/runtime/tests/model/training/test_b12_production_participation.py bilqis_mlx/runtime/tests/batch/test_factory_training_bridge.py`

Result: **10 PASS, 8 environment skips, 0 failures/errors**. The eight Factory
bridge tests require the real `BILQIS_A01_ATLAS_BUNDLE` fixture, which is not
mounted in this worktree. Their reviewed-unified C02 successor was independently
proved before PR #895 merged; the non-fixture production B09/B12 boundary tests
executed here.

`BILQIS_QUALITY_BASE_REF=origin/codex/bamf-unified-base-20261028 npm run quality:changed`:
**PASS** after consuming reviewed unified `58eb36bb...`; changed-file smell audit
0 findings, governance integrity clean, legacy-trainer static authority clean,
legacy-trainer tests 6/6, BAMF flow-control clean (Lane B ACTIVE 2/6), and
flow-control tests 15/15.

Production/cold-resume custody seam:

`python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/model/test_atlas_model_forward.py bilqis_mlx/runtime/tests/custody/bamf_bundle/test_production_authority.py bilqis_mlx/runtime/tests/custody/bamf_bundle/test_cold_resume_continuation.py`

Result: **21 PASS, 2 environment skips, 0 failures/errors**. The two skipped model
forward tests require `BILQIS_ATLAS_REAL_ARTIFACT`; the production authority and
cold-resume candidate/custody paths executed successfully.

`git diff --check`: PASS.

The aggregate `npm run test:premerge` gate was also exercised. It entered the
repository-wide differential suite and exposed broad curriculum/Factory failures
well outside the B12 ownership surface. After the same failure families were
observed across multiple unrelated modules, the aggregate run was interrupted
rather than spending the rest of the gate on already-known non-B12 debt.

To distinguish inherited integration debt from a B12 regression, a disposable
detached worktree was created from the exact reviewed base
`53eba37e5c9dd6ad065b1980fa4850c484aaa624` and a representative five-file
sample was rerun there:

`bilqis_mlx/curriculum/tests/test_school.py`

`bilqis_mlx/diagnostics/tests/test_teaching_methodology.py`

`bilqis_mlx/errors/tests/test_catalog.py`

`bilqis_mlx/factory/tests/test_architecture.py`

`bilqis_mlx/runtime/tests/capability/factory/test_factory_retention_owner_adversarial.py`

Exact-base result: **85 total; 67 passed; 18 non-green (7 failures, 11
errors)**. It reproduced the same representative failures seen on the B12 parent
candidate, including school-state equality, teaching-methodology expectations,
the frozen error-catalog cardinality, Factory development-evidence policy, and
retention-owner `_source_family(..., seed=...)` incompatibilities. None of those
paths is changed by #370. They are therefore inherited reviewed-base debt, not a
B12 parent regression.

The first `quality:changed` integration gate also exposed two already-merged C02
evidence sentences that the legacy-trainer authority checker correctly treated as
ambiguous historical Prometheus-as-current-baseline language. PR #895 later landed
the C02 post-merge optimizer repair, but exact reviewed base
`58eb36bba1958e0b3ca5d6aa3080260ccac3e9a1` still reproduces those same two static
checker violations. The B12 branch therefore retains the minimal documentation-only
mechanical-conformance repair so a required whole-repository gate does not remain
red on inherited wording debt. Both sentences explicitly classify Prometheus as
historical/non-authoritative for adaptation and retain the canonical operator
lineage at
`/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`.
No C02 runtime behavior or authority contract is changed.

## Mutation boundary

This parent closeout started no persistent or human-owned trainer and performed no
neural update to a durable student. It used disposable software tests only. It did
not touch `main` and does not authorize self-merge.

Final current-unified reconciliation, integration-boundary quality/differential
checks, exact-head EGM disposition, branch SHA, PR, and hosted check readback are
recorded in the final #370 turn-in comment after they exist.
