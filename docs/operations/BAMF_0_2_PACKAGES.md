# BAMF cognitive package staging

C12.1 / #525 provides the portable manifest boundary under
`bilqis_mlx.runtime.cognitive_package`. C12.2 adds local exchange, disposable delta
screening and the accepted-import candidate. C12.3 / #527 hardens the public-export
authority boundary and composes package import with C03 teacher custody.

`authorize_public_export(...)` first binds an immutable `ExportSnapshot` to the
current A12/C09 source authority. It requires the source-owner-signed
`ExportClearanceReceipt`, exact Atlas selection, current source frontier and current
`SourceAuthorityRegistry`. The receipt's exact export digest set must equal the
snapshot artifact digest set.

C12 derives public classification from the already-typed package role after that
A12 authorization. `FIXTURE` and `COUNTEREXAMPLE` project to `PUBLIC_FIXTURE`;
`PROCEDURE`, `EXACT_TRANSFORM`, `ADAPTER_DELTA`, `WEIGHT_DELTA` and
`BEHAVIORAL_DIFF` project to `PUBLIC_DERIVED`. The classification is descriptive,
not a new rights regime: exact digest membership in the signed A12 export set is
the authority. Upstream `PRIVATE_REAL` material cannot enter that set and
`UNCLASSIFIED` material has no positive export authorization.

The resulting `PublicExportGrant` is sealed, process-local and non-portable.
`export_capability(snapshot, signature, grant)` exports a single semantic
signature from an immutable `ExportSnapshot`. The snapshot identifies its source
generation, exact operator, base weights, topology, parameter schema, semantic
release, active semantic set, factor map and motif key map. Every identity digest
is lowercase SHA-256. The manifest includes executable artifacts, qualification
fixtures, counterexamples, behavioral diff and positive byte resource limits.
The storage limit bounds decoded payload bytes; it does not bound peak parser RAM.

`SourceRights` carries an authority ID, clearance receipt digest, public payload
allowlist, revoked payload digests and sorted unique revocation-lineage digests.
Every artifact, including fixtures and behavioral evidence, must appear in the
public allowlist. Revocation overrides that allowlist. These are embedded clearance
assertions, not independent source authority. Export and staging therefore grant no
adoption right. `publish_screened_delta_import(...)` requires an A12
`ExportClearanceReceipt`, verifies its detached signature through C09's
host-provisioned source-authority registry, binds it to the live A12 selection and
source frontier, and requires the package `SourceRights` to be its exact portable
projection. Embedded rights or matching caller fields cannot authorize adoption.
Neither `PackageArtifact` nor `cognitive-package/v1` carries source classification.
The sealed grant and sender-publication authority token are deliberately non-wire.
Cold package readers therefore reconstruct only the portable package and its
historical `SourceRights`; they cannot reconstruct or invent source-export
authority and cannot republish the cold-decoded object through the sender API.
Do not pass private metadata to the public export API.

For a C16.1c-born lineage, the host administrator provisions C09 registry material
independently at the fixed Darwin path
`/etc/entif-ai/bilqis/source-authority-registry.json`. Bilqis runtime reads and
validates that fixed root but never provisions it and exposes no package, CLI,
configuration, environment, or run-directory selector for it. New generation zero
records the exact registry record, digest, and `HOST_SYSTEM_V1` origin in accepted
custody; every later authority consumer derives system-vs-legacy behavior from that
authenticated custody rather than from caller input.

Historical pre-#950 lineages preserve the #917 run-local registry contract. A
verified historical parent that genuinely lacks origin, record, and digest may bind
the existing run-local registry only on its first ordinary non-C07 retained
successor. Atlas/C07 publication cannot establish that anchor. Once a legacy tuple
exists, descendants inherit it exactly. Explicit null/unknown origins, half-bindings,
replacement, HOST downgrade, and forged HOST upgrade fail closed.

`CognitivePackage.canonical_json` is the portable representation. JSON uses sorted
keys, compact separators, UTF-8 without normalization, arrays for tuples and
lowercase hex payloads. `digest` is SHA-256 over those exact UTF-8 bytes. The schema
is `bilqis.c12.cognitive-package/v1`. Cold loading rejects unknown/missing fields,
duplicate JSON keys, noncanonical encodings, malformed records and uncleared or
revoked payloads. No payload executes during export, read or staging.

`stage_import(package, receiver_binding)` produces an immutable `ImportPlan`.
Identical supplied labels return `EXACT_BINDING`; this preliminary comparison is not
receiver custody or publication authority. A mismatched procedure/exact-transform
package returns `TEACHING_ONLY`. Any mismatched adapter/weight delta rejects the
whole package, including mixed exact/delta packages, before a plan is returned.
Base weights, parameter schema, topology, semantic release, active set, factor map
and motif map must all match for any delta. No approximate matching exists.

A plan records only package digest, receiver binding and compatibility disposition.
It does not apply tensor slices, allocate banks or motifs, run retention, or publish
a generation. Exact-compatible deltas first become sealed disposable candidates.
The accepted-import path is separate and requires signed A12 clearance plus a sealed
C05 screen before B12 can construct receiver-owned reset state and B13 can publish it.
Changing a sender's rights after export does not mutate an immutable package;
a future adoption owner must consult current source revocations before use.

Run the synthetic two-consumer and adversarial boundary proof:

```sh
python3 -B -m unittest discover -s bilqis_mlx/runtime/cognitive_package/tests -t .
```

Synthetic snapshots are test fixtures. They are not accepted B13 generations,
semantic admissions or retained-learning receipts. Parent #381 remains open.

## Local directory exchange (C12.2 / #526)

`cognitive_package.exchange.publish_package(package, directory)` is the public
sender-publication boundary. It accepts only the exact in-memory package returned
by the current authorized `export_capability(...)` path. Directly constructed or
cold-decoded packages fail before sender publication. Authorized publication writes
canonical bytes as `<package.digest>.json` using a flushed/fsynced temporary file,
create-only atomic link and directory fsync. Retries preserve existing identical
bytes and mtime. Existing conflicts and symlink entries reject; publication never
replaces an addressed file. Directories are trusted local paths, not a remote
transport.
An error after linking, including a directory-fsync failure, can leave a complete
addressed entry even though the call raises. Retry the same package to converge;
never interpret an exception as proof that no entry exists.

`inspect_package(sender, package_digest, binding, max_wire_bytes=...)`
requires a positive explicit wire-byte limit. It verifies regular-file type,
bounded raw bytes, exact address digest, canonical package encoding, embedded
clearance assertions and the existing compatibility plan without writing receiver
staging. `stage_received_package(inspected, receiver)` performs the durable write
through a private canonical-byte writer only after the production operator has
validated current accepted-run authority. Receiver staging does not mint a new
sender token and therefore does not create re-export authority.
`receive_package(...)` remains the lower-level inspect-then-stage convenience API.
The returned frozen `StagedExchange` holds the package, plan and receiver path.
Heterogeneous exact packages receive `TEACHING_ONLY`; incompatible deltas reject
before receiver creation. Payloads never execute during exchange.

These directories exchange staging artifacts. There is no activation, tensor
application, optimizer reset or source qualification in the directory exchange
itself. Current production revocations still need the source authority at adoption;
embedded clearance is a historical assertion.

## Disposable plastic-delta candidate (C12.2 / #526)

`encode_plastic_delta(...)` defines the bounded v1 fixture codec used by the
current proving slice. Each changed slice names an already allocated parameter,
an exact flat `[start, stop)` range, the SHA-256 of the receiver's current slice,
and finite little-endian float32 additive delta bytes. Overlapping slices,
noncanonical records, unknown parameters and out-of-range slices fail closed.
This is a selected implementation encoding for the current atlas-native proving
path, not authority to reinterpret a differently encoded package.

`ReceiverTensor` is an immutable float32 byte snapshot. The receiver's base-weight
digest and parameter-schema digest are independently rederived from the actual
canonical tensor set and must equal the package binding before any delta is
applied. The current B13 pointer and complete bundle supply the topology, semantic release,
active-set, factor-map and motif-map identities. The pointer lock remains held while
the complete receiver is checked and the candidate is constructed.

`apply_plastic_delta(package, receiver_run_dir)` creates a `DisposableDeltaCandidate`
from the current B13-published receiver generation. It copies only declared slices into a candidate and derives a
new candidate generation digest from the exact parent generation, package digest
and resulting tensor digests. The parent snapshot is never mutated. The function
does not allocate a parameter, bank or motif and does not reset or publish any
optimizer, age, clock, teacher or checkpoint state.

After the disposable candidate has been built, `screen_delta_candidate(...)` asks
the Factory-owned C05 retention boundary to evaluate the sealed B12 package-import
transaction through `evaluate_factory_package_import(...)`. C05 owns the complete
solver comparison and issues the retention decision from that evaluation. Callers
cannot supply a matching decision, policy, cohort set, or acceptance Boolean. A
rejected candidate is discarded and the current B13 pointer remains unchanged.

`publish_screened_delta_import(...)` is the durable acceptance boundary. It re-reads
the current B13 receiver, rejects stale parent drift, revalidates the signed A12
export-clearance receipt through the C09 registry selected by authenticated accepted
custody (fixed HOST root for `HOST_SYSTEM_V1`, run-local #917 root for legacy),
and consumes the B12 transaction already bound into the internally issued screened
candidate. B12 accepts tensor changes only inside the package's declared slices. It
resets `m` and `v` on those slices, resets the owner-supported update count for the
affected rows or tensor, resets touched identity-row age, preserves untouched state
and policy mode, and resets the accepted-fast cadence counter. Package import does
not fabricate an optimizer step.

B13 publishes the result as a distinct `PACKAGE_IMPORT` generation at the same
optimizer-step clock. The generation records parent manifest, package digest, reset
policy, C05 decision/evidence/policy digests and A12 clearance digest. A public
`BamfBundleCandidate` cannot self-authorize this transition. Pointer failure leaves
the prior generation current and retry converges on the immutable staged bundle.
Cold load preserves the import lineage and reset state, and the next disposable B12
optimizer step starts from those reset counts and moments.

If the recipient already has mature C03 lineage, accepted package import also
rebinds that recipient-owned teacher custody to the changed retained student through
C03's existing `bind_next_teacher_epoch(...)` and `advance_teacher_lineage(...)`.
The recipient's teacher/strategy knowledge, adaptation authority, replay ancestry,
seed, cursor and historical last visit are preserved; checkpoint-local grade,
causal and retirement evidence reset through the normal changed-student binding.
The package never imports sender teacher state.

If C03 has not bootstrapped yet, package import preserves the pre-bootstrap teacher
sidecar. C03 may subsequently perform its ordinary bootstrap on a post-import
generation only when the current transition is an authenticated `PACKAGE_IMPORT`,
the retained optimizer step is still zero, teacher sidecar identity/epoch still
match generation provenance, and the ordinary authoritative legacy receipt,
adaptation and prior-region inputs are supplied. Any intervening optimizer step,
non-package transition or missing bootstrap authority remains fail-closed.

## Production receive -> screen -> publish operator

`cognitive_package.operator.receive_screen_and_publish_package(...)` is C12's
production composition seam. It derives the receiver binding from the current B13
generation, inspects bounded local package bytes without staging, refuses any delta
that is not `EXACT_BINDING`, verifies the current A12/C09 source authority, and only
then stages the package. It next constructs the disposable B12 candidate, obtains the C05 owner-issued
decision, and delegates accepted publication to the B13 boundary above.

The final pre-staging currentness check owns the B13 pointer lock, authenticates the
exact current accepted student, confirms its correction-frontier registry digest is
the digest cleared earlier, and resolves C09 through that accepted frontier. A HOST
lineage rereads the fixed system root without taking the run-local registry lock; a
legacy lineage preserves the established pointer-lock -> registry-lock order. Host
root drift after clearance therefore rejects before durable package staging.

The operator is orchestration, not a new authority. An `ExportClearanceReceipt`,
Atlas selection, and source frontier supplied to the call are revalidated against
the accepted run's custody-owned source authority. The production clearance boundary
requires the exact host-minted `SourceExecutionContext`; duck-typed substitutes are
rejected before durable staging. Callers do not supply or select a source-authority
registry. A matching embedded
`SourceRights`, an `ELIGIBLE`-style result, or a caller-created `accepted=True`
cannot publish a generation. Presentation/CLI code therefore does not duplicate
this chain or become a package-admission trust root.
