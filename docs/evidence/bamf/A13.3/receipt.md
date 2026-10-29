# A13.3 C09 contextual invalidation | implementation receipt

- Issue: #432; parent A13 #354; Lane A
- Consumed unified trunk:
  `44f78431709ec3b8fc23f47b45d9b18f167c7354`
  (already ancestor; no no-op merge)
- Consumed A13.1 source-grant gate EGM `cba2ae4`;
  A13.2 approved projection EGM `f351334`
- Branch: `codex/bamf02-a-semantics`; candidate head pending push
- Independent EGM: `PENDING`

## Contract and bounded local invalidation

`context_eligibility.py` adds immutable
`C09ContextInvalidation`, `ContextTransition`, and
`transition_context(previous, frames, task_scope, source_frontier,
policy) -> ContextTransition`. The transition uses the A13.2
`project_context` gate and emits a local C09 invalidation
only when a previously approved digest changes or becomes held.
Initial admission, identical rechecks and input-frame
reordering do not emit invalidations.

The C09 event binds prior/new approved digest, reason codes,
principal/tenant, scope, release, policy/rights epochs,
correction generation, causal prefix and invalidated opaque
frame/member handles. It includes no source payload, private
identity, evaluator gold or external graph record.
Cross-principal, cross-tenant or cross-scope transitions fail
closed before emitting another actor's handles.

Schema versions:
`bilqis.c09-context-invalidation/v1`,
`bilqis.context-transition/v1`;
consumed `bilqis.context-approved-projection/v1`,
`bilqis.context-source-frontier/v1` and
`bilqis.context-policy/v1`.

The transition is pure and uses the visit-pinned task scope,
frontier and policy. It makes no network call, does not require
a live policy service per gradient step, and does not itself
write an outbox, invalidate a live cache or mutate a learner.
Downstream C09 owns durable delivery/consumption of the local
invalidation event.

## Prime tests

`PATH=/Users/emilie/Code/bamf-planning-20261027/.venv/bin:$PATH python -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_context_eligibility.py`:
**20 passed, 0 failed, 0 skipped**.

New literal tests verify revocation emits a stable C09 event
with previous approved handles, policy/time changes invalidate
cache identity, unchanged/reordered contexts do not invalidate,
and independent synthetic actors/scopes cannot cross-read
each other's context transitions. All prior A13.1/.2
eligibility and PUBLIC_FORMAL A/B/C fixture tests remain green.

No A13 parent integration, neural training, external outbox
delivery or source promotion is claimed.
