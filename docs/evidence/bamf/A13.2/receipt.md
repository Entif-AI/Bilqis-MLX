# A13.2 immutable approved-context projections | implementation receipt

- Issue: #431; parent A13 #354; Lane A
- Consumed unified trunk:
  `44f78431709ec3b8fc23f47b45d9b18f167c7354`
  (already an ancestor; no no-op merge)
- Consumed A13.1 source-grant evidence repair: `7895cea`;
  independent EGM receipt: `cba2ae4`
- Branch: `codex/bamf02-a-semantics`; candidate SHA pending push
- Independent review: `EGM_PENDING`

## API and source boundaries

`context_eligibility.py` adds frozen
`ApprovedContextProjection` and
`project_context(frames, task_scope, source_frontier, policy)`.
The projector calls the existing A13.1 eligibility gate first,
returns ContextHold without exposing any approved handles on failure,
and binds its readout to the immutable `EligibleContext.digest`.
The projection verifies frame occurrence/content, source handle,
member handles and envelope digest against the admitted membership.
Only its `frame`, `member` and `attention_handles` accessors expose
approved records; its `cache_key` includes the complete approved
context digest and immediate dependencies.

`frame_adapters.py` adds the source-owned
`public_formal_context` constructor for registered A/B/C source
rows. It calls the existing `bind_registered_source_row`, which
rechecks the source adapter and frozen Atlas/graph contracts, before
issuing PUBLIC_FORMAL grants for exact frame/member evidence. It
is deliberately outside `context_eligibility.py` so runtime
solver import closure cannot reach source-adapter assessment
entrypoints through the pure eligibility module. Source grants are
stable and idempotent; a changed source span or source evidence
cannot reuse an existing handle with a different digest.

Input schemas: A13.1 `bilqis.context-eligibility/v1`,
`bilqis.context-source-grant/v1`, A03 frame-instance v2.
New output: `bilqis.context-approved-projection/v1`.
No new rights authority, semantic release, or neural training
permission is inferred from SOURCE_AVAILABLE.

## Literal proof

`PATH=/Users/emilie/Code/bamf-planning-20261027/.venv/bin:$PATH python -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_context_eligibility.py bilqis_mlx/semantics/tests/test_frame_adapters.py bilqis_mlx/semantics/tests/test_cognitive_operators.py`:
**43 passed, 0 failed, 0 skipped**.

The new tests verify approved-only readout, member ordering,
policy/time-sensitive cache keys, forbidden joins, future-prefix
hold without minted handles, real source-registered A/B/C PUBLIC_FORMAL
rows without NLP/network calls, deterministic re-admission, tampered
source rejection, release mismatch and source-span grant collision.

## 2026-10-28 independent review repair: first-admission authority

Goldfish reviewed immutable `e959100` and found one Blocker:
the PUBLIC_FORMAL constructor trusted a caller-replaceable
`RegisteredSourceAdapter.check` callable and caller-supplied
source span. An unverified row or backdated first-admission
span could therefore mint a fresh grant.

The repaired constructor resolves the exact canonical A/B/C
registered adapter and verifies descriptor plus every callback
identity before using its canonical checker. It pins the
source root to the repository's current formal source bundle
and rechecks the supplied graph against its canonical source
graph. It no longer accepts `source_span`: the only formal
source span is `SourceSpan(0, len(row["tokens"]))` over the
fully checked source sequence. Frame/member handles bind a
digest of source-visible ID/record/tokens, deliberately excluding
gold/assessment labels. The public formal `observed_at=0`
and `effective_from=0` values denote the explicit timeless
formal-source epoch, not an observed external event.

New negatives forge a checker while retaining a real adapter
descriptor, attempt a first-admission source-span override,
tamper the canonical row, change the release, and point at an
unverified source root. All reject without minting grants.
Focused context + adapter suites: **28 passed, 0 failed,
0 skipped**. Cumulative affected source/frame/operator tests:
**61 passed, 0 failed, 1 optional real-Atlas skip**.
Fresh independent immutable-head readback is pending.

`git diff --check` passed. Repository module-size and error-control
checks retain inherited unrelated findings. The existing
`frame_adapters.py` source-adapter import boundary is not introduced
by this leaf; the new pure runtime projector imports no source
adapter or evaluation gold.

This leaf exposes the approved interface; future B-lane attention
and A07.3 cache consumers must wire it before claiming end-to-end
neural/cache acceptance. A13 parent integration remains open.
