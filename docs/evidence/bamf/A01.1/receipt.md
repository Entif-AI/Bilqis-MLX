# A01.1 source-qualified Atlas projection evidence

Issue: #396
Lane: `codex/bamf02-a-semantics`
Consumed unified head: `44f78431709ec3b8fc23f47b45d9b18f167c7354`
Starting lane head: `4a700e42963271e41403a5ad0287113fbf00f79e`
Review disposition: `EGM_PENDING`

## Implemented contract

`compile_atlas_release(corpus_dir, coverage_receipt, prior_abi, formal_domain_bindings)` now binds one immutable conformance evidence bundle to deterministic Atlas records. The compiler verifies the bundle manifest and every constituent digest, validates the source-owned coverage receipt, requires all four conformance gates, verifies canonical RDF and independent comparison bytes, reconciles the independent source-row census, and rejects stale coverage before constructing a release.

The projection preserves source-qualified root and Stem x Specification sense identities separately. Source notations are realizations attached to those identities. Types, URI relations, source loci and labels come from canonical RDF. Non-admitted mapping rows remain held/rejected records and never become active semantic records. Boolean and numeric authorities remain explicit formal-domain bindings with independent source-owner digests.

## Real canonical witness

Pinned conformance bundle: `f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`

- canonical RDF SHA-256: `7a0a0cd04133be41db69ca3fe1e2f09b4efbc8c965610b75c5ac30bc0954b50e`
- canonical RDF triples: 130173
- coverage SHA-256: `73a249c1dfff4c9cda382808b5d0bf87c8912bb04b3ac8b805675262007c6461`
- independent source-row SHA-256: `f500cad84f390e4f5abb35d66ac8f5d171fdf5e13e3aa44c1432e2b2dd225c76`
- conformance SHA-256: `276edfe06bface167883ea779a221983e2ba307a2263b64f5a9be9501cdb7cf8`
- source rows: 25692
- conformance: coverage, no-omission, determinism and SHACL all passed; declared source coverage remains `partial`
- projected source-qualified identities: 104 concepts, 5967 roots and 3008 senses
- preserved mapping non-admissions: 552 held/rejected rows
- projected realizations: 6186
- projected source loci: 9085
- projected URI relations: 6120
- formal-domain bindings: Boolean and numeric
- deterministic Atlas release SHA-256: `a39ca2eb1ccce4c52d0ea6ed9444171b3a8ec4fdcd6c46b85fdc7c84bc7c0bbe`

This witness consumes the published canonical source bundle. It does not claim a new raw-source extraction replay or complete New Ithkuil coverage.

## Verification

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_atlas_projection.py`: 3 passed, 1 real-corpus witness skipped when the external witness is absent.

The same test file with the pinned real-corpus witness enabled: 4 passed, 0 skipped. This covers deterministic repeat compilation, literal root/two-sense identity separation, multiple realizations on one root, stale-coverage rejection, held-identity non-admission, exact real corpus census and explicit Boolean/numeric bindings.

`scripts/run_tests.py bilqis_mlx/semantics/tests/test_historical_abi_contract.py`: 10 passed, 2 skipped because the full historical checkpoint is not mounted. The source-level historical ABI prefix and meaning/index guards pass.

`scripts/skos_test_policy.py plan --base-ref 4a700e42963271e41403a5ad0287113fbf00f79e`: `SKOS_VERIFIED_BUNDLE_UNCHANGED ... FULL_SUITE_SKIPPED`.

`git diff --check`: passed.
