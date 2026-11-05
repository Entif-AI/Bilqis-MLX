# BAMF-0.2 A12.2 cutover and rebuild receipt

Issue: #428
Existing owner: #295
Lane: A
Reviewed-unified base consumed: `7c8974191f5c9c5449f1056149776771ad2b72f3`
Cutover implementation checkpoint: `a9662001f84aa61fcfedfc2c91ca68c314001a21`
Branch: `codex/bamf02-a12-2-428-20261105`
Disposition: implementation candidate; exact-head review and hosted acceptance still required.

## Cutover result

Current repository callers no longer import the legacy
`bilqis_mlx.semantics.atlas_snapshot` alias. They import the canonical owner
`bilqis_mlx.semantics.atlas.snapshot` directly. The legacy alias remains
registered by `bilqis_mlx.semantics.__init__` only as a historical public-import
compatibility surface; a boundary rule now rejects its use by current code.

The same declaration table classifies the other Atlas compatibility aliases as
legacy-only and distinguishes them from current Atlas owners. Historical public
facades such as `atlas_projection.py` remain explicit compatibility/read-only
surfaces rather than being confused with a second source of semantic authority.

## Source-to-consumer table

| Consumer / former source | Declared role after cutover | Authority / rebuild binding |
| --- | --- | --- |
| A01 pinned Atlas snapshot | `CURRENT_SOURCE_OWNER` | Canonical semantic release, source bundle, Atlas bundle and source-owned hold reasons |
| A02 `VocabularyExtension` | current ABI projection | Replayed from the pinned A01 snapshot and predecessor ABI; exact semantic IDs and indices |
| A03 released frame schemas | `DERIVED_SOURCE_FACADE` | Pinned derived-source manifest bound to the same A01 release/bundle/source |
| A08 `SourceConstructiveLessonSet` | current lesson projection | Replayed against the same release and source/formal semantic identities |
| A12 graph projection | `HISTORICAL_COMPATIBILITY_FACADE` for the public facade; current projection is derived | Deterministic digest over the pinned snapshot; cannot redefine source identity |
| Registry mirror | current derived ABI projection | Rebuilt from A02 allocation digest, predecessor, active indices and exact rows |
| `copular_registry_v1.json` | current predecessor/prior-ABI ledger | Historical accepted ABI continuity; not an independent current semantic source |
| `atlas_source_pins_v1.json` | current source pin ledger | Selects the admitted source release; does not mint a parallel meaning |
| `frame_schema_source_pins_v1.json` | current derived-source pin ledger | Selects admitted A03 derived schemas; does not override A01 identity |
| `semantics.atlas_snapshot` and sibling Atlas aliases | `LEGACY_COMPATIBILITY_ALIAS` | Historical decode/import compatibility only; current imports are rejected by the architecture guard |
| declared formal-domain bindings | legitimate separate formal authority | Kept explicit and digest-bound; not forced into SKOS under #295's stop rule |

## Rebuild receipt

A12.2 reuses the already accepted A12.1 typed `AuthorityReceipt` rather than
inventing a second receipt type. That receipt binds the source release, source
bundle, Atlas bundle, ABI, AST/frames, lessons, graph projection, registry
mirror, prior ABI and declared formal-domain digests. The accepted A12.1 real
producer witness performed two independent full regenerations from the pinned
A01 source/artifact authority and proved deterministic release/bundle,
consumer bindings, audit digest, graph digest, selected new semantic,
append-only ABI allocation and unchanged prior indices. Its expensive semantic
proof is reused here because this child changes import ownership/control-plane
paths, not the underlying semantic producers or receipt algorithm.

A12.2 adds a rerunnable repository guard around that proof. The guard declares
canonical/current, derived, compatibility-facade and legacy-alias roles and
fails if current code imports a legacy Atlas alias. The compatibility test also
proves the retained `semantics.atlas_snapshot` alias resolves to the exact same
module object as `semantics.atlas.snapshot`, preserving historical import
decoding while denying it current-source authority.

## #295 acceptance matrix

| #295 acceptance criterion | Exact-branch disposition |
| --- | --- |
| Current ABI names one canonical semantic release | SATISFIED by A12.1 `AuthorityReceipt` replay |
| Current AST semantic bindings name the same release | SATISFIED by A03 pin validation in A12.1 |
| Current lesson/curriculum manifest names the same release | SATISFIED by A08 replay in A12.1 |
| No current execution path can silently override semantic identity from a second registry/source | SATISFIED by A12.1 source replay plus A12.2 caller cutover/guard |
| Historical compatibility sources are explicitly translation/read-only | SATISFIED by declared dispositions and compatibility-role table |
| Stale shadow source cannot change current generated semantics | SATISFIED by accepted poisoned historical-loader A12.1 regression |
| Architecture/code-ownership guard prevents reintroduction | SATISFIED by `scripts/check_semantic_boundaries.py` declarative import roles and negative legacy-alias regression |
| Clean rebuild produces same semantic lineage across ABI, AST and lessons | SATISFIED by accepted two-regeneration A12.1 witness; receipt reused because this delta is nonsemantic import/control-plane cutover |

Candidate conclusion: #295's existing acceptance is satisfied by the combined
A12.1 + A12.2 branch surface, subject to #428 exact-head review, hosted checks
and accepted merge into reviewed unified. #309 remains a separate combined-
candidate qualification owner and is not silently closed by this leaf.

## Verification performed on the cutover candidate

- `python3 -B scripts/check_semantic_boundaries.py` -> `SEMANTIC_BOUNDARIES_OK`
- semantic boundary/A12 source-free suite -> 15 passed, 12 subtests
- Factory/curriculum affected surface -> 223 passed, 13 expected skips, 78 subtests
- runtime/source-adapter affected surface -> 5 passed, 16 expected skips, 2 subtests
- development-structure check -> 0 violations
- Factory architecture -> green
- BAMF flow control -> green, Lane A ACTIVE 1/6
- changed-file smell -> 0 findings
- error-control plane -> new debt 0
- `git diff --check` -> clean

One unrelated inherited learning-layout assertion reports 36 owner files while
its literal expected count remains 32. This A12.2 patch adds no learning files
and does not change that layout test; it is recorded as baseline debt rather
than being repaired from Lane A.

## Non-claims

- No neural training, optimizer mutation or source-gold change occurs here.
- No historical compatibility artifact is deleted.
- No legitimate formal domain is collapsed into SKOS.
- A12 parent #364 remains open because A12.3/#429 remains after this leaf.
