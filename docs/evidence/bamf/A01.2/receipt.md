# A01.2 deterministic semantic ABI and release evidence

Issue: #397
Lane: `codex/bamf02-a-semantics`
Consumed unified head: `44f78431709ec3b8fc23f47b45d9b18f167c7354`
Consumed A01.1 lane head: `20c97c19a092b05703f1beaf7c645228d703fed5`
Review disposition: `EGM_PENDING`

## ABI authority and allocation

The predecessor row ledger is the repository-owned verified native readback
`bilqis_mlx/semantics/copular_registry_v1.json`, SHA-256
`30d18c7140d49c168488416e04644b934ea79492561c2b73f65e55be18ed4e8c`.
Its legacy envelope has no schema field, so the compiler records the input schema
as `UNVERSIONED` rather than inventing one. The ledger contains 228 contiguous
accepted rows at indices 0 through 227. Local source-staging evidence records that
index 227 was appended after the already admitted numeric rows while preserving
indices 0 through 226.

The Atlas compiler verifies that predecessor native-row digest and preserves every
prior row's index, symbol and semantic identity. New source-qualified semantic IDs
follow in canonical semantic-ID order. Logical ABI addresses use one fixed 8192-row
bank size with `index = 8192*bank + row`; newly projected rows remain masked until
an independently authorized admission transition. This leaf allocates semantic ABI
addresses only. It does not allocate or mutate model tensors, optimizer moments,
checkpoints or live student state.

Shape-policy SHA-256:
`72eef37c3d6225a50ed4ace7b389c34d6442e9917facd103d30c726aaa05f197`

Active-set SHA-256:
`173287b6e9ea90e4f9d88dc6ddb136772828a0cafcd47bda952d24f9da433790`

## Real canonical witness

The source release is the pinned conformance bundle
`f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`
with canonical RDF SHA-256
`7a0a0cd04133be41db69ca3fe1e2f09b4efbc8c965610b75c5ac30bc0954b50e`.
All four existing source conformance gates pass. Coverage remains correctly
declared `partial`; this receipt does not claim a new raw-source extraction replay
or complete New Ithkuil coverage.

The compiled release keeps the required count domains separate:

- source rows: 25692
- distinct RDF terms: 67448
- source-qualified semantic identities: 9079
- logical ABI entries: 9307
- logical 8192-row ABI banks: 2
- active prior ABI indices: 228
- declared trainable formal capabilities: 4
- source-held rows: 1052
- source IR-only rows: 9488
- source-qualified implementation-uncovered identities: 9079

Every non-teaching source row carries its source disposition, implementation
status and explicit reason. Source-held identities cannot enter the ABI even when
an active learner request supplies a plausible symbol or gloss. The adversarial
test for that request fails before persistence and leaves the previously written
manifest byte-identical.

Deterministic Atlas release SHA-256:
`58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`

Content-addressed artifact bundle ID:
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`

Persisted payload fingerprints:

- `atlas.json`: `2a90023131aafb803df618f263dff639aa1088175e2138593f4314e8ec45023d` (3219992 bytes)
- `concepts.jsonl`: `c10d456a31579d4bf2b5a917f9ffc3e4d2e95f275458fb6dc0403938e28395ab` (8985170 bytes)
- `relations.jsonl`: `ac70a12785da4cc201e543ec54c5b02530ee6bcdda57dbc05c92c676cf52c938` (2069572 bytes)
- `held.jsonl`: `f86f3f94f468abc153f84483bb3380a53f284bc19a2efea98a16fbb3b974fb4c` (10252779 bytes)

The manifest itself is canonical JSON; its SHA-256 is the artifact bundle ID.
Repeating persistence for the same release verifies and reuses the exact existing
content-addressed directory rather than rewriting it.

## Verification

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_atlas_projection.py` with the
provided dependency environment: 5 passed, 1 real-corpus witness skipped when the
external witness is absent.

The same test file with the pinned real-corpus witness enabled: 6 passed, 0 skipped.
This includes deterministic compilation, prior-row preservation, canonical append
ordering, content-addressed idempotence, distinct counts, stale-coverage rejection,
held-request non-admission, and real-corpus persistence.

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_historical_abi_contract.py`:
10 passed, 2 skipped because the full historical checkpoint is not mounted.

The provided planning environment cannot import MLX, so its first attempt to load
`test_token_atlas.py` stopped at `ModuleNotFoundError: mlx` before any test ran.
The same owner test was rerun under the host MLX-capable Python and passed 3 tests
with 1 historical-checkpoint mount skip.

`scripts/skos_test_policy.py plan --base-ref 20c97c19a092b05703f1beaf7c645228d703fed5`:
`SKOS_VERIFIED_BUNDLE_UNCHANGED ... FULL_SUITE_SKIPPED`.

`git diff --check`: passed.
