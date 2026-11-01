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
Identical bindings return `EXACT_BINDING`. A mismatched procedure/exact-transform
package returns `TEACHING_ONLY`. Any mismatched adapter/weight delta rejects the
whole package, including mixed exact/delta packages, before a plan is returned.
Base weights, parameter schema, topology, semantic release, active set, factor map
and motif map must all match for any delta. No approximate matching exists.

A plan records only package digest, receiver binding and compatibility disposition.
It does not apply tensor slices, allocate banks/motifs, reset optimizer state,
change teacher state, run retention or publish a generation. Those steps and their
rollback/next-step/cold-resume proofs remain with C12.2/#526 and C12.3/#527 and the
native B13/C05 custody owners. No production importer consumes these plans yet.
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
application, optimizer reset or source qualification. Actual retained adoption and
rollback remain gated by B13/C05 and #527. Current production revocations still
need the source authority at adoption; embedded clearance is a historical assertion.
