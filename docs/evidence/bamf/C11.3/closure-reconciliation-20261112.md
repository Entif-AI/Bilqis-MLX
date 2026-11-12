# C11.3 / #524 closure reconciliation | 2026-11-12

Issue: `#524`  
Branch: `codex/524-c11-closure-20261112`  
Reviewed unified consumed: `cc186239958eaaa3de835312734f6ddbc01221c5`

## Current authority state

The earlier C11.3 receipts predated the integrated BAMF create/resume and custody
owners. Reconciliation against current reviewed unified established:

- C11.2/#523 is closed.
- #751, the #522 create/resume mitigation, is closed and patch-equivalent in
  reviewed unified.
- A12/#364, B13/#372, C03/#376, C05/#378 and C08/#374 are closed/completed.
- C07.4 is merged and the human-started accepted `atlas-release` resume path reaches
  the restart-safe C07 flywheel through accepted custody. C07 parent #380 remains
  open only for its final real-path parent acceptance witness.
- C10.1/#519 remains open. Its projection/outbox implementation is present in
  reviewed unified, but its own acceptance record still leaves native producer and
  source/rights/evaluator qualification incomplete.

Therefore #524 can progress and its stale runbook state can be repaired now, but
final turn-in must not claim accepted production `bilqis.bamf.operator-status/v1`
issuance until that producer authority exists. The dashboard continues to preserve
`NOT MEASURED` rather than infer evidence from activity, retention counts or grade
labels.

## Current-unified proof before this documentation repair

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/presentation/tests/test_bamf_metrics.py \
  bilqis_mlx/presentation/tests/test_atlas_evidence.py \
  bilqis_mlx/presentation/tests/test_bamf_watch.py \
  bilqis_mlx/presentation/tests/test_operator_policy.py
```

Result: **18/18 PASS**.

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/presentation/operator_cli/tests/bamf_lifecycle/test_bamf_resume.py \
  bilqis_mlx/presentation/operator_cli/tests/bamf_lifecycle/test_bamf_resume_precedence.py
```

Result: **18/18 PASS**.

The first ring proves the existing C11.3 cockpit/evidence behavior remains intact.
The second proves current accepted-custody resume/conflict behavior on the exact
reviewed-unified base consumed by this branch. Neither ring claims the still-open
#380 parent witness or #519 producer qualification.

The current launch/enrollment surfaces were also exercised directly:

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/presentation/operator_cli/tests/bamf_lifecycle/test_bamf_create_resume.py \
  bilqis_mlx/presentation/operator_cli/tests/bamf_lifecycle/test_bamf_atlas_release_create.py \
  bilqis_mlx/presentation/operator_cli/tests/bamf_lifecycle/test_bamf_enrollment_failure_recovery.py
```

Result: **15/15 PASS**. This covers neural-inert fresh dry-run, generation-zero
creation, exact persisted C07 v2 lease enrollment/readback, staged-to-enrolled
resume, no silent lease renewal, fail-closed authority epochs, and failed-enrollment
recovery without generation-zero republication.

The actual npm wrapper also exposes the runbook's parser surface:

```sh
npm run train -- --help
```

Verified flags include `--dry-run`, `--resume`, `--atlas-release-manifest`,
`--atlas-admission-scope`, `--source-prefetch-workers {0,1,2}`, and
`--reserve-gib`. No learner or optimizer update was started to obtain this proof.

Additional inherited cockpit acceptance was re-run on current unified:

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/presentation/tests/test_operator_dashboard_events.py \
  bilqis_mlx/presentation/tests/renderer/test_sections.py \
  bilqis_mlx/presentation/operator_cli/tests/test_terminal.py \
  bilqis_mlx/presentation/operator_cli/tests/test_bamf_preflight.py
```

Result: **32/32 PASS**. This includes the stagnation-withheld GREW denominator,
fresh-v2 topology/manifest/parser fail-closed behavior, and operator terminal
restart semantics.

#524 also adds one literal parent-acceptance regression:

`test_zero_elapsed_and_zero_visits_render_unmeasured_rates_not_nan`

The test sets elapsed time, attempted work, retained visits and visits to zero and
requires ST/M, R/H and G/RTN to render `-`, with neither `NaN` nor infinity in the
observable dashboard. `test_bamf_metrics.py` is **7/7 PASS** with this regression.

## Acceptance reconciliation

| Original C11/C11.3 clause | Current proof | Disposition |
| --- | --- | --- |
| Candidate provenance, eligible-vs-held cohorts, delivered work, debt, promotion attempts, fresh retention and learned transfer remain separate | `test_atlas_evidence.py`, `test_bamf_metrics.py`, `test_bamf_watch.py` | Reader behavior complete; accepted production producer still pending |
| A grade label cannot manufacture priority or hide an eligible capability | grade-relabeling tests in `test_atlas_evidence.py` and `test_bamf_metrics.py` | PASS |
| Historical grade policies are lineage metadata, not active BAMF policy | `test_operator_policy.py` plus evidence-rendering tests | PASS |
| Fresh v2 and resume parse; conflicting saved topology fails before mutation | create/resume, resume-precedence and preflight rings | PASS |
| Ten retentions with no growth differ visibly from genuine improvement | `test_ten_retentions_do_not_claim_growth_or_perfect_mastery` | PASS |
| Zero elapsed time or visits never emits NaN | `test_zero_elapsed_and_zero_visits_render_unmeasured_rates_not_nan` | PASS |
| Stagnation-held active capabilities stay in the GREW denominator | `test_grew_averages_active_capabilities_including_stagnation_withheld` | PASS |
| Status is read-only | detached watcher snapshot/follow tests preserve journal bytes, mtime and directory membership | PASS |
| Runbook exposes actual create/resume and resource-custody controls | 15/15 lifecycle/enrollment/recovery ring plus real `npm run train -- --help` | PASS for command surface; no durable learner start claimed |

The only unresolved #524 acceptance is not a missing presentation behavior: it is
authority evidence. The cockpit cannot truthfully claim source/evaluator/rights-bound
production observations until an accepted owner emits or authorizes the exact
operator-status projection. #519 remains the live upstream seam for that evidence,
and #380's final parent witness must be consumed before final #524 turn-in.

## Documentation correction

`docs/operations/BAMF_0_2_RUNBOOK.md` previously described the persistent v2
lifecycle as feature-branch/pending and still named #522/B13/A12/C05 as unresolved
launch/resource dependencies. Those statements are stale on current reviewed
unified. The runbook now distinguishes:

1. integrated create/dry-run/resume, generation-zero custody, C07 enrollment and
   accepted-custody flywheel routing;
2. the explicit source-worker and disk-reserve command controls, the unchanged
   100 GiB production reserve, and the neural-inert operator boundary; and
3. the still-unqualified production producer for the optional operator-status
   evidence projection.

No source, learner, optimizer, admission, scheduling, projection, or custody
behavior changes in this reconciliation patch.
