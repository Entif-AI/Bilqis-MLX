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
`SourceAuthorityRegistry`. It requires an already-bound `CacheAuthorityRuntime`
capability, and #485 exposes no production constructor, issuer, mint, factory or
other callable that accepts a registry or MAC key to create one. Production cache
authorization is therefore **FAIL-CLOSED / UPSTREAM_AUTHORITY_PENDING** until the
accepted B13/A09/A12 run authority supplies a pre-bound capability. Before using
that capability, cache code still requires the binding's authority id, public key
and `ARTIFACT/cache:` scope to match the capability's bound C09 registry.

Each stored artifact carries one required 128-bit HMAC-SHA256 authenticator in
the existing literal header tag slot. The authenticator covers the complete
binding digest, mode/geometry and exact stored payload bytes. There is no
detached per-artifact signature outside the measured record. The header remains
61 bytes; a full 256-vector ROT3 record is exactly 61 header + 2592 payload =
2653 required bytes, or 3.4544270833 bits/channel, below the 3.5 bound.

`decode_cache()` requires the pre-bound capability before `_validate_artifact()`,
which calls the internal binding/authenticator check before the codec or any
payload decode is entered. A
revoked/superseded rights epoch, source/semantic release, prefix, topology,
generation or inference-state mismatch therefore rejects before stale lossy bytes
can affect attention. Relabelling only the binding/header while preserving stale
compressed payload is rejected because the capability MAC no longer matches.
Knowing the public MAC algorithm or supplying an attacker registry/key does not
permit a cache-operation caller to mint a valid authenticator without the
pre-bound authority capability.

The focused tests obtain that capability from an isolated test-only owner created
by `_new_authority_owner()` and install only that owner's lookup during the test.
They do not populate private object slots. Production still exposes no
registry/key-taking authority mint. This fail-closed posture is the accepted #720
boundary until the upstream run owner supplies the production capability.

`rebuild_revoked_cache()` accepts an immutable eligibility receipt for the new
binding. It no longer accepts a caller-selected canonical FP32 source. The
capability owner supplies the current canonical source beside the B13/A12/context
authority inputs. Rebuild validates the receipt, derives fresh finite FP32 bytes
through that owner, consumes the receipt once, persists the rebuilt artifact, and
rechecks current authority before reporting success. It never decodes or relabels
the stale artifact. Reusing the same binding is rejected.

## Adversarial proof

The focused tests prove:

- rights-only and policy-epoch-only changes reject the old cache, then rebuild
  from the newly qualified canonical FP32 source;
- prefix-only and topology-only changes do the same;
- every newly added identity field invalidates an old record;
- an ineligible or mismatched eligibility receipt cannot persist anything;
- non-FP32 or non-finite canonical source input rejects;
- the public rebuild signature exposes no caller-supplied canonical FP32 source;
- stale-record relabeling under the same binding rejects;
- a stale compressed payload cannot be relabelled under a new rights binding by
  replacing its binding/header metadata;
- an attacker-selected registry and public key cannot replace the host trust
  root at public encode/decode/inference/rebuild boundaries;
- direct production construction rejects, `_issue` is absent, and the production
  cache-runtime module exposes no registry/key-taking authority mint/factory;
- recomputing HMAC-SHA256 over stale bytes with an attacker-owned key still
  fails because only the host capability owns the accepted MAC key;
- the 256-vector literal byte-cost witness includes every required per-record
  authentication byte and remains 2653 bytes / 3.4544270833 bits/channel;
- two different stale lossy payloads produce the same rebuilt artifact when the
  qualified canonical FP32 source and new binding are the same;
- a poisoned codec entrypoint is never reached when stale source-rights identity
  is rejected, directly witnessing rejection before payload decode;
- public encode, decode and inference re-derive owner-current B13/A12/policy/
  context identity before cache use, so an old authenticated binding is rejected
  even when the caller supplies that same old binding;
- if owner authority changes inside the persistence callback, rebuild does not
  report success and the stored artifact is rejected by the public read boundary;
- cache policy, record and rebuild owners import no training, AdamW, gold or frame
  sidecar dependency.

## Verification

Historical focused cache suite at the original B14.4 checkpoint: 45/45 pass.
Correction/revalidation coverage including
the frozen pre-split canonical signing-byte compatibility witness passes 19/19;
the split helper again emits the historical literal LF byte rather than the two
bytes `\\n`. Development-structure and governance checks report zero violations;
flow-control tests pass 4/4 and the Lane B validator reports ACTIVE 0/2 because
#485 is truthfully parked on its upstream production-authority dependency.
`git diff --check` is clean. The authority-boundary implementation checkpoint is
`9800132e0492b000369da368607ccb35b8c5b611`.

## Authority status and threat boundary

No accepted production B13/A09/A12 run-authority owner exists on this branch, so
#485 does not manufacture one. Production authenticated-cache use is intentionally
unavailable until that upstream owner supplies the pre-bound capability.

This contract protects against attacker-controlled cache artifacts and callers of
the cache data/API boundary that cannot execute arbitrary code inside the trusted
Python process. It does **not** claim cryptographic secrecy or unforgeability
against arbitrary same-process Python execution/reflection. If that attacker is
in scope, the MAC key must live behind an OS/process/HSM boundary outside #485,
such as OS-protected key material in a privileged helper or authenticated IPC to
a separate authority service.

The issue-required Google EGM review has not been claimed in this session;
`EGM_PENDING` remains the integrator-facing review status unless an actual pinned
EGM receipt is supplied. Fresh independent NON-EGM review found caller-selected
registry substitution, omitted mandatory signature bytes in the cache budget,
and a pre-split canonical-newline compatibility regression. This checkpoint
repairs those findings; another exact-head independent review is required. This
review stream is defect-discovery evidence and does not substitute for the
required pinned EGM receipt.

## 2026-11-05 #719 owner-bound eligibility repair

Fresh pinned Google EGM at `b3a35956759bf7f024af2ff061b2e0b44b438e4c`
reviewed PR #854 head `0341232765ed10a4d134b2c79ac28105671557e1`
and returned **NOT PASS** with one Blocker and four unique Majors. The review
found that the eligibility issuer remained importable, policy/context and the
B13 run selector were still caller-controlled, lineage/inference identities were
not owner-derived, and issued rebuild receipts were reusable across later
authority changes.

Implementation commit `76f144c9690de21d550f0dbf0a7af8905c0f655f`
repairs those seams as one authority-boundary change:

- `CacheAuthorityRuntime` now owns a current eligibility resolver. The public
  issuance API accepts only that opaque capability plus the requested binding;
  callers can no longer pass a pointer path, policy, context, source frontier or
  A12 receipt into the issuance boundary.
- The resolver supplies the authoritative B13 pointer and current A12/source,
  context and policy inputs. Issuance re-reads B13 custody, verifies the signed
  A12 clearance, reprojects the current context and cross-checks the retained
  rights/correction frontier.
- Lineage is derived from the B13 run identity. Optimizer-independent inference
  state is derived from the complete validated executable parameter tree through
  `execution_generation_digest`; neither remains a caller-ratifiable label.
- The former module-level `_issue_eligibility` mint is gone. A caller-created
  receipt or a receipt registered by an unrelated test/factory owner cannot enter
  the production receipt registry.
- Eligibility is owner-scoped and one-use. Rebuild re-derives current authority
  before work and again immediately before consuming the receipt and persistence.
  A policy/context or generation change after issuance therefore fails closed;
  a successfully consumed receipt cannot be replayed.

The new adversaries were red before repair for the exposed mint, reusable receipt
and unchecked lineage/inference identities. Post-repair coverage also proves that
another internally valid B13 run cannot replace the capability-bound run, a
self-consistent caller policy/context cannot replace the owner policy/context,
and owner policy drift after issuance rejects before persistence.

Affected cache/A12/context/B13 verification is now **65/65 PASS**. BAMF
flow-control remains Lane B **2/6 ACTIVE** with **15/15 PASS**. Base-aware
development-structure, governance-integrity and code-smell checks report **zero
new findings**, and `git diff --check` is clean. These are implementation proofs,
not the final review gate: a fresh pinned EGM on the final immutable PR head is
still required before #719 or B14.4 can claim EGM acceptance.

### Exact-head follow-up after the second pinned review

A second fresh pinned review of PR #854 head
`59f45809b1c8b23d9ace4f5cb1f1a0870d53b37b` found two additional Blockers and
two Majors. The Blockers were real use-boundary defects: an old authenticated
binding could still be decoded when the caller supplied that same old binding,
and rebuild still accepted caller-authored FP32 bytes as the canonical source.

Implementation commit `3e173b1c2d44fe37ff3f9fed5037600722dfe0e6`
repairs those defects and tightens the persistence race:

- public encode, decode and interactive inference now verify the requested
  binding against the capability owner's current B13/A12/source/policy/context
  state before cache bytes can be produced or consumed;
- canonical FP32 recomputation moved behind the owner-bound eligibility inputs;
  the cache-operation caller cannot supply replacement FP32 bytes;
- rebuild rechecks owner currentness after the persistence callback. Authority
  drift during that callback makes the operation fail, and the public read path
  rejects any artifact that became stale during the callback;
- regressions cover old-binding reuse after owner policy drift and policy drift
  during persistence, including the requirement that stale bytes never reach
  cache decode or attention.

The remaining production-issuer observation is not repaired by adding a new mint.
#720 explicitly accepted a fail-closed production posture with no exposed issuer.
This branch preserves that boundary. The legitimate owner path is exercised by an
isolated owner seam that supplies live B13/A12/context authority; production stays
unavailable until that upstream owner supplies the pre-bound capability.

Current affected verification is **67/67 PASS**. Error-control reports **zero new
opaque error/numeric debt**. Base-aware development-structure, governance and
code-smell checks report **zero new findings**. BAMF flow-control remains Lane B
**2/6 ACTIVE** with **15/15 PASS**, and `git diff --check` is clean. A fresh pinned
review of the new immutable branch head remains required before claiming EGM
acceptance.

No actual student, native AdamW, teacher, checkpoint, source release, admission,
human-run state or production cache caller was modified. B13 accepted generation
custody and parent B14 full integration remain open.
