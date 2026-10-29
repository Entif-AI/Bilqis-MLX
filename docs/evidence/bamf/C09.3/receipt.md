# C09.3 | Bitemporal validity and stale-remediation escalation

Issue #518, predecessor C09.2 #517, parent C09 #377.
Lane C branch `codex/bamf02-c-runtime` consumed reviewed unified
`6e83c0f6618f81a6d41f82503f16a80b8e14164f`.
Implementation commit:
`1b7d797a4bd97275b0662a93155e69c7cdb24b5c`.
Draft PR #550 remains unmerged.

## Exact owned behavior

- `bilqis.c09.temporal-event/v1` distinguishes source time,
  effective interval, observation and recording time, plus explicit
  event kinds PLANNED, OBSERVED, EXPLICIT_NONOCCURRENCE and CORRECTION.
- `project_as_of` uses only recorded/effective evidence at the
  requested time. It distinguishes an upcoming plan, an overdue
  missing report, an explicit negative event, a later correction,
  expiry and conflicting alternatives. Future recorded events do
  not leak into earlier projections.
- `bilqis.c09.temporal-projection/v1` binds a deterministic
  source-scoped TIME dependency to known validity boundaries and
  current interval. `bind_as_of_dependency` replaces only that
  actor's prior boundary on an immutable artifact, enabling exact
  reverse-edge invalidation when validity changes.
- `bilqis.c09.remediation-receipt/v1` and
  `bilqis.c09.derived-claim/v1` retain original source event/time,
  superseded evidence, correction receipt, completed remediation
  attempt and ordered derived path.
- A stale replay **after** reported remediation completion and
  along the affected lineage produces
  `bilqis.c09.process-fault/v1` with registered
  `SCHOOL.BAMF_REVALIDATION.PROPAGATION_FAILURE`. Unsafe descendants
  are held, and learned support enters source-targeted
  REQUALIFICATION_REQUIRED without touching retained generations.
  Relabeling a stale source event ID does not evade detection;
  genuinely new source evidence and unrelated paths do not fault.

## Verification and remaining authority gates

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_atlas_revalidation.py
bilqis_mlx/runtime/tests/test_error_control_plane.py`:
**17 passed, 0 failed, 0 skipped** (13 C09 tests, 4 error-control).

The test suite asserts literal 09:30 plan, missing expected report,
explicit non-occurrence, 10:20 correction, post-remediation stale
replay, source-event-ID relabeling, later independent actor/evidence,
as-of expiry, time-dependency replacement, held descendant chain
and unchanged historical generation IDs. Static scans found no new
C09-specific error-control or module-size debt.

This is a public synthetic source-authority seam. Actual source
receipt authentication, C10 durable outbox/Akasha projection,
upstream A01/B07/B13/C04 and full C09 parent integration remain
pending. The new C09.3 helper module separates temporal and
process-fault semantics from the existing C09.1/.2 revalidation
owner. Independent EGM is pending. No live neural run, optimizer
mutation, source-rights expansion, private data or merge occurred.
