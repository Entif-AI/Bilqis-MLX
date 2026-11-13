# A13.3 C09 contextual invalidation | implementation receipt

- Issue: #432; parent A13 #354; Lane A
- Consumed unified trunk:
  `44f78431709ec3b8fc23f47b45d9b18f167c7354`
  (already ancestor; no no-op merge)
- Consumed A13.1 source-grant gate EGM `cba2ae4`;
  A13.2 approved projection EGM `f351334`
- Branch: `codex/bamf02-a-semantics`; candidate head pending push
- Independent EGM: **PASS**, full-issue clearance at
  `b3bea14fe241f5f11c68d11a41af3d938aebd8ae`

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

## 2026-10-28 unified sync and independent review repair

Consumed current unified `6e83c0f6618f81a6d41f82503f16a80b8e14164f`
through Lane A merge `982ba51127b7e851cd795039644565bc3625ebaa`.
Goldfish inspected immutable `982ba51` and found one Major:
the new frozen C09 invalidation/transition records lacked
boundary validators and accepted malformed digests, empty
actor/scope IDs, negative epochs, duplicate reasons/handles
and wrong schema versions while still minting event IDs.

Both records now validate at construction through the
existing ErrorBus/catalog. The invalidation enforces exact
SHA-256 digest/release identities, nonempty actor/scope,
nonnegative epochs, sorted unique nonempty reasons/handles,
and the versioned schema. A transition accepts only an
approved projection or hold, canonical unique invalidations,
and events targeting its actual current digest/hold.
An adversarial table covers malformed fields and invalid
transition shapes.

Focused context suite: **21 passed, 0 failed, 0 skipped**.
Independent Goldfish targeted readback at immutable
`d23c5999e2783a99617871dc69a1484d764d7011`
returned **PASS, zero remaining Blockers/Majors**.
The reviewer independently executed 21 focused tests from
the immutable archive and confirmed the invalidation and
transition records reject the previously accepted malformed
values. See `docs/evidence/bamf/A13/egm.md`.

## Full-issue EGM reconciliation

The separate fresh-context EGM receipt on #432
(`6486695979`) found three Majors at the original
`29f3d9b` target. The typed-boundary Major above is
cleared, but that scoped PASS did not review the other
two. The transition now also fail-closes changes of
purpose, jurisdiction and semantic release, in addition
to principal, tenant and scope, before attributing prior
approved handles to the new task. Synthetic negative
tests exercise all six authority partitions. The final
Major is PR Development closing-link/receipt metadata,
which must be verified after the code is pushed.
The full-issue independent Goldfish re-review at immutable
`b3bea14` returned **PASS, zero remaining Blockers/Majors**.
It independently executed 21/21 owner tests and verified
all six authority-partition dimensions and both typed
record validators. PR #546 Development closing references
for #432 and #411 were confirmed through GitHub GraphQL
`closingIssuesReferences`, not inferred from prose.
The PR remains draft/unmerged and parent A13 stays open.
