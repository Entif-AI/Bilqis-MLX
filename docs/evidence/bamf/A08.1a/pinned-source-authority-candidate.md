# A08.1a formal-domain authority repair candidate

Issue: #417 (A08.1a). Parent A08.1 #416 / A08 #358.
Isolated candidate: `codex/bamf02-a08-formal-authority-20261029`.
Source Lane A baseline: `915e22a884e09b2d981b55378d749db177c1ee8b`.
Reviewed unified ancestor: `6b5460032fc0b19115843cce95fe8be9582af141`.
Independent EGM: **PENDING**. This is not a leaf acceptance or parent closure.

## Source boundary

The A01 v1 artifact already commits the exact formal-domain binding set:
`bundle_id = SHA256(canonical manifest)`; the manifest commits
`atlas.json` bytes; `atlas.json` contains the full canonical formal
bindings. A bare `FrozenAtlasSnapshot` is constructible and can be
replaced while retaining the old identity strings, so A08 must not
accept it as source authority.

`AtlasArtifactSelection/v1` now carries the **independently selected**
A01 artifact path and expected bundle, release and source-bundle
digests. `load_pinned_atlas_snapshot` verifies those pins through
the existing database-free A01 reader and issues an immutable
`PinnedAtlasSnapshot`. All four public A08 census, compiler,
lesson and checker entrypoints require that loader-issued view.
The internal pure snapshot functions remain separate so literal
source-family tests can exercise construction without impersonating
source admission.

The trusted source-admission caller must obtain selection pins from
the approved A01 receipt/config, **not** from the candidate snapshot.
This repair does not itself grant a new semantic release or source
admission. It changes no A01 v1 artifact files, schema, bundle ID,
release digest, neural state, or optimizer.

## Discriminating verification

- Real pinned A01 corpus plus synthetic owner suites:
  `test_atlas_projection.py` and `test_skos_curriculum.py`,
  **28 passed, 0 failed, 0 skipped**.
- Adjacent `test_frame_adapters.py` and `test_atlas_features.py`:
  **23 passed, 0 failed, 0 skipped**.
- Repacking a same-family Boolean binding to OR or OR/XOR produces a
  different A01 bundle ID and fails the **original** trusted bundle
  pin, even when the release string is retained.
- All public A08 paths reject raw caller-replaced snapshots; the
  pinned view rejects reassignment and a wrong release pin.
- The original real A01 bundle identity
  `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
  remains unchanged. The real census remains 9,307 eligible identities
  and 12,351 required obligations, with no learning credit.
- `git diff --check`: clean. Static error-control and module-size
  checks introduce no new findings beyond inherited unrelated debt.

## Rejected alternative

Adding a new `release.json` to the existing content-addressed
artifact would bind a full release preimage, but would change the
historically pinned A01 bundle ID and require an artifact-format
migration unrelated to this A08 leaf. A local experiment proved that
regression; the candidate preserves the existing v1 artifact instead.

Next: commit this isolated candidate, obtain fresh pinned Goldfish
review against its immutable head, then integrate through the
serialized Lane A writer after its current unrelated dirty work is
reconciled. Do not self-merge the lane PR.
