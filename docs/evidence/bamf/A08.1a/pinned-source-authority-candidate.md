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

`AtlasArtifactSelection/v1` carries an A01 artifact path and claimed
bundle/release/source IDs, but those caller fields are **not** an
authority. The A01 reader first checks them against the repository-owned
`atlas_source_pins_v1.json` whose exact canonical bytes are pinned by
`ATLAS_SOURCE_PIN_REGISTRY_SHA256` in source code. The registry contains
the A01.2 real-corpus receipt identity and explicitly labels it
`A01_SOURCE_ATTESTED_NOT_NEURAL_ADMITTED`. Only then does the existing
database-free reader verify every artifact member and manifest digest.

All four public A08 census, compiler, lesson and checker entrypoints
take a selection and **reload the verified artifact at the consuming
boundary**. There is no caller-constructible in-memory authority
wrapper. Internal pure snapshot functions remain separate for literal
algorithm tests, not for public source admission.

Adding a future source release requires an explicit, reviewed registry
and code-pinned digest update; a caller cannot self-attest a repacked
artifact by changing the expected bundle ID.
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
  different A01 bundle ID. It fails both the **original** trusted pin
  and a forged **self-attested replacement** pin before any public
  census is returned.
- All public A08 paths reject raw caller-replaced snapshots. The
  removed wrapper cannot be forged with a leaked issuer or mutated
  with `object.__setattr__` because no such wrapper exists.
- The original real A01 bundle identity
  `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
  remains unchanged. The real census remains 9,307 eligible identities
  and 12,351 required obligations, with no learning credit.
- `git diff --check`: clean. Static error-control and module-size
  checks introduce no new findings beyond inherited unrelated debt.

## Independent review and repair history

Goldfish reviewed immutable `ae2faa1` and returned **EGM NOT PASS**:
zero Blockers, one Major. The initial implementation treated a
caller-mintable selection and an in-process wrapper as source authority.
The reviewer reproduced single-ID and equal-cardinality same-family
substitution using a repacked manifest/new caller pin, plus issuer-token
and `object.__setattr__` wrapper forgery.

The repair removes the wrapper entirely, introduces the repo-owned
SHA-pinned A01 source registry, and reloads the artifact at each public
entrypoint. The original v1 artifact identity is preserved. The
expanded real-corpus tests now reject both self-attested repack forms.
**Fresh independent immutable-head re-review remains required.**

## Second EGM Major: unverified helper authority separation

Goldfish independently reviewed `f8b90c1` and returned **EGM NOT
PASS**, zero Blockers and one Major. Although public entrypoints
reloaded the pinned artifact correctly, four raw-snapshot helpers
could still emit the same authoritative schemas from a caller-forged
snapshot bearing the trusted A01 identity strings. The reviewer
reproduced an eight-concept fake census and a true checker result
under those strings.

The repair now distinguishes source *projection* from source
*attestation* mechanically. Raw-snapshot helpers emit only
`UNVERIFIED_SOURCE_PROJECTION` records with separate unverified
schema IDs. Their checker returns a typed
`UnverifiedSourceFactCheck`, whose implicit Boolean conversion
fails closed. Public A08 entrypoints reload the independently
registry-pinned artifact, then issue distinct
`A01_PINNED_SOURCE_ATTESTED` census/candidate/lesson schemas.
Public checking requires an attested lesson and rechecks the
underlying source, never accepting a fixture result as authorization.

The exact reviewer attack is a regression: an eight-concept fake
snapshot with all three trusted A01 identity strings still produces
only unverified schemas, and its fact-check result cannot be used as
a Boolean. Public consumers reject raw snapshots, unverified lessons,
and forged census inputs. The real pinned A01 owner suites now pass
**29/29**, zero failures/skips. This is source attestation only,
not live A13 rights or neural admission. Fresh EGM review of this
second repair is still required.

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
