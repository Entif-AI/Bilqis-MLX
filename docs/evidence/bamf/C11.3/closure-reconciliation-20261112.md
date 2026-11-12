# C11.3 / #524 closure reconciliation | 2026-11-12

Issue: `#524`
Branch: `codex/524-c11-closure-20261112`
Initial reviewed unified: `cc186239958eaaa3de835312734f6ddbc01221c5`
Current reviewed unified consumed: `c672c62113108695a2a60cd0eb0d7f19d085f838`

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
- C16.3/#545 and its C03.4b authority leaf #1010 are now closed/completed and merged
  through reviewed unified `c672c621...`. The same human resume command can enter the
  persistent BAMF-native operator without routing through the legacy `state.json`
  trainer.
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

## C16.3 integration defect found during #524 reconciliation

After C16.3 merged, current dispatch had one cross-owner launch defect for leased
lineages. A staged BAMF resume returning `READY_TO_RESUME` entered
`operate_bamf(...)`, but an accepted `atlas-release` resume returned the C07 flywheel
terminal status directly and never entered the persistent operator. That meant the
lease intended to authorize future Factory deltas could permanently strand the
already-authorized neural writer behind admission-only control flow.

Failing-before regression:

`test_human_resume_with_saved_atlas_lease_replans_then_continues_learning`

Before repair the resume file ran **13 pass / 1 error**. The new case received the
flywheel lifecycle record instead of an operator result and failed with
`KeyError: 'status'`; the patched `operate_bamf` was never reached.

The #524 repair changes only the CLI composition boundary. Human non-dry resume now
continues into `operate_bamf` after these safe C07 terminals:

- `FIXED_POINT`
- `WAITING_FOR_EVIDENCE`
- `IMPLEMENTATION_UNCOVERED`
- `LEASE_REQUIRED`

The operator output preserves the preceding flywheel status as `admission_status`.
`HELD` is deliberately excluded because C07 currently uses it both for ordinary
source holds and for integrity failures such as binding drift; without a more
specific typed distinction, learning must fail closed. A sibling regression proves
ambiguous `HELD` does not enter the operator.

Passing-after proof on the merged C16.3 tree:

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/presentation/operator_cli/tests/bamf_lifecycle/test_bamf_resume.py \
  bilqis_mlx/runtime/tests/operator/test_bamf_operator_session.py
```

Result: **20/20 PASS**.

Resource-command reconciliation also found that C16.3 does not consume the legacy
`--source-prefetch-workers` value. The native operator receives exact C03.4-selected
source offers/rows and therefore starts zero independent prefetch workers. The
runbook now says so explicitly instead of presenting that compatibility flag as an
active BAMF resource control. `--minutes`, `--max-visits`, and `--reserve-gib` are
the actual current persistent-session controls consumed by C16.3.

The post-C16.3 preflight ring also exposed one inherited stale assertion: the parser
help now correctly says BAMF create/enrollment remain neural-inert while an accepted
human `--resume` may enter the persistent BAMF-native learner, but
`test_train_help_preserves_operator_descriptions_after_parser_factoring` still
expected the pre-C16.3 text saying BAMF v2 remained wholly neural-inert. The exact
failure reproduces on pristine reviewed unified `c672c621...` at **17 pass / 1
fail**. #524 updates only that expected help string to the already-landed contract;
it does not weaken a behavioral assertion or change parser behavior.

The C16.3 dashboard delta also changed state routing so a `bamf-state.json` pointer
is checked for a persistent accepted generation before falling back to the
generation-zero foundation projection. The pre-existing dashboard test still used
an empty directory while asserting the foundation loader was called, so it fails on
pristine `c672c621...` at **7 pass / 1 fail** even though an empty directory has no
BAMF pointer to project. #524 updates that regression to model the new routing
boundary explicitly: a pointer is present, the accepted-generation probe reports
generation zero, and the lightweight foundation projection is then consumed. The
test continues to prove no legacy `state.json` is created.

## C10.1 upstream qualification remains a real gate

The #519 issue comment is old, but the missing producer authority is not merely stale
bookkeeping. Current reviewed unified still classifies `BANK_ALLOCATION`,
`PLASTICITY_EPOCH`, and `PACKAGE_EXPORT` as `OWNER_FIXTURE_KINDS`. Their wire payload
is valid only with `verification_mode=DISPOSABLE_CONTRACT`; attempting
`verification_mode=PRODUCTION` rejects. Public staging also rejects these fixture
categories until a versioned public maturity schema exists. The native generation
adapter does cover accepted teacher visits, Factory release changes, and capability
outcomes, but that does not silently promote the fixture-only categories or mint
source/rights/evaluator authority for them.

Current-tree proof:

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/projection/test_owner_receipt_fixture.py \
  bilqis_mlx/runtime/tests/projection/test_generation_projection.py \
  bilqis_mlx/runtime/tests/projection/test_bamf_projection.py
```

Result: **12/12 PASS**. The passing fixture tests explicitly prove that production
mode and public staging remain forbidden for the three immature owner categories.
Therefore #519 remains a genuine upstream qualification gate for full C10/C11
production projection claims; #524 must not paper over it with a synthetic cockpit
producer.

## Final current-tree proof for this checkpoint

On the exact #524 working tree after consuming reviewed unified `c672c621...`:

- persistent dashboard / GREW / terminal ring: **14/14 PASS**;
- C11.3 cockpit/evidence/watcher/policy ring: **19/19 PASS**;
- resume / precedence / C16.3 operator ring: **24/24 PASS**;
- create / atlas-release enrollment / recovery ring: **15/15 PASS**;
- preflight plus exact lifecycle wire ring: **19/19 PASS**;
- disposable first-start composition witness: **1/1 PASS**;
- C10 projection / native-generation / fixture-maturity ring: **12/12 PASS**.

Total bounded selections in this final proof: **104/104 PASS**. No durable student
or live optimizer session was started.

Repository gates on the same tree:

- changed-module structure: PASS, zero violations;
- changed-file smell audit: zero findings;
- Factory architecture: PASS;
- docs: PASS;
- governance integrity: zero violations;
- error control plane: zero new debt;
- `git diff --check`: PASS.

Fresh independent review of the leased-resume composition and updated C11.3 docs
finished at **0 Blockers / 0 Majors / 0 Minors**. The reviewer separately confirmed
that the four safe flywheel terminals may preserve already-authorized learning,
`HELD` must remain fail-closed because it also represents integrity drift, ADOPTED
custody is cold-reloaded before C16.3 execution, and the additive
`admission_status` field does not change the exact lifecycle-report wire.

## Documentation correction

`docs/operations/BAMF_0_2_RUNBOOK.md` previously described the persistent v2
lifecycle as feature-branch/pending and still named #522/B13/A12/C05 as unresolved
launch/resource dependencies. Those statements are stale on current reviewed
unified. The runbook now distinguishes:

1. integrated create/dry-run/resume, generation-zero custody, C07 enrollment and
   accepted-custody flywheel routing;
2. neural-inert create/enrollment versus the explicitly human-started persistent
   resume boundary, together with its real time/visit/disk controls and unchanged
   100 GiB production reserve; and
3. the still-unqualified production producer for the optional operator-status
   evidence projection.

The production-code change in this reconciliation patch is deliberately narrow: it
composes the already-landed C07 flywheel with the already-landed C16.3 operator so a
safe admission terminal no longer suppresses already-authorized learning. It does
not create source/rights authority, alter C07 admission decisions, change optimizer
arithmetic or C03 scheduling, weaken B13 custody, or start a durable student during
verification.
