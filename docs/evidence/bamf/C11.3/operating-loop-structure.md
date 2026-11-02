# C11.3 / #524 operator-session structural interruption

Consumed reviewed unified: `5ac0e9ca2a94e11a6bbb25bcca8282af3eb8fc4e`.
The preserved pre-extraction source is commit `a5232e12`.

The encountered `runtime/operating_loop.py` is reduced from 842 to 193 lines.
The human entrypoint keeps its exact signature, source preparation, exclusive
operator lock, memory-policy/ExitStack lifetime and direct executable-release
check. Cohesive imported owners separate validation, profile selection, admitted
student setup, stagnation-session initialization, iteration/assessment,
autonomous dispatch, disk preflight, visit publication and final stop/archive.
Every extracted owner and focused companion is below 240 lines. The shared
checkpoint module remains the canonical imported object, preserving its patch
and observer identity. No governance guard or quality baseline is changed.

Loop helpers return explicit `DispatchControl` values for the original stop,
continue and visit paths. Their state returns preserve the original assignment
order. Setup remains split around the actual `_ensure_executable_release` call
in the facade. Native publication, retention, teacher and scheduler decisions
remain with their existing owners.

## Verification

The source-order witness is reproducible from the repository root:

```sh
python3 -B docs/evidence/bamf/C11.3/verify_operating_loop_extraction.py
python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/operator_session/tests \
  bilqis_mlx/runtime/tests/admission/test_atlas_admission_command.py \
  tests/system/test_disposable_cutover_contracts.py \
  bilqis_mlx/runtime/tests/custody/test_inherited_outbox.py \
  bilqis_mlx/runtime/tests/custody/test_checkpoint_imports.py \
  scripts/tests/test_error_inventory.py
```

The witness passes for setup, stagnation, iteration, autonomy, visit, finish,
preflight, disk, both profile helpers and the human signature. It compares the
original AST statements after reversing only the explicit control returns and
import aliases. Tokenized original comments remain present. This supplements
behavioral tests; it does not execute the human entrypoint.

The affected selection passes **38/38**, with zero skips. Literal boundary
checks cover preflight refusals, disk stop/recheck, time-limit stop, autonomy
stop/continue/proceed, missing durable delivery after flush, invalid initial
staircase, final budget refusal and final-stop output. The new tests are also
included in hosted portable verification. A separate existing compatibility,
Factory, teacher, topology and recovery selection passes **35/38**, with three
unchanged explicit source-fixture skips. Native disposable topology creation
and cold read pass; no existing student or its optimizer is used.

An isolated built wheel resolves all ten facade/session modules from its
installed directory. Its actual CLI returns HELD exit 2 and creates no run
directory. Structure, governance, architecture, documentation, staged-file
hygiene and zero-new-error-debt checks pass. Ordinary fresh-context review found
no actionable behavioral defect; reported whitespace was corrected. Final
merge-readiness EGM and exact-head hosted results are separate receipts.

The original runbook task resumes after this structural commit. Full #524/#384
production create/resume, source/evaluator/custody and learned-outcome acceptance
remain open. No durable student, own AdamW, teacher, admission, source-release
or graph state changed. Source authority remains the opaque IPR-0220 identifier.

## Hosted hygiene reconciliation

Hosted run `41465075365` rejected head `953d3da8` for four new long functions
and the witness's module-level mutable list. The earlier local changed-from
scan ran before commit and omitted added index-only files; its zero-finding
result did not cover the complete proposal. PM-2026-11-02-003 / RC-144 records
this verification-scope failure. That result is not a runtime failure claim.

The follow-up splits autonomous hold/evidence/routing, assessment, durable
teaching publication, stop recording and archive maintenance into cohesive
functions. Every new function is below the existing 80-line threshold; the
witness uses an immutable tuple. Its static inliner checks those extracted
statements against the same preserved source. Staged verification includes all
added files, and committed verification is required before push. No baseline,
threshold, exclusion or suppression is changed.
