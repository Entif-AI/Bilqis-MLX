# B14.4 | Revoked-cache rejection and qualified FP32 rebuild

Issue #485; parent #375. IPR-0220 remains governing. This is a staged Lane B
child receipt, not production cache acceptance or durable neural authority.

## Inputs and ownership

This issue branch consumes reviewed unified / Lane B
`ed5df098fddf0e88ccd028652b44ba81e0b235a5`. B14.3 #484 is already
integrated in that reviewed trunk, so the former staged-predecessor hold is
cleared. The branch preserves the issue-owned B14.4 changes while consuming the
current unified frame-codec and BAMF architecture updates.

## Observable contract

`CacheBinding` now includes source release, semantic release, source-rights,
rights-purpose, policy epoch, context-eligibility and optimizer-independent
inference-state identity in addition to generation, lineage, topology, causal
prefix, masks, scope, key, offset and codec identity. Every field participates in
the canonical binding digest. The public cache boundary no longer accepts a raw
`SourceAuthorityRegistry`. A host-issued `CacheAuthorityRuntime` fixes registry
provenance outside artifact/data calls and owns a 32-byte cache-MAC key. Direct
construction and ungated issuance are rejected; the internal host-bootstrap seam
is not exported from the public codec facade. Before minting or accepting a cache
record, the capability requires the binding's authority id, public key and
`ARTIFACT/cache:` scope to match its trusted C09 registry.

Each stored artifact carries one required 128-bit HMAC-SHA256 authenticator in
the existing literal header tag slot. The authenticator covers the complete
binding digest, mode/geometry and exact stored payload bytes. There is no
detached per-artifact signature outside the measured record. The header remains
61 bytes; a full 256-vector ROT3 record is exactly 61 header + 2592 payload =
2653 required bytes, or 3.4544270833 bits/channel, below the 3.5 bound.

`decode_cache()` enters the host-bound capability before `_validate_artifact()`,
which calls the internal binding/authenticator check before the codec or any
payload decode is entered. A
revoked/superseded rights epoch, source/semantic release, prefix, topology,
generation or inference-state mismatch therefore rejects before stale lossy bytes
can affect attention. Relabelling only the binding/header while preserving stale
compressed payload is rejected because the host MAC no longer matches. Knowing
the public MAC algorithm or supplying an attacker registry/key does not permit a
caller to mint a valid authenticator without the host-owned MAC capability.

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
  replacing its binding/header metadata;
- an attacker-selected registry and public key cannot replace the host trust
  root at public encode/decode/inference/rebuild boundaries;
- direct construction and direct ungated issuance of the cache authority
  capability reject;
- recomputing HMAC-SHA256 over stale bytes with an attacker-owned key still
  fails because only the host capability owns the accepted MAC key;
- the 256-vector literal byte-cost witness includes every required per-record
  authentication byte and remains 2653 bytes / 3.4544270833 bits/channel;
- two different stale lossy payloads produce the same rebuilt artifact when the
  qualified canonical FP32 source and new binding are the same;
- a poisoned codec entrypoint is never reached when stale source-rights identity
  is rejected, directly witnessing rejection before payload decode;
- cache policy, record and rebuild owners import no training, AdamW, gold or frame
  sidecar dependency.

## Verification

Final focused cache suite: 44/44 pass. Correction/revalidation coverage including
the frozen pre-split canonical signing-byte compatibility witness passes 19/19;
the split helper again emits the historical literal LF byte rather than the two
bytes `\\n`. Development-structure and governance checks report zero violations;
flow-control tests pass 4/4 and the Lane B validator reports ACTIVE 1/2.
`git diff --check` is clean. The implementation checkpoint is
`8c93853d4549dd65343a81d211b339e7f50c052f`.

The issue-required Google EGM review has not been claimed in this session;
`EGM_PENDING` remains the integrator-facing review status unless an actual pinned
EGM receipt is supplied. Fresh independent NON-EGM review found caller-selected
registry substitution, omitted mandatory signature bytes in the cache budget,
and a pre-split canonical-newline compatibility regression. This checkpoint
repairs those findings; another exact-head independent review is required. This
review stream is defect-discovery evidence and does not substitute for the
required pinned EGM receipt.

No actual student, native AdamW, teacher, checkpoint, source release, admission,
human-run state or production cache caller was modified. B13 accepted generation
custody and parent B14 full integration remain open.
