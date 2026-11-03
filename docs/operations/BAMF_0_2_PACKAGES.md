# BAMF cognitive package staging

C12.1 / #525 provides the portable manifest boundary under
`bilqis_mlx.runtime.cognitive_package`. C12.2 adds local exchange, disposable delta
screening and the accepted-import candidate. Parent #526/#718 still owns final EGM
and human integration.

`export_capability(snapshot, signature, rights)` exports a single semantic
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
Do not pass private metadata to the public export API.

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

`cognitive_package.exchange.publish_package(package, directory)` publishes canonical
bytes as `<package.digest>.json` using a flushed/fsynced temporary file, create-only
atomic link and directory fsync. Retries preserve existing identical bytes and
mtime. Existing conflicts and symlink entries reject; publication never replaces
an addressed file. Directories are trusted local paths, not a remote transport.
An error after linking, including a directory-fsync failure, can leave a complete
addressed entry even though the call raises. Retry the same package to converge;
never interpret an exception as proof that no entry exists.

`receive_package(sender, receiver, package_digest, binding, max_wire_bytes=...)`
requires a positive explicit wire-byte limit. It verifies regular-file type,
bounded raw bytes, exact address digest, canonical package encoding, embedded
clearance assertions and the existing compatibility plan before receiver writes.
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

After the disposable candidate has been evaluated with the complete solver,
`screen_delta_candidate(...)` asks C05 to run the required cohorts itself through
`evaluate_retention_candidate(...)`. Callers cannot supply a matching retention
decision or evidence object. A rejected candidate is discarded and the current B13
pointer remains unchanged.

`publish_screened_delta_import(...)` is the durable acceptance boundary. It re-reads the
current B13 receiver, rejects stale parent drift, verifies current A12 authority,
and asks B12 to create a sealed package-import transaction. B12 accepts tensor
changes only inside the package's declared slices. It resets `m` and `v` on those
slices, resets the owner-supported update count for the affected rows or tensor,
resets touched identity-row age, preserves untouched state and policy mode, and
resets the accepted-fast cadence counter. Package import does not fabricate an
optimizer step.

B13 publishes the result as a distinct `PACKAGE_IMPORT` generation at the same
optimizer-step clock. The generation records parent manifest, package digest, reset
policy, C05 decision/evidence/policy digests and A12 clearance digest. A public
`BamfBundleCandidate` cannot self-authorize this transition. Pointer failure leaves
the prior generation current and retry converges on the immutable staged bundle.
Cold load preserves the import lineage and reset state, and the next disposable B12
optimizer step starts from those reset counts and moments. This candidate does not
close #526/#718 until final exact-head EGM and human integration.
