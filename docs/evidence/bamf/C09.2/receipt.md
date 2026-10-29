# C09.2 | Alternative corrections and learned-support requalification

Issue #517, direct predecessor C09.1 #516. Lane C branch
`codex/bamf02-c-runtime` consumed reviewed unified
`6e83c0f6618f81a6d41f82503f16a80b8e14164f` without a no-op
merge. Source implementation commit:
`be7127151d3933db5a87519fe55410edf0311f7a`.
Draft PR #550 remains human-controlled.

## Behavior and wire contracts

- `bilqis.c09.correction-branches/v1` retains concurrent incompatible
  qualified correction events as separate active alternatives. Only
  explicit, acyclic supersession retires a branch from the active
  projection; historical events remain immutable. Repeated identical
  event IDs are idempotent; divergent duplicates reject.
- `bilqis.c09.capability-support/v1` binds each learned capability
  to its exact supporting artifact IDs, source anchors, historical
  observations and retained generation identity.
- `bilqis.c09.requalification-ledger/v1` marks only capabilities
  whose support chain intersects the current correction's held or
  materially changed artifacts as REQUALIFICATION_REQUIRED.
  Unrelated capabilities remain qualified, and the old support record
  is appended to immutable history without altering neural weights.
- `bilqis.c09.targeted-source-task/v1` requests fresh work only
  from declared source anchors. `bilqis.c09.c10-invalidation-intent/v1`
  produces a stable eventID/payload digest with explicit
  `PENDING_C10` state. This is a durable C10 handoff intent,
  **not** a claim of delivered Akasha projection.
- Repeated correction application is idempotent; unrelated older
  ineligible artifacts do not contaminate the current event lineage.

## Focused evidence and integration limits

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_atlas_revalidation.py
bilqis_mlx/runtime/tests/test_error_control_plane.py`:
**15 passed, 0 failed, 0 skipped** (11 correction tests,
4 error-control tests).

The C09.2 import initially failed before implementation and then
passed. Tests cover conflicting branches, explicit supersession,
duplicate event rejection, source-targeted tasks, preserved generation
and observations, C10 intent identity, idempotency and unrelated
correction isolation. No MLX, live source, optimizer or run was opened.

Independent EGM is pending. The original C09 parent and the
actual C10 outbox/projection, source-owner A01/B07/B13/C04
qualification and learned-capability reassessment remain separate
integration gates. No claim of completed delivery or retained
learning is made.
