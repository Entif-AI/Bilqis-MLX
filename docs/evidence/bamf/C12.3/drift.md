# C12.3 | Design-to-code drift report

Design target: `docs/tasks/bamf-0.2/children/C12.3.md` plus GitHub #527 amendment
comments `6753769152`, `6753797209`, `6753812392`
Pre-implementation reviewed-unified base:
`6a770f10074df6f4f8889d439f783ad42f5efe63`
Exact semantic implementation/proof head:
`3aa81f18dba338b79eff935de96e9d94eda75fae`
Pinned EGM:
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`

## Prime differential audit

No harmful contract drift detected in the exact `base..head` diff.

The implementation follows the amended design boundaries:

- public-export classification is deterministic from `PackageKind` and remains
  non-wire;
- exportability still comes from exact source-owner-signed A12 digest clearance;
- sealed `PublicExportGrant` and the in-memory sender token cannot survive cold
  package decode;
- sender publication and receiver-local canonical staging remain distinct;
- `cognitive-package/v1` and the historical golden digest remain readable and
  byte-stable;
- B12/C05/B13 package-import ownership is reused rather than reimplemented;
- mature C03 custody is rebound through the existing teacher-lineage owner;
- pre-bootstrap C03 continuation is restricted to authenticated PACKAGE_IMPORT
  custody at optimizer step zero with ordinary bootstrap authority;
- next-step package/reset ancestry remains transitive through the imported B13
  parent manifest rather than expanding candidate-step wire.

Implementation-only support not separately named in the design is limited to
shared deterministic test-authority fixtures and the refactoring of the exchange
writer into a private canonical-byte helper required to keep receiver staging
separate from sender authorization. Both are direct mechanical consequences of the
amended contract and do not create new authority.

## Independent drift scopes

All three independent exact-head drift scopes completed with
**0 Blockers / 0 Majors**:

- **Readiness drift:** PASS 0B/0M after reviewing all 20 semantic changed paths,
  the original C12.3 contract plus the live amendment, production source, focused
  acceptance/recovery/C03 tests, operations documentation and call sites.
- **Comprehension drift:** PASS 0B/0M. The reviewer independently confirmed the
  portable/local authority boundary, unchanged v1 wire/golden digest, non-wire
  grant/token, cold-decode non-authority, receiver-staging separation, mature C03
  rebind and the narrow pre-bootstrap PACKAGE_IMPORT exception.
- **Codebase-fit drift:** PASS 0B/0M. The reviewer confirmed the sealed A12 grant,
  sender/receiver publication split, host-bound C09 revalidation at adoption,
  unchanged C05/B12/B13 ownership, C03 rebind/bootstrap behavior and unchanged
  v1 wire/golden fixture.

The prime differential audit and all three independent scopes found no harmful
drift.

Benign implementation differences identified by the independent scopes:

- `authorize_public_export(...)` is the concrete source-side grant issuance API.
  `ExportClassification` and `PublicExportGrant` are importable C12 types, but
  only module-private issuance can mint a valid grant.
- `ExportClassification` names `PRIVATE_REAL` and `UNCLASSIFIED` for local
  domain description even though issued grants contain only
  `PUBLIC_FIXTURE`/`PUBLIC_DERIVED`. Those values are non-wire and
  non-authorizing.
- sender persistence is factored through private `_publish_canonical_package`;
  the public sender API adds the source-export token gate while receiver staging
  uses the private writer without minting re-export authority.
- C03 package-import behavior is factored through
  `rebind_package_import_teacher_custody`,
  `_require_current_c03_lineage` and
  `_package_import_bootstrap_eligible`.
- acceptance proof is decomposed across existing adoption/recovery coverage, the
  new C12.3 acceptance module, C03 custody tests and shared deterministic fixtures.
- the historical golden package remains the literal compatibility fixture. The
  current signed-A12 synthetic fixture has different historical SourceRights
  values, so the wire test locks the old bytes/digest independently and separately
  round-trips current v1 packages. `wire.py` and the golden file are unchanged.
- source-side export takes the C09 `SourceAuthorityRegistry` directly, as specified
  by the amendment. Receiver adoption separately binds currentness to host-provisioned
  C09 custody through the accepted runtime.

## Reviewed-unified integration sync

After semantic drift was frozen, reviewed unified advanced from `6a770f10` through
`039fbcab9df0e3aac6efb622bfaa059fa7e2bf5a` with B09.3 plasticity-transition
and transition-authority work that touched package-import/retention dependencies.
Lane C merged the latest reviewed base conflict-free at integration head
`64351d421edcd9594f1f393322fa15936602fc8c`.

The complete C12 package suite (**68/68**) and targeted C03/B09/vocabulary ring
(**10/10**) passed after that latest merge. The earlier cross-owner
C03/B13/C05/A12/source-rights ring remains **33/33** at the semantic-head proof.
Flow-control and contract-mirror checks also remained green after `039fbcab`.
The aggregate quality chain previously stopped only on the pre-existing C07.1b
legacy-trainer receipt defect reproduced on the reviewed base; #527 does not edit
that unrelated receipt.
