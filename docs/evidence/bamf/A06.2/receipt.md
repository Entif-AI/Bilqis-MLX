# A06.2 | Immutable local AtlasFeatures/v2 export

- Issue: #412; parent A06 #352; Lane A
- Consumed unified trunk: `6e83c0f6618f81a6d41f82503f16a80b8e14164f`
  (already an ancestor through merge `982ba51127b7e851cd795039644565bc3625ebaa`;
  no no-op merge)
- Direct prerequisite: A06.1 #411, independent EGM PASS at `b3bea14`
- Implementation head: pending commit/push
- Independent EGM: **PENDING**

## Owned API and source boundaries

`bilqis_mlx/semantics/atlas_feature_io.py` provides:

- `persist_feature_manifest(features, output_root) -> FeatureArtifactReceipt`
- `load_feature_manifest(bundle_dir, expected_bundle_id=...,
  expected_feature_digest=..., expected_semantic_release=...,
  expected_source_bundle_id=..., expected_atlas_bundle_id=...,
  predecessor=...) -> AtlasFeatures`

Input is the frozen `bilqis.atlas-features/v2` manifest from A06.1.
The export envelope is `bilqis.atlas-feature-artifact/v2`, and
the receipt is `bilqis.atlas-feature-artifact-receipt/v1`.
The manifest and feature payload use canonical sorted-key UTF-8
JSON with SHA-256 digests. The bundle directory name is the exact
manifest-content SHA-256. The payload is checked against its
file digest, the manifest against its directory identity, and
the parsed typed record against the manifest's feature digest
and release/source/Atlas provenance. The reader rejects
noncanonical payloads, foreign pins, unexpected files, symlinks,
malformed maps and mismatched predecessor assignments.

Publication uses a same-directory temporary bundle, fsynced
payloads, directory sync, atomic directory rename, and a
readback before returning its receipt. A retry with the same
content verifies the existing artifact; a drifted existing
artifact is rejected rather than silently overwritten.
These are local disk artifacts, not network services.

A02 initialization and B02 embeddings can load and pin this
immutable manifest, then call `features_for` entirely in memory.
No A02/B02 neural wiring or live optimizer operation is claimed
by this leaf.

## Independent golden-vector evidence

`bilqis_mlx/semantics/tests/reference_atlas_features.py`
is a standalone standard-library SHA-256 reference script,
independent of the production feature compiler. Its exact
canonical output is committed as
`docs/evidence/bamf/A06.2/golden_vectors.json`.
The test checks full 128-dimensional overflow vectors for
two beyond-capacity IDs, the disconnected Graph64 literal,
and opposite-sign channel-47 collision accumulation.
It also checks byte-for-byte regeneration of the committed
fixture without updating it.

## Verification

- Focused A06.2 and A06.1 suites: **20 passed, 0 failed,
  0 skipped** before independent review.
- Reordered source rows produce the same content-addressed
  artifact and local readback.
- A successor preserves prior category rows and held-source
  reasons. Deliberately drifted predecessor assignments fail.
- An offline socket trap covers local load plus
  `AtlasFeatures.features_for`.
- Corrupt payloads, wrong expected pins, unexpected files,
  symlink aliases and non-finite JSON fail closed through
  the ErrorBus.
- An injected disk publication failure is reported as a
  catalogued boundary error rather than leaking a raw OSError.

Parent A06 remains open for its integration gate. No public
source promotion, live training, merge into unified, or merge
into main is authorized by this receipt.
