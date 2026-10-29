# A06.1 deterministic AtlasFeatures/v2 projection | implementation receipt

- Issue: #411; parent A06 #352; Lane A
- Consumed unified trunk:
  `44f78431709ec3b8fc23f47b45d9b18f167c7354`
  (already an ancestor; no no-op merge)
- Consumed A01 frozen Atlas source and A03 typed frame/ConceptRef contracts
- Branch: `codex/bamf02-a-semantics`; candidate head pending push
- Independent EGM: `PENDING`

## Contract and exact mapping

`bilqis_mlx/semantics/atlas_features.py` implements
`build_feature_manifest(release, feature_schema) -> AtlasFeatures`
and `AtlasFeatures.features_for(concept, role, schema, scope) -> FeatureRow`.
The feature compiler consumes a frozen `FrozenAtlasSnapshot` and
explicit source-owned role/schema IDs. No model, optimizer, live
graph query, independent assessment or network call is required.

Schemas:
`bilqis.atlas-feature-schema/v2`,
`bilqis.atlas-features/v2`,
`bilqis.atlas-concept-feature/v2`,
`bilqis.atlas-feature-row/v2`.

Three independent append-only categorical maps assign
`UNKNOWN=0`, `NONE=1`, then UTF-8-sorted IDs to rows 2..511.
Successor releases retain every prior assignment and append new
IDs only into unused rows. Overflow remains at UNKNOWN row 0
but carries its exact source ID plus deterministic f128
SHA-256 byte expansion. Identity is never reconstructed from
the factor vector or a collision-prone hash.

Graph64 channels 0..6 are
`min(log1p(count)/log(1025), 1)` for incoming, outgoing,
outgoing SKOS broader, outgoing SKOS narrower, type count,
source form/notation count and attested sense-source-row count.
Channel 7 is the unresolved-source-mapping flag.
Channels 8..63 are signed SHA-256 hashes of admitted incident
relation signatures with exact neighbor types, direction and
predicate, normalized by signature count. Only admitted
SKOS semantic/membership relations whose endpoints are active
enter this graph; held or unqualified relational-IR-only
predicates do not enter. No taxonomy prerequisite is inferred.

The complete active ABI, including formal identities without
Atlas concept rows, receives exact ID sidecars and an explicit
untyped/unresolved status instead of invented types. The
manifest binds source bundle/release and its predecessor
feature digest. A supplied `ConceptRef` must match release,
ABI index and authoritative type IDs before feature lookup.

## Prime tests

`PATH=/Users/emilie/Code/bamf-planning-20261027/.venv/bin:$PATH python -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_atlas_features.py`:
**10 passed, 0 failed, 0 skipped**.

Literal witnesses cover the one-type disconnected vector
(channel 4 = log(2)/log(1025), other channels zero),
signed SKOS graph hashing, role swap preserving identity,
held/relational-IR-only edge exclusion, source form/sense
counts, 512-row overflow f128, lexical successor stability,
source row reorder stability, foreign/forged ConceptRef
rejection, and all 228 current formal source ABI identities
projected without network or invented type claims.

Repository module-size check retains three inherited
shared-runtime findings; no new A06.1 module-size finding.
`git diff --check` passed.

A06.2 owns corpus-wide persisted manifest/readback,
release pinning and successor proofs. A06 parent integration
and downstream training admission remain open.

## 2026-10-28 unified sync and independent review repairs

Consumed current unified `6e83c0f6618f81a6d41f82503f16a80b8e14164f`
through Lane A merge `982ba51127b7e851cd795039644565bc3625ebaa`.
The three initial Goldfish Majors at `a02a64d` were:
root-side sense count missing source-owned sense links;
arbitrary role/schema IDs admitted as learned categories;
and a foreign predecessor accepted without A01 lineage proof.

The feature compiler now counts attested sense concepts
linked to a root by canonical qualified hasSense or admitted
SKOS narrower/broader source edges. A source sense is counted
only if its own frozen concept carries a lexicon_root_senses
source row. Role and schema IDs are checked against A03's
exact pinned source graph, active frozen ABI index/symbol
and released FrameSchema construction; a caller cannot
allocate invented source rules. Synthetic overflow maps
are tested as pure factor-map fixtures, not as source
admission. The predecessor feature manifest carries the
exact A01 atlas bundle ID, and a successor's
`prior_abi_sha256` must equal that bundle ID.

Focused owner suite remains **10 passed, 0 failed**,
including root/sense link fixtures, forged source
role/schema and ABI-index negatives, foreign predecessor
and 512-row overflow. Independent immutable-head EGM
re-review is pending; this is not an A06 parent closeout.
