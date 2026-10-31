# A03.4 immutable released frame-schema body witness candidate

Issue: #578 (A03.4). Parent: A03 #349. Lane: A.
Consumed unified SHA: `7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4`.
Source lane base: `9fa752b6410c8248aa784a361247a8a7230fb748`.
Review disposition: **EGM PASS for A03.4**, zero remaining
Blockers/Majors at immutable `1297f3d`.

## Source and consumer contract

`bilqis_mlx/semantics/released_frame_schemas.py` freezes the *existing*
`FrameSchema.canonical_bytes()` and `SchemaTagMap` into a content-addressed
A03 release manifest. It binds semantic release, A01 Atlas bundle and source
bundle IDs, exact schema IDs/revisions, body digests and release-local map
identity. No new AST, schema semantics or parallel registry is introduced.

Issuance (`seal_released_frame_schemas`) stages source-owner bodies only;
staging is not an admission credential. `persist_released_frame_schemas`
uses an append-only digest-named artifact path and rejects altered existing
bytes. The consumer entrypoint (`load_released_frame_schemas`) requires the
**independently accepted A03 artifact digest**, a frozen A01 snapshot and,
where available, expected release/map pins. It verifies canonical manifest
bytes, body serialization, exact map coverage, A01 source identity and digest
before returning an offline witness lookup. A consumer must not derive its
trusted expected digest from the same untrusted candidate payload.

`VerifiedReleasedFrameSchemas.require_schema` refuses same-ID/revision body
substitution; `require_schema_bytes` canonicalizes JSON object key ordering
but preserves role-array order as semantic. These are suitable A03 gates for
B07 motif-key construction and B08 motif reads. A13 rights, revocation and
cache dependencies remain separate source-owner obligations.

## Focused verification

Initial red: new owner test module failed to import the absent A03.4 API.
After implementation:

- 9/9 new A03.4 tests pass with the real A01 artifact mounted, including
  actual registered A source rows and all three source-family pin lookups;
- combined A03 schema/adapters, A04 codec and A03.4 with real A01
  artifact and canonical corpus mounted: **52 passed, 0 failed, 0 skipped**;
- `git diff --check` passes;
- static module/error audits report no new A03.4 findings; inherited
  repository-wide findings remain outside this leaf.

The tests cover changed AST construct, role order, allowed types,
cardinality, scope, order mode, contract SHA, forged local catalog,
foreign release/map, A01 source-bundle mismatch, duplicate/noncanonical
manifest controls, append-only file drift and key-order canonicalization.

## 2026-10-29 source-owned pin publication candidate

The source-owner generator
`scripts/generate_released_frame_schema_pins.py` reloaded the *existing*
repo-pinned A01 artifact (bundle
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`,
release `58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`)
and checked actual registered A/B/C source rows and recursive ASTs. It
rederived six unique exact frame-schema bodies in each of three source
families: `micro`, `boolean`, `numeric`. Same-ID/revision body conflicts
fail rather than silently selecting a new schema.

Three append-only canonical manifests are staged in
`bilqis_mlx/semantics/frame_schema_releases/`. Their SHA-256 identities:

- micro: `937f0309dd46e37fa8dc1e5022963baefb1bc3511f40dd03e5b1a0a45b5413ac`
- boolean: `639f102ee55ef11d2c4860ccad06a9d90cc0abfcec52acefa2f7bcb576a21cf7`
- numeric: `d89f845fbeedfda69d95f156a6d424174698d8b65480e3db9764530dec7f439b`

The repo-owned source pin registry
`frame_schema_source_pins_v1.json` has SHA-256
`4c8da914834f8dc5cadef67bbf9b7da1031f07cc80d4775a47d18b68af62a6c1`,
independently pinned in the loader code. The production consumer
`lookup_source_pinned_frame_schema(schema_id, revision, *, source_family,
atlas_selection)` and `verify_source_pinned_frame_schema(candidate, *,
source_family, atlas_selection)`
first revalidates A01 against its separate repo-owned pin, then loads
the fixed A03 pin registry and exact content-addressed manifest.
No caller-supplied schema registry, manifest path or expected digest
enters these production consumer entrypoints. They return canonical
source-pinned schemas (and inspectable witnesses), not a caller-supplied
authority object. Self-pinned low-level staging objects are not admission.

The generator was rerun idempotently and reproduced all three manifest
digests and the pin-registry digest. The real A01/source-family test
passed 9/9 without skips using a disposable source artifact.

## Remaining downstream integration

## Independent EGM finding and targeted repair

Goldfish worker-17 reviewed immutable `71db092` and found one **Blocker**:
the initial `SourcePinnedReleasedFrameSchemas` object could be
caller-minted by importing its module-global constructor sentinel.
It demonstrated a changed-scope schema passing the forged exact-type
check using a self-pinned staging manifest. The manifest loader itself,
all 18 actual source pins, generator and 52 real tests passed review.

The production contract no longer treats an in-process object or
sentinel as authority. `lookup_source_pinned_frame_schema` and
`verify_source_pinned_frame_schema` now **re-enter both independent
repo-owned pin registries on every call**, accept no caller-provided
manifest, registry, digest or purported trusted object, and compare
the exact canonical schema body. A new test reproduces the original
self-pinned forged staging manifest and confirms the production
verification rejects it across all three source families. The repaired
combined real suite again passes **52/52, zero skips**.

Independent worker-17 read back immutable `1297f3d` and returned
**EGM PASS, zero remaining Blockers/Majors**. It retried the original
forged-scope staging attack against both production object and bytes
verification for micro, boolean and numeric: all failed closed with
`FRAME_RELEASED_SCHEMA_BODY_MISMATCH`. Wrong A01 artifact-path
substitution failed at the independent A01 pin. It rederived all 18
actual source schemas and reproduced all three manifests/maps and
the source pin-registry hash. The reviewer executed 52/52 real
A01/A03/A04 tests with zero skips and verified a clean diff.

B07.1/B08.1
must call these source-pinned functions themselves before motif-key/readout
admission; they must not accept caller-provided witnesses as credentials.
A13 rights/revocation and cache dependency gates remain independent.
No neural admission, training or merge occurred.


## Current reproduction route — 2026-10-30

The source-owner generator is preserved under `scripts/semantics/` after the
root-script directory repair. From the repository root, invoke
`python3 -B -m scripts.semantics.generate_released_frame_schema_pins` with the
original pinned artifact and output arguments above. Its implementation is
unchanged except the equivalent repository-root calculation after relocation.
This path correction does not generate a new release or renew source authority.
