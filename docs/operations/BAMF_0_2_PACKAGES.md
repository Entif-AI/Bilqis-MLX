# BAMF cognitive package staging

C12.1 / #525 provides a portable manifest boundary under
`bilqis_mlx.runtime.cognitive_package`. This is provisional software staging.
Accepted source/generation producers and full package adoption remain pending.

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
public allowlist. Revocation overrides that allowlist. These are explicit
caller-supplied clearance assertions, not independently verified signatures or
source authorization. Only a trusted source adapter may supply cleared metadata
and these records in a production integration. Payload scanning cannot prove that
arbitrary metadata is public. Do not pass private metadata to this public export API.
The current slice has no production source adapter and grants no production rights.

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
It does not itself apply tensor slices, allocate banks/motifs, reset optimizer
state, change teacher state, run retention or publish a generation. C12.2/#526 now
adds a separate pure disposable-candidate path for an exact-compatible delta; the
durable receiver-owned adoption/reset transition remains C12.3/#527. No production
importer consumes these plans yet.
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
`screen_delta_candidate(...)` passes its exact parent and derived candidate
generation identities to C05's existing `retain_candidate(...)` owner. An eligible
decision remains advisory evidence only: B12/B13 still own publication. A rejected
candidate is rolled back by discarding the immutable disposable candidate; the
parent bytes are unchanged.

C12.2 source-rights and authoritative screening remain open under #718. #527 owns
the durable receiver transition: changed-slice optimizer resets, establishment-age
and cadence resets, `PACKAGE_IMPORT` origin, atomic commit/crash rollback,
subsequent native optimizer receipt and cold-resume equivalence. Production #526
turn-in also remains gated on accepted A12 source/rights and B13 generation custody;
the current synthetic PUBLIC fixtures do not promote those pending authorities.
