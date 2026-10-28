# A13.1 source-bound context eligibility and join admission

Issue: #430
Lane: `codex/bamf02-a-semantics`
Consumed unified: `44f78431709ec3b8fc23f47b45d9b18f167c7354`
Consumed A03.3 source-authority repair: `7439f0a4483559f15da21e817fc7743a914126b8`
Consumed A04.3 frame-sidecar candidate: `55bdffae4f638b7887f5933d5616c4dfea1246ce`
Review disposition: `EGM_PENDING`

## Versioned immutable policy boundary

`bilqis_mlx/semantics/context_eligibility.py` defines typed,
frozen `ContextEligibility`, `ContextMember`, `SourceGrant`,
`SourceFrontier`, `TaskScope`, `ContextPolicy`, `ApprovedFrame`,
`EligibleContext` and `ContextHold` records. Input records bind
synthetic or source-owned principal/tenant, purpose, regime, semantic
release, jurisdiction/scope, policy and rights epochs, correction generation,
observation/effective-time frontiers and causal visibility.

`check_context_eligibility(frames, task_scope, source_frontier, policy)`
checks every frame and ordered constituent handle against the pinned source
grant frontier. It denies revoked, unknown, future, out-of-scope,
unpermitted-purpose, wrong-release and stale-rights inputs. Individually
permitted frames are still denied unless every proposed pair and the full
multi-frame join class combination is explicitly allowed. SOURCE_AVAILABLE
alone never authorizes a training-purpose view.

The approved result contains only immutable frame/constituent handles,
source-bound content and occurrence digests, permitted join classes and
the eligibility digest. The digest binds relevant grants and
policy/time/rights projections, independent of frame enumeration order,
while preserving each frame's original member order. An unrelated source
grant does not invalidate the view. Denials return only opaque source
handles, stable BAMF_CONTEXT reason codes and at most 16 bounded
reason/handle diagnostics, never raw blocked source evidence.

Malformed record shapes raise the existing registered
`SEMANTIC_FRAME.BINDING.INVALID` boundary error. This module performs no
network request, NLP call, model forward pass or optimizer update.

## Executed verification

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_context_eligibility.py`:
14 passed, 0 failed, 0 skipped after the review repair.

Literal cases cover the individually-allowed/forbidden-pair adversary,
forbidden three-frame set, revocation after a formerly valid view,
missing member grant, invisible constituent, future source, release
mismatch, unresolved purpose, rights/correction epochs, unauthorized
training purpose, malformed records, policy/time cache-identity changes
and order-invariant three-frame PUBLIC_FORMAL admission without a
network socket. Public fixtures use independent synthetic principals,
scopes and source handles.

This child establishes the policy boundary and its data contract. It
does not yet wire approved handles into A05 pooling, B08 motif reads,
neural attention, C09 invalidation or the full real A/B/C source
constructor integration. Those are separate child/integration obligations
and must not be claimed complete from this isolated proof.

Fresh independent EGM has not returned in this resumed execution.
`EGM_PENDING` is recorded for the integrator. No private source data,
neural state or historical learner was accessed or changed.

## Source-handle evidence-binding review repair

Independent Goldfish review of `926385c` identified a Blocker: source
grants were checked by opaque handle string but not by the immutable
frame/member evidence that the handle purported to authorize. The
original implementation could relabel revoked frame content under a
different still-live grant and admit it.

`SourceGrant` now carries the source-owned semantic release and
`evidence_digest`. A frame grant must match the canonical digest of
the entire immutable frame, including source instance, source span,
all role bindings and concept source references. A member grant must
match its exact frame occurrence, role/index, full source binding and
source-authorized visibility prefix. The eligibility gate compares
these digests against the trusted source frontier before emitting any
approved handle, and refuses duplicate frame/member handle reuse.
The digest functions compute identities; they do not themselves issue
permissions. Only the source frontier supplies authorized grants.

The relabelled-revoked-evidence adversary was observed incorrectly
returning `EligibleContext` before this repair. It now returns
`ContextHold` with `BAMF_CONTEXT_EVIDENCE_MISMATCH`. Additional
regressions reject source-reference substitution even when the frame
content digest stays unchanged, and backdated member visibility
under a still-live grant. The focused suite now passes 14/14.
Fresh independent review of this repaired immutable head remains
`EGM_PENDING`; no A13 parent or downstream integration is closed.
