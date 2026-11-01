# B14.4 | Revoked-cache rejection and qualified FP32 rebuild

Issue #485; parent #375. IPR-0220 remains governing. This is a staged Lane B
child receipt, not production cache acceptance or durable neural authority.

## Inputs and ownership

The refreshed Lane B and reviewed unified trunk were identical at
`4fa27b42430b220e0ba07ed0dbf3f1a7d83dc6d4`. This branch then consumed the exact
same-lane B14.3 review head `b9e1a20b37b79ac779b7b7a88715f2f93533d463`
through merge `0d98c193`. B14.3 PR #670 is exact-head hosted green and ready for
human review, but is not yet integrated into unified. B14.4 therefore remains
staged until that prerequisite is accepted through the reviewed trunk.

The earlier B14.4 branch carried an obsolete structural predecessor chain. The
refresh replayed only its issue-owned implementation commit `ac42ba61` onto the
current Lane B plus exact B14.3 state. The resulting implementation commit is
`d6872978`; focused adversary refinements are `48faae76`.

## Observable contract

`CacheBinding` now includes source release, semantic release, source-rights,
rights-purpose, policy epoch, context-eligibility and optimizer-independent
inference-state identity in addition to generation, lineage, topology, causal
prefix, masks, scope, key, offset and codec identity. Every field participates in
the canonical binding digest.

`decode_cache()` calls `_validate_artifact()`, which calls
`require_cache_binding()` before the codec or any payload decode is entered. A
revoked/superseded rights epoch, source/semantic release, prefix, topology,
generation or inference-state mismatch therefore rejects before stale lossy bytes
can affect attention.

`rebuild_revoked_cache()` accepts an immutable eligibility receipt for the new
binding and a callable canonical FP32 source. It never decodes or relabels the
stale artifact. The fresh source must be finite exact FP32, the rebuilt artifact
must bind to the new identity, and only that newly encoded artifact is handed to
the persistence callback. Reusing the same binding is rejected.

## Adversarial proof

The focused tests prove:

- rights-only and policy-epoch-only changes reject the old cache, then rebuild
  from the newly qualified canonical FP32 source;
- prefix-only and topology-only changes do the same;
- every newly added identity field invalidates an old record;
- an ineligible or mismatched eligibility receipt cannot persist anything;
- non-FP32 or non-finite canonical source input rejects;
- stale-record relabeling under the same binding rejects;
- two different stale lossy payloads produce the same rebuilt artifact when the
  qualified canonical FP32 source and new binding are the same;
- a poisoned codec entrypoint is never reached when stale source-rights identity
  is rejected, directly witnessing rejection before payload decode;
- cache policy, record and rebuild owners import no training, AdamW, gold or frame
  sidecar dependency.

## Verification

Final focused cache suite: 41/41 pass. The affected
attention/backbone/runtime-identity selection passes 68/68 with zero skips.
Development-structure and governance checks report zero violations. Factory
architecture and documentation checks pass. Base-aware error control reports
`new debt 0`. `git diff --check` is clean.

The issue-required Google EGM review has not been claimed in this session;
`EGM_PENDING` remains the integrator-facing review status unless an actual pinned
EGM receipt is supplied. A separate independent read-only GPT review found zero
Blockers and zero Majors plus two proof-coverage Nits. Both Nits were repaired
before final publication: the poisoned-codec ordering witness now covers rights,
prefix and topology independently, and the forbidden-dependency scan now covers
binding, codec, policy, rebuild and record owners. This review is additional defect
discovery and is not a substitute for the required pinned EGM receipt.

No actual student, native AdamW, teacher, checkpoint, source release, admission,
human-run state or production cache caller was modified. B13 accepted generation
custody and parent B14 full integration remain open.
