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
reset an optimizer step, or invent a missing receipt merely to get past a guard.

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

## Search the living diagnostic atlas

The typed catalog is the authority for meanings and recovery. Query it directly:

```bash
python3 -m bilqis_mlx.cli explain SCHOOL.STATE.COURSE_DIGEST_MISMATCH
python3 -m bilqis_mlx.cli explain INVALID_OR_DRIFTED_SCHOOL_STATE
python3 -m bilqis_mlx.cli explain STAGED_SUCCESSOR_BINDING_REQUIRED
```

The second command is deliberately useful during migration: if one legacy code
historically collapsed several invariants, it lists every typed replacement
instead of pretending the old string identifies one diagnosis.

For source locations, the code-derived atlas indexes errors, statuses, events,
gates, and otherwise unclassified uppercase terms. From the repository root:

```bash
python3 -B scripts/operator_contract_audit.py --lookup INVALID_OR_DRIFTED_SCHOOL_STATE
python3 -B scripts/operator_contract_audit.py --lookup STAGED_SUCCESSOR_BINDING_REQUIRED
```

Use `--json` for machine-readable source locations. To inspect codes introduced
by another concurrently developed branch, pass `--source-root /path/to/that/worktree`.
The atlas distinguishes exception sites, event names, status/stop reasons,
gate names, and otherwise unclassified symbols. **An occurrence is not a
definition.** For terms not yet in the typed catalogs, the atlas deliberately
reports source locations rather than fabricating recovery instructions.

The durable `operator_contract_baseline.json` is an inventory of **existing**
string-error and numeric-guard debt, not permission to repeat it. CI checks
that baseline through `scripts/error_control_plane.py --check` and rejects
new raw error identities and opaque numeric guards. To retire a debt item,
refactor to a named domain policy or registered diagnostic; do not silently
refresh the baseline.

The generated exhaustive catalog is `docs/operations/ERROR_FIELD_MANUAL.md`;
`docs/operations/error_catalog.json` is the machine-readable form. Those files
are generated from the runtime catalogs. This shorter manual explains operator
procedure and high-value recovery patterns; it is not a second error registry.

## Source-development handoff (issue #349)

`AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED` is a **stop reason**, not evidence
of checkpoint corruption. It means currently admitted productive teaching
was exhausted and the JIT frontier had no eligible compiled successor.
The matching event is `SCHOOL_AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED`.

`STAGED_SUCCESSOR_BINDING_REQUIRED` is an **admission gate** recorded for a
candidate with no verified mapping to a precompiled executable successor.
The issue-owned run observed this gate for all 240 current frontier candidates.
The correct engineering continuation is to build and verify the
source-candidate-to-staged-successor compiler, then rerun source admission.
Do not invent source evidence, assume all candidates are invalid, or modify
the preserved student or AdamW.

## Binary sampling, audit budgets, and hidden policy numbers

The Grade-B constructor balances Boolean answers by alternating TRUE and
FALSE. An even sample count is required for equal class totals. The historical
minimum `each=4` corresponds to two examples per outcome; **it does not**
prove coverage of all operand-truth combinations. The audit's historical
`max_rounds <= 32` is a resource ceiling without a source-backed derivation
in the inspected code history. These are preserved as named, inspectable
policy choices in `bilqis_mlx/semantic_sampling.py`, not mathematical laws.

Use `sample_count_violations` and `audit_budget_violations` for pure validation,
`balanced_answer_targets` for the explicit sampling sequence, and
`missing_coverage_cases` to test *actual* semantic case coverage. The
coverage audit now raises a typed, context-rich broker diagnostic for invalid
budgets and schema mismatches. The legacy Grade-B source constructor is
still hash-bound; its historical file must not be silently rewritten merely
to centralize validation, since doing so changes the constructor release
identity and can break checkpoint compatibility.

## Adding a new hard error

Any new operator-visible error must ship with the following in the same change:

1. a typed `ErrorSpec` in `bilqis_mlx/errors/catalog.py`, using a compositional namespace;
2. exact failed-predicate context preserved at the detection boundary;
3. owner, localization/recovery keys, recovery disposition, self-heal owner, and operator steps;
4. a focused test that asserts the typed invariant and repair context;
5. an attempt at safe domain-level self-healing **before** allowing the condition to reach the CLI;
6. regenerated `ERROR_FIELD_MANUAL.md` and `error_catalog.json`;
7. a clean operator-contract ratchet. Do not refresh the baseline to admit the new string.

New code should raise through `ErrorBus.Raise(...)`. The legacy substring
classifier exists only so old failures remain survivable while they are migrated.
It is not an approved way to define a new failure.

An uppercase identifier by itself is a developer breadcrumb, not an operator recovery experience.
