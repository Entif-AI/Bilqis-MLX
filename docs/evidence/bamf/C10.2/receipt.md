# C10.2 | Domain-bound, graph-independent projection outbox

Issue #520, predecessor C10.1 #519, parent C10 #378.
Lane C `codex/bamf02-c-runtime`, reviewed unified
`6e83c0f6618f81a6d41f82503f16a80b8e14164f`.
Implementation commit:
`f79001cf04a07e183a961049c91ae38c2b30e8f1`.
Draft PR #550 remains unmerged.

## Exact owned behavior

- `bilqis.c10.projection-domain/v1` binds source identity,
  source as-of, semantic release, model generation, evaluator
  and rights digests into a stable domain identity.
- `bilqis.c10.bamf-projection-event/v1` requires the same
  six identities for every event and rejects future-recorded
  events outside the requested as-of prefix.
- `project_generation_outbox` preflights all events before
  any write, rejects domain drift, deduplicates by eventID
  and canonical payload digest, and appends only to the
  local C10.1 SQLite outbox. Its receipt reports eventIDs,
  payload digests, appended/duplicate counts, pending count
  and domain digest.
- The projection function has no graph, network or SKOS
  client parameter. A graph outage cannot interrupt the
  local trainer's optimizer loop; pending events remain
  durably queued for later delivery.

## Verification and limits

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_bamf_projection.py
bilqis_mlx/runtime/tests/test_akasha_outbox.py`:
**8 passed, 0 failed, 0 skipped**.
Tests cover domain binding, rights/release/model/evaluator/as-of
drift, future prefix rejection, repeated deduplication and
graph-unavailable continuation without an external call.
No new C10-specific static error-control or module-size debt.

Actual source rights authority, C10.3 staging graph promotion,
SKOS/Akasha delivery, privacy filtering and parent C10
integration remain pending. Independent EGM is pending.
No neural state, checkpoint, private source or external
graph was modified.
