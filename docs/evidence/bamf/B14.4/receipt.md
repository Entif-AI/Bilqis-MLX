# B14.4 | Revoked-cache rejection and qualified FP32 rebuild

Issue #485; parent #375. IPR-0220 remains governing. This is a staged Lane B
child receipt, not production cache acceptance or durable neural authority.

## Inputs and ownership

This issue branch consumes reviewed unified / Lane B
`3088ee02d085f2a88e53b7c78c8d9637916663fe`. B14.3 #484 is already
integrated in that reviewed trunk, so the former staged-predecessor hold is
cleared. The branch preserves the issue-owned B14.4 changes while consuming the
current unified frame-codec and BAMF architecture updates.

## Observable contract

`CacheBinding` now includes source release, semantic release, source-rights,
rights-purpose, policy epoch, context-eligibility and optimizer-independent
inference-state identity in addition to generation, lineage, topology, causal
prefix, masks, scope, key, offset and codec identity. Every field participates in
the canonical binding digest. Each stored artifact also carries a 128-bit
payload/authority integrity tag over that binding digest, record geometry and
the exact stored payload bytes. The tag is part of the literal record header,
which remains within the parent's 64-byte metadata ceiling at 61 bytes. A
256-vector ROT3 record measures 3.454427 bits/channel, below the 3.5 acceptance
limit.

`decode_cache()` calls `_validate_artifact()`, which calls
`require_cache_binding()` before the codec or any payload decode is entered. A
revoked/superseded rights epoch, source/semantic release, prefix, topology,
generation or inference-state mismatch therefore rejects before stale lossy bytes
can affect attention. Relabelling only the binding/header while preserving stale
compressed payload is rejected because the payload/authority tag no longer
matches; callers cannot request automatic re-minting of that tag through the
artifact constructor.

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
- a stale compressed payload cannot be relabelled under a new rights binding by
  replacing its binding/header metadata, and an absent tag fails construction;
- two different stale lossy payloads produce the same rebuilt artifact when the
  qualified canonical FP32 source and new binding are the same;
- a poisoned codec entrypoint is never reached when stale source-rights identity
  is rejected, directly witnessing rejection before payload decode;
- cache policy, record and rebuild owners import no training, AdamW, gold or frame
  sidecar dependency.

## Verification

Final focused cache suite: 42/42 pass after the payload/authority relabel
adversary was added. The widened affected attention/backbone/runtime-identity
selection passes on the same source state with the cache regression included.
Development-structure and governance checks report zero violations. Factory
architecture and documentation checks pass. Base-aware error control reports
`new debt 0`. `git diff --check` is clean.

The issue-required Google EGM review has not been claimed in this session;
`EGM_PENDING` remains the integrator-facing review status unless an actual pinned
EGM receipt is supplied. A fresh independent exact-head review found one Major in the earlier refreshed
candidate: callers could relabel the authority digest/header onto unchanged
compressed bytes. That defect is now repaired with the payload/authority tag and
a literal rights-only relabel adversary. A new exact-head independent review is
required after this repair. This review stream is defect-discovery evidence and
does not substitute for the required pinned EGM receipt.

No actual student, native AdamW, teacher, checkpoint, source release, admission,
human-run state or production cache caller was modified. B13 accepted generation
custody and parent B14 full integration remain open.
