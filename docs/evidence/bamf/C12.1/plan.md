# C12.1 / #525 portable package staging plan

Base: synchronized Lane C and unified `bb626d75`. This slice implements a new
immutable portable manifest boundary. It does not grant production source rights,
apply tensors, publish generations, or claim A12/B13/C05/C09 acceptance.

Create `bilqis_mlx/runtime/cognitive_package/` with contracts, serialization and
export/import staging modules; create mirrored package-local tests. Create
`docs/operations/BAMF_0_2_PACKAGES.md`. Modify the existing central ErrorBus catalog
and school namespace to register one typed package error. No existing runtime
behavior changes. Every new source and test module stays below 240 lines.

Records are frozen dataclasses with tuples and bytes only. `PackageBinding` binds
base weights, parameter schema, topology, semantic release, active set, factor map
and motif key map by SHA-256. `PackageArtifact` binds an ID, kind and immutable
bytes. Kinds: procedure, exact transform, adapter delta and weight delta.
`SourceRights` is an explicit caller-supplied clearance record, with authority ID,
clearance digest, public artifact digest allowlist and revoked digest set.
It is not a signature verifier or a substitute for source-owned qualification.
`CognitivePackage` includes semantic signatures, exact binding, operator identity,
qualification fixtures, counterexamples, behavioral diff, resource envelope,
rights and revocation lineage. Fixtures/counterexamples/diff are byte artifacts
subject to the same clearance check as executable payloads. Public metadata is
caller-cleared; arbitrary private metadata cannot be detected by content scanning.

`export_capability(generation, signature, rights)` takes a typed source export
snapshot (not a live B13 generation) and one semantic signature. It requires every
artifact digest to be public-cleared and unrevoked, verifies the signature matches,
and returns a portable package without writes. This snapshot remains provisional
until the actual source and generation owners issue accepted receipts.

`stage_import(package, receiver)` takes an immutable receiver binding. Exact
procedures and transforms return a teaching-only plan when bindings differ.
Any adapter/weight delta requires equality of every binding field; mismatch raises
the catalog error before a plan exists. A matching delta plan means only that
manifest identities match; tensor slice, optimizer reset, retention, atomic commit,
and cold-resume validation belong to #526/#527 and must precede actual adoption.

Canonical JSON uses sorted keys, compact separators, UTF-8 and allow_nan=False;
bytes are hex. Every schema is exact v1; loading rejects unknown/missing fields,
wrong types, duplicate JSON keys, invalid hex and noncanonical bytes. The package
digest is SHA-256 of canonical bytes. Revalidate nested records at public boundaries.
No untrusted payload is executed or written.

Proof: first add failing behavioral tests for two-consumer roundtrip, all manifest
fields surviving, private/revoked payload rejection, forged nested records,
noncanonical/malformed JSON, exact import/teaching fallback and each delta binding
mismatch. Then implement and run focused tests, ErrorBus catalog checks, structure,
governance, architecture, docs and diff checks. Fresh pinned EGM readiness review
precedes implementation; fresh codebase/comprehension review precedes turn-in.

## Concrete schema and implementation inventory

Create `cognitive_package/contracts.py`: `PackageKind` is a string Enum with values
`procedure`, `exact_transform`, `adapter_delta`, `weight_delta`, `fixture`,
`counterexample`, `behavioral_diff`. `PackageBinding` has exactly seven digest
strings, in order: base_weight_digest, parameter_schema_digest, topology_digest,
semantic_release, active_set_digest, factor_map_digest, motif_key_map_digest.
All digests are lowercase 64-character hexadecimal SHA-256 values.
`PackageArtifact(artifact_id: str, kind: PackageKind, payload: bytes)` exposes
`digest`, computed from payload bytes. Payload and artifact ID must be nonempty.
`SourceRights(authority_id: str, clearance_digest: str,
public_artifact_digests: tuple[str,...], revoked_artifact_digests: tuple[str,...],
revocation_lineage: tuple[str,...])` requires digest tuples sorted and unique.
Lineage contains opaque ancestor/revocation receipt digests; it is preserved, never
interpreted as clearance. Revoked wins over public allowlist membership.

Create `cognitive_package/records.py`: frozen `ExportSnapshot(generation_id: str,
signature: str, binding: PackageBinding, operator_identity: str,
artifacts: tuple[PackageArtifact,...], max_memory_bytes: int,
max_storage_bytes: int)` requires positive exact integers, nonempty strings,
unique artifact IDs, at least one procedure/transform/delta, and at least one
fixture, counterexample and behavioral_diff artifact. Artifact order is preserved.
Frozen `CognitivePackage` has those same fields plus `rights: SourceRights` and
`schema_version: str = 'bilqis.c12.cognitive-package/v1'`. Both record constructors
revalidate nested records. `CognitivePackage` additionally checks every payload
against clearance. Its `canonical_json`, `digest`, `from_canonical_json` delegate
to wire functions. `ImportPlan(package_digest: str, receiver: PackageBinding,
disposition: str)` is frozen and only permits EXACT_BINDING or TEACHING_ONLY;
it carries no tensors, optimizer state, allocations or adoption authorization.

Create `cognitive_package/wire.py`: `encode_package` recursively emits record
field names, Enum values and lowercase payload hex; tuples become JSON arrays.
`decode_package` parses JSON with duplicate-key rejection, reconstructs exact
nested records using keyword constructors, and compares the result's canonical
JSON byte-for-byte with input. Unknown/missing fields, arrays where records are
required, wrong types, whitespace, NaN, infinity, float integers and upper-case
hex fail. Only outer package schema is versioned in this initial embedded schema.
Catch KeyError/TypeError/ValueError/RecursionError and raise the package catalog
error. No filesystem or network I/O exists in this module.

Create `cognitive_package/staging.py`: `export_capability` requires exact snapshot,
signature string and SourceRights types, revalidates them, rejects signature drift,
then builds CognitivePackage. `stage_import` revalidates package and receiver;
returns EXACT_BINDING on equality. On mismatch, if any artifact is adapter_delta
or weight_delta, raises typed error; otherwise returns TEACHING_ONLY.
Create `cognitive_package/__init__.py` exporting only the seven record/Enum types
and the two staging functions. Private validation helpers live in contracts.py.

Modify `errors/specs/school_bamf.py`: add BAMF_PACKAGE.INVALID using `_spec`, owner
runtime.cognitive_package, reason parameter, PRESERVE_AND_INSPECT disposition.
Modify `errors/specs/school.py` to expose it; modify `errors/catalog.py` CATALOG
list to register it. Errors use `ErrorBus.raise_`, preserving ValueError ancestry.
Reasons are plain lower-case operator-facing details (binding, clearance, revoked,
artifact, signature, resource, wire), not a second uppercase error-code registry.

Tests are created under `cognitive_package/tests/`, mirroring contracts/staging
through `test_contracts.py`, wire through `test_wire.py`, exchange through
`test_staging.py`; shared fixtures.py supplies the literal synthetic source.
The four artifacts contain exactly `b'x + 1'`, `b'1 -> 2'`, `b'0 != 2'`, and
`b'gains=1;regressions=0'`. Binding fields are SHA-256 of UTF-8 strings '0'..'6';
resource limits are 1024 memory bytes and 2048 storage bytes. Tests assert these
literal values, exact disposition strings, all seven mismatch failures for each
delta kind, per-artifact missing clearance failures, revoked-before-export,
forged nested binding/payload failure, duplicate IDs, boolean limits, malformed
schema/hex, duplicate JSON keys, whitespace, truncation, float limits and NaN.
Run `python3 -B -m unittest discover -s
bilqis_mlx/runtime/cognitive_package/tests -t .`. Initial run has three expected
ImportErrors because the public API does not yet exist. No implementation added.

Mixed exact/delta packages follow the strictest contained artifact: one mismatched
delta rejects the entire package. ImportPlan never grants adoption: it contains
only the digest, receiver identity and compatibility disposition. No consumer is
wired to apply it in this slice. Model identity is the exact base weights,
parameter schema and topology in PackageBinding, alongside operator_identity.

Verification checkpoints:
1. Red: package tests fail with missing APIs (captured /tmp/c525-red.log).
2. Green: package tests plus `python3 -B scripts/run_tests.py
   bilqis_mlx/errors/tests/test_catalog.py`.
3. Gate: `python3 -B scripts/check_module_size.py --changed-from bb626d75`,
   `python3 -B scripts/quality/check_governance_integrity.py --base-ref bb626d75`,
   `python3 -B scripts/check_factory_architecture.py`,
   `python3 -B scripts/quality/check_docs.py`,
   `python3 -B scripts/error_control_plane.py --check --base-ref bb626d75`, and
   `git diff --check`. Preserve actual failure receipts; do not normalize debt.
4. Fresh EGM codebase/comprehension review, bounded repairs, rerun affected proof.
5. Commit/push, draft PR to unified, issue receipt and all tracker tabs reconciled.

String encoding is ensure_ascii=False, including metadata; canonical strings are
UTF-8 without normalization. Empty/control-character IDs are invalid. The initial
API transports a single signature per package. max_storage_bytes bounds the sum
of decoded artifact payload lengths; it is not a claim of peak decoder memory.
Wire literal fixture and independently computed SHA-256 will be stored beside the
serialization tests and compared byte-for-byte, before implementation turn-in.

Readiness re-audit resolved the schema/design Majors. Its remaining proof Major
was repaired: semantic mutation tests now emit canonical JSON and assert the
package catalog identity, independently of whitespace rejection. The tests now
include mixed exact/delta whole-package rejection and the checked-in literal
`golden_package.json`, SHA-256
`98527cd13e7a10c65d4697277e681137f34ff55dbdf479bf842eb7f87c6372e4`.
