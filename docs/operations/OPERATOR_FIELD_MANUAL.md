# Bilqis Operator Field Manual

This is the recovery manual for human-operated Bilqis training. An operator-facing
failure is not complete unless it answers four questions:

1. **What failed?** Name the exact predicate, artifact, or prerequisite.
2. **What is still safe?** State whether the durable student + AdamW checkpoint remains authoritative.
3. **What can the trainer do itself?** Retry, regenerate, defer, reconcile, or migrate automatically when that is proven safe.
4. **What must the human do?** Give a concrete neural-inert diagnostic or repair command. Never answer only with an error code.

The trainer must prefer self-healing before surfacing a hard stop. It must never
self-heal by weakening source truth, custody, checkpoint identity, optimizer ownership,
semantic identity, or graduation requirements.

## First response to any hard stop

Unless the error specifically says otherwise, preserve the run directory exactly as it
is and start with a neural-inert preflight against the **same** run directory:

```bash
npm run train -- --dry-run --resume --verify-source --run-dir <same-run-dir>
```

If the run uses the default `runs/school-mlx-v1`, `--run-dir` may be omitted.

Do not delete a bundle, copy another checkpoint over the live one, edit `state.json`,
modify the workstation state data plane directly, reset an optimizer step, or invent
a missing receipt merely to get past a guard. `state.json` may be a tiny Merkle-DAG
head rather than the full logical receipt; use `npm run storage:dag-status` for its
resolved state/data-plane status and `npm run storage:dag-migrate -- --run-dir PATH`
only while human training is stopped.

For a large existing event ledger, run `npm run storage:plane-warm-events -- --run-dir PATH`
once before resume so outbox membership starts from the shared SQLite index instead of a cold JSONL scan. `npm run storage:plane-dedupe-bundles -- --run-dir PATH` safely hardlinks byte-identical bundle payload aliases; both commands refuse an active human-training lock.

## Recovery dispositions

| Disposition | Meaning | Operator posture |
| --- | --- | --- |
| `OPERATOR_ACTION` | The command itself is incomplete or wrong. | Re-run with the exact flag/action printed by the trainer. |
| `RETRY_OR_REGENERATE` | A bounded generated work set was exhausted or empty. | The owning domain should regenerate or select another source-valid item before stopping. |
| `RECONSTRUCT_OR_RESTORE` | Required durable evidence is missing. | Rebuild only from authoritative receipts or restore the original artifact. |
| `PRESERVE_AND_DIAGNOSE` | State identity failed a structural check, but corruption is not established. | Preserve the checkpoint, run the neural-inert diagnostic, then repair the owning state/program boundary. |
| `PRESERVE_AND_REPAIR` | Identity/custody evidence actually disagrees. | Preserve evidence, repair the mismatched authority boundary, then retry. |
| `AUTHORITY_OR_POLICY_BLOCK` | The requested operation is intentionally forbidden. | Use an authorized path; do not bypass the guard. |
| `INTERNAL_RECOVERY_REQUIRED` | An internal path reached a condition it should have handled itself. | Treat it as a trainer defect. Preserve the run; fix the owner before asking the operator to retry. |
| `PRESERVE_AND_REPORT` | No safe automatic recovery is known yet. | Preserve the run and diagnose the owning boundary. Add an exact recovery entry before recurrence. |

## `INVALID_OR_DRIFTED_SCHOOL_STATE`

### What it means

The saved school state failed one of the base scheduler identity/shape checks. The
message now names the exact failed predicate. The possible checks are:

- `schema`: the state is not the supported `bilqis.mlx.letter-grade/v1` shape.
- `course_digest`: the saved curriculum identity differs from the curriculum program
  reconstructed by the current runtime.
- `stage`: the saved scheduler stage is not a legal stage.
- `active_grades`: the saved school contains no admitted grades.
- `grade_index`: the current grade index falls outside the saved active-grade list.

The most common and most important case is `course_digest`. That means **the syllabus
identity differs**, not automatically that the neural checkpoint is damaged. A source
refactor, release transition, compatibility failure, or an invocation against the wrong
run/repository can all produce that symptom.

### Safe diagnosis

Run:

```bash
npm run train -- --dry-run --resume --verify-source --run-dir <same-run-dir>
```

Then compare the `saved=` and `expected=` values printed in the blocking line.

If the default canonical school is in question, also run:

```bash
npm run status
npm run diagnostics -- --run-dir ./runs/school-mlx-v1
```

### Recovery decision

If `course_digest` differs:

1. Confirm you invoked the same repository and run directory that produced the saved state.
2. Let the compatibility/release reconstruction path select the program sealed to that state.
3. If a code change made the current program digest drift without an intended curriculum change,
   repair that code or add an explicit compatibility migration. Do **not** replace the saved digest.
4. If an intended curriculum transition changed the program identity, perform the governed
   transition/migration that creates a new receipted state with the new digest.
5. Re-run the neural-inert preflight. Only resume human training after it reports no blockers.

If `schema`, `stage`, `active_grades`, or `grade_index` differs, treat the producer of that
state as the defect. Reconstruct from the immutable generation receipt when possible rather
than hand-editing the live state.

## `COHORT_EMPTY`

This is an internal recovery failure, not a request for the operator to fabricate questions.
The cohort owner must regenerate, defer, or choose another admitted work item. If this reaches
the CLI, preserve the run and fix the internal caller before resuming.

## Adding a new hard error

Any new operator-visible error must ship with the following in the same change:

1. a stable error code;
2. the failed predicate or relevant observed/expected values in the exception text;
3. a specific entry in `bilqis_mlx/runtime/operator_recovery.py` when generic classification
   cannot provide a concrete resolution;
4. a focused regression test;
5. a field-manual entry when operator judgment or a new recovery procedure is required;
6. an attempt at safe domain-level self-healing **before** allowing the condition to reach the CLI.

An uppercase identifier by itself is a developer breadcrumb, not an operator recovery experience.
