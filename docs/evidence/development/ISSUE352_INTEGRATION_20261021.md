# Main integration and runtime ownership — 2026-10-21

Working branch: `codex/352-main-integration-20261021`, forked from
`bb71d6dff50ee89b1d891cf1d8cb8ab915b5a55e` in the existing managed worktree.
The original #349 branch remains unchanged. A separately pushed preservation
branch, `codex/349-preserved-before-352-20261021`, names the same source commit.
Integration merge `bc6e6b3` includes main
`2327c42f323d10f4444b2c3932e4bdacc15b29e0`. No main promotion is authorized here.
IPR-0220 and execution issues 349/352 remain open.

## Reconciled behavior

- Main's durable outbox-source checks govern generation advancement. Metadata
  advances publish their own generation-bound event; transient copies cannot
  publish altered prior intent.
- Main's profile-transition, championship-reset and adoption-receipt helpers
  own adoption. JIT supplies a verified precompiled successor to those same
  transactions, including the existing student/own-AdamW catalog-growth path.
- The operating loop retains automatic JIT staging/adoption, current-parent
  frontier refresh, bounded remediation and source-development fallback.
  Main's elapsed no-progress/stagnation timing remains in the exam path.
- `generated_assessment.verify_stored_cohort` owns v1/v2 reconstruction.
  Diagnostics pass source/scope expectations through that verifier. Rubric
  identity remains distinct from the v2 storage envelope and release identity.
- Assessment validation uses the scope actually measured, even if quarantine
  changes afterward. A v2 release can generate a new source's rows without a
  historical compatibility Course. The legacy Course is required only by the
  legacy generation path.
- Source prefetch consistently uses `executable_release` for fresh, rehearsal,
  fragile-preservation and optional-enrichment draws. Worker authority remains
  source-only; the student, AdamW and teacher remain serialized.
- Typed ErrorBus classification feeds the richer recovery catalog, explanation,
  safe-check and field-manual interface.
- Thin JIT profiles may skip unrelated inactive grades while preserving typed
  prerequisite closure. The existing A-to-D factory test exercises this case.

## Ownership after extraction

`trainer.py` is a 303-line import facade preserving existing importable symbols.
119 of the 120 moved functions have identical normalized ASTs after resolving
qualified dependency names; the operating loop uses the equivalent repository
root owner and an explicit compatibility-inventory helper.
Domain services do not import the facade. Dependency calls resolve through the
owning modules, so tests patch actual owners instead of an orchestration namespace.

| Owner | Responsibility |
| --- | --- |
| `runtime/session.py` | Locking, source preparation, init/resume and session limits |
| `runtime/checkpoints.py` | Immutable state, bundles, custody, outbox and publication |
| `runtime/release_adoption.py` | Release migration, profile/catalog/JIT transactions |
| `runtime/reconciliation.py` | Source-context, vocabulary, retention and stagnation repair |
| `runtime/candidate_evidence.py` | Fresh/fixed retention panels and preservation rows |
| `runtime/visits.py` | Source-grounded teaching visit execution |
| `runtime/exam_execution.py` | Routine, promotion and generalization orchestration |
| `runtime/frontier_refresh.py` | Current-parent inference over unchanged frontier questions |
| `runtime/boundary_commit.py` | Scored checkpoint and stop-boundary commit |
| `runtime/operating_loop.py` | Serialized phase dispatch and operator session |
| `learning/student_ops.py` | MLX batches, inference and optimizer primitive |
| `learning/lesson_guidance.py` | Lesson selection and frozen mentor guidance |
| `learning/championship_runtime.py` | Fresh title/battery/fanout orchestration |

## Size and debt disposition

The largest extracted module is 822 lines. `operate` (786 lines), `_take_visit`
(603) and `_take_exam` (446) retain their existing imperative ordering in this
behavior-preserving extraction. Their cross-domain helpers now have explicit
owners. Further phase extraction is recorded debt; this change does not claim
that those functions are small.

The scheduler remains 1,061 lines: its state transitions and measured-scope
validation share one scheduling contract. This is below the hard module gate;
no new scheduler responsibility was added. Factory autonomy remains 1,196 lines
and presentation modules remain separate follow-up decomposition work. Their
sizes are visible in ordinary verification output.

`check_module_size.py` reports modules at 800 and functions at 150 lines. It fails
new or worsened module/function violations at 1,200/300 lines. The baseline is
measured at the integration merge; existing trainer function debt follows its
new owner. Tests/vendor/generated exports/fixtures are explicitly excluded.
The check runs in `quality:check` and portable CI. An empty-baseline negative
control rejects inherited hard-limit debt; the preserved baseline accepts zero
growth. The factory architecture guard follows facade imports statically and
rejects a leaf importing the trainer.

Smell fingerprints were relocated only for unchanged functions/error identities.
The unified operator ratchet predates newer main changes and already failed on
both parent snapshots: 90 inherited occurrences on #349 and 69 on main against
#349's ceiling. The integrated excess was 132 occurrences, all independently
witnessed in a frozen parent. The explicit inherited-debt receipt records every
increment; no allowance was created for an unwitnessed source occurrence. This
is baseline reconciliation, not conversion of those legacy sites to typed errors.
The regenerated error manual reflects the actual new source owners.

## Qualification boundary

Verification uses tracked test modules, full Grade B enabled and disposable
models/checkpoints only. Unrestricted filesystem discovery also found ignored
source archives under `.local`. A failing-before discovery fixture now proves
that archive copies are excluded from ordinary test discovery. The full suite
was run against the unique tracked test inventory. No canonical/historical run or
existing issue-owned experimental learner was resumed or updated.

Final totals and exact pushed code head are recorded in the issue checkpoint and
current HANDOFF. Neural learning, mastery, D admission and feature promotion
remain separate from source-integration correctness. ABI verification is advisory
without an independently supplied expected digest; no fingerprint was changed.
