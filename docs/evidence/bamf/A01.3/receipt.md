# A01.3 frozen Atlas reader and source-hold census evidence

Issue: #398
Lane: `codex/bamf02-a-semantics`
Consumed unified head: `44f78431709ec3b8fc23f47b45d9b18f167c7354`
Consumed A01.2 lane head: `bd3a3ce0450c5f4b0b7f9aadade7db42c3ccc1bd`
Review disposition: `EGM_PENDING`

## Database-free frozen read API

`load_atlas_snapshot(bundle_dir, expected_bundle_id=..., expected_release_sha256=...,
expected_source_bundle_id=...)` loads the content-addressed five-file Atlas release
without a database or mutable semantic registry. It requires the exact
content-addressed directory name, verifies the canonical manifest and every file
digest/byte count, validates the persisted semantic-release identities, reconstructs
immutable typed concepts, ABI entries, relations and withheld coverage rows, and
checks their cross-file invariants before returning
`bilqis.semantic-atlas-snapshot/v1`.

The frozen snapshot exposes direct ABI-index lookup, semantic-ID-to-ABI lookup,
source-qualified concept lookup, the source-hold census, and the
implementation-uncovered census. Concept and semantic lookups use immutable sorted
indexes derived from the verified files at load time. No reader path writes a file,
updates a database, substitutes an implicit latest release, or derives semantic
identity from provider implementation bytes.

The real canonical witness loads as:

- source bundle:
  `f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`
- canonical RDF:
  `7a0a0cd04133be41db69ca3fe1e2f09b4efbc8c965610b75c5ac30bc0954b50e`
- Atlas release:
  `58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`
- content-addressed Atlas artifact:
  `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
- source-qualified concepts: 9079
- logical ABI entries: 9307
- source-held census: 1052 rows
- source-qualified implementation-uncovered census: 9079 identities

The release and artifact digests are unchanged from A01.2. The stricter admission
checks therefore reject invalid inputs without changing valid canonical output.

## Admission-boundary repairs

A same-session bounded admission audit of the earlier immutable A01.1 implementation
identified five fail-open source-boundary cases. This leaf repairs those seams before
the snapshot API can expose a release:

1. The independent source-row census must contain the exact same
   `(domain, table, key)` identities as coverage, with no duplicates on either side.
2. Each registered conformance gate appears exactly once as a typed
   `gate/version/status/evidence` record.
3. Every aggregate gate must equal its canonical `gate-*.json` constituent receipt.
4. The source manifest member set is exact; undeclared or missing members fail.
5. The bundle manifest and all member paths must be regular non-symlink files before
   their contents are read.

The package tests reproduce wrong-census identity, same-count census duplication,
constituent SHACL disagreement, duplicate aggregate gate, unexpected manifest member
and symlink-member attacks. Every case now fails with a structured ErrorBus error.

Label and realization ordering now uses explicit stable keys for optional language and
datatype values, so equal lexical values with `None` versus string metadata remain
deterministic instead of depending on invalid Python comparisons.

## Reader failure witnesses

Focused tests also prove that:

- a mismatched expected Atlas release is rejected explicitly;
- a mismatched expected canonical source release is rejected explicitly;
- a renamed `latest` alias is rejected rather than silently substituted;
- a self-consistent artifact missing `source_bundle_id` is rejected;
- payload-byte tampering fails the manifest digest check without mutating the manifest;
- a held semantic identity remains absent from ABI lookup, and a forged active ABI
  entry for that identity is rejected before the manifest, active-set artifact, or
  held ledger can change;
- a prior Atlas ABI can be consumed only through a manifest-verified
  `FrozenAtlasSnapshot`; supplying bare `atlas.json` rows as accepted predecessor
  state fails with `ATLAS_PRIOR_ABI_PROVENANCE_REQUIRED`.

Persistence also fsyncs the output parent directory immediately after the atomic
content-addressed rename, matching the repository SKOS publisher's durability
boundary. The real-corpus test pins the exact Atlas release digest, artifact bundle
ID, shape-policy digest, active-set digest, RDF-term count and all four persisted
payload digests.

The held-identity case above proves the A01 ABI boundary only. It does not claim that
the downstream Factory admission API has already received and rejected an A01 hold
request. That cross-contract witness belongs at the existing Factory/admission seam
when the later semantic-coverage binding reaches it.

## Verification

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_atlas_projection.py` in the
provided dependency environment: 9 passed, 1 external real-corpus witness skipped.

The same test file with the pinned real-corpus witness enabled: 10 passed, 0 skipped.
The real witness exercises persistence, frozen readback, bank-1 lookup at index 8192,
source-hold census, exact concept lookup, all admission-boundary repairs and the
existing root/sense/realization/hold assertions.

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_historical_abi_contract.py`:
10 passed, 2 skipped because the full historical checkpoint is not mounted.

The host MLX-capable Python ran
`scripts/run_tests.py bilqis_mlx/semantics/tests/test_token_atlas.py`: 3 passed,
1 skipped because the historical checkpoint is not mounted.

`scripts/skos_test_policy.py plan --base-ref bd3a3ce0450c5f4b0b7f9aadade7db42c3ccc1bd`:
`SKOS_VERIFIED_BUNDLE_UNCHANGED ... FULL_SUITE_SKIPPED`.

`python3 -B scripts/error_control_plane.py --check` reports zero
`bilqis_mlx/semantics/atlas_projection.py` debt. The repository-wide gate still
exits nonzero for nine inherited literal-error findings in shared scheduler,
plasticity and runtime owners outside this Lane A change; those findings were
already present in the unified base and are not waived or modified here.

`git diff --check`: passed.

Independent EGM review of the cohesive A01 three-leaf batch remains pending.
