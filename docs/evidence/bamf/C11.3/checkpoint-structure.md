# C11.3 / #524 checkpoint custody interruption

## Current continuation — 2 November 2026

The previous scoped review missed a facade patch regression. At exact head
`f3e99245`, the lost-event-acknowledgment system proof passes only 3/4:
patching `runtime.checkpoints._record` no longer injects the expected crash into
the extracted outbox owner. The independent finding is recorded on issue #524,
comment `6571755583`, and as PM-2026-11-02-001 / RC-143 / proposed PAT-102 in the
native incident ledger. The earlier PM-2026-11-01-009 concerns diagnostic
inventory and remains a separate episode.

Merge `a5232e12` consumes reviewed unified
`5ac0e9ca2a94e11a6bbb25bcca8282af3eb8fc4e`. The canonical 228-line checkpoint
facade and its `_custody` owners replace this branch's superseded
`checkpoint_parts` extraction. Explicit callback injection preserves the late
facade lookup used by crash/replay consumers. The inherited-outbox tests return
to `runtime/tests/custody/test_inherited_outbox.py` without changed test bodies.
The generated error inventory is rebuilt from the resulting sources.

The exact prior head reproduces the failure; the merged head passes 4/4 system
proofs and 19/19 across system, inherited-outbox, cold-import and scanner tests,
with zero skips. Tests use an isolated dependency environment and disposable
run directories. No human entrypoint or existing student was invoked.
The historical proof below describes the earlier checkpoint, not the current
implementation or its review disposition. Final merge-readiness EGM remains
pending until the complete known engineering queue is clear.

This continues draft PR #699 from `e3e010c2`, on consumed unified
`3088ee02d085f2a88e53b7c78c8d9637916663fe`. Work Stack retains the paused
operator-runbook task and the remaining `operating_loop.py` interruption.

The encountered 649-line `runtime/checkpoints.py` is now 167 lines. It retains
generation advancement, persistence and orphan recovery. Imported owners cover
the shared operator-view context and append-only journal, complete bundle
staging/quarantine, retained reference validation, boundary-event construction,
signed outbox reconciliation, and publication/retirement. Every owner and focused
companion is below 240 lines. External lookup sites retain their established
facade imports, including the patchable generation/persistence entry points.

Nineteen of 22 production function bodies have identical ASTs. Three bundle
functions match after resolving four named constants to the original literal
error strings. Those constants remove duplicate error-code findings without
changing refusal text or expanding a quality baseline. Direct staging-refusal
checks verify the same historical error before any model access.

Independent review caught a related inventory defect before this repair was
committed: the generated raw-error catalog ignored named-constant raises even
though the existing debt scanner already resolved them. The catalog now reuses
that same module-string resolver. A new regression first failed with one counted
raise instead of three, then passed with literal, assigned and annotated
identities grouped together; unknown names remain unguessed. The focused scanner
selection passes 10/10. Constant extraction does not remove raw-error debt: all
four codes and their eight raise occurrences must remain in the generated
catalog. No scanner baseline or quality threshold changes. The contained near
miss is recorded as PM-2026-11-01-009 / RC-142 in the canonical native ledger.

The 221-line inherited-outbox suite moves byte-for-byte beside its outbox owner.
The 322-line teacher-capture companion splits into 237-line integration and
93-line identity files; every test/helper method keeps its original AST. Hosted
portable selection explicitly includes the new identity file, preserving those
tests in CI.

## Executed proof

Both the untouched and refactored custody selections run 42 tests: **28 pass,
14 explicit native-MLX skips**, with no failure. This Python environment has no
MLX; those skipped tests are not native custody or training acceptance.

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/checkpoint_parts/tests/test_outbox.py \
  bilqis_mlx/runtime/tests/teacher/test_teacher_observation_replay.py \
  bilqis_mlx/runtime/tests/teacher/test_teacher_observation_capture.py \
  bilqis_mlx/runtime/tests/teacher/test_capture_identity.py \
  bilqis_mlx/runtime/tests/admission/test_prepared_successor_commit.py \
  bilqis_mlx/runtime/tests/model/test_topology_lifecycle.py \
  bilqis_mlx/runtime/tests/test_historical_recovery.py
```

A separate disposable-directory witness checks that a callback installed through
the facade receives events published by the extracted outbox owner. A failing
observer still leaves the event durably journaled; replay adds no duplicate.
The ContextVar remains one shared object, with its original name and lifetime.

Fresh independent read-only code review found no concrete missing import or
custody, event-identity or publication-order regression in the scoped files.
The reviewer read the pinned Google EGM Codex integration and supplied personas
at `b3a35956759bf7f024af2ff061b2e0b44b438e4c`. This code-review receipt does
not claim that native tests were independently run or that a full EGM document
audit was completed.

This is a structural repair. It does not change checkpoint locks, own-AdamW
readback/fsync, signed inherited-outbox validation, read-only reconciliation,
source authority or retirement policy. No durable learner operation occurred.
IPR-0220 remains an opaque source authority; full #524/#384 acceptance is open.
