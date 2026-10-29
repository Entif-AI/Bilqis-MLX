# B07.1 | Source-shaped motif keys and candidate-only allocation plan

- Issue: #456; parent B07 #356; Lane B.
- Candidate source: `bilqis_mlx/learning/atlas_engram.py`.
- Input schema: A03 `bilqis.semantic-frame-instance/v2`,
  `bilqis.semantic-frame-schema/v1`, `ConceptRef/v1` and
  `ChildFrameRef/v1` consumed through narrow read-only protocols.
- Output schemas: `bilqis.motif-key/v1`,
  `bilqis.motif-manifest/v1`,
  `bilqis.motif-allocation-plan/v1`,
  `bilqis.motif-candidate-view/v1`.
- Upstream A03 source: independent EGM PASS at `4c422aa`,
  available on Lane A; not yet merged into unified.
- Independent B07.1 EGM: **PENDING**.
- Integration/issue closeout: **BLOCKED** until the actual A03
  implementation arrives through the reviewed unified branch.

## Implemented candidate behavior

Immutable motif keys bind semantic release, frame schema/revision,
ordered role/occurrence/typed filler identities, source-schema
relation structure and source-owned scope. Exact keys preserve
canonical concept IDs or child-frame content identity; structural
keys use only A03-admitted type IDs, preserving role/occurrence,
binding state and relation shape. Unknown, absent and alternative
states remain distinct. No English gloss, guessed source meaning,
neural tensor or independent frame parser is introduced.

`prepare_motifs(frames,parent_manifest,budget)` reads the
accepted immutable parent manifest, tries exact then structural
keys, and plans missing structural keys before exact instance
keys. New slot IDs are append-only and limited to 64 per
candidate. Within each class, observed use is sorted descending,
then the full canonical key digest ascending. A full-key
comparison follows every hash-bucket lookup, including a
test-only forced collision. Unallocated keys remain explicit
pending evidence and a miss returns factorized fallback,
without creating a trainable residual.

Page growth, deterministic vector initialization, optimizer
custody and accepted-generation publication remain B07.2/B07.3.
No live student, checkpoint or optimizer state was mutated.

## Focused prime proof

`python3 -B scripts/run_tests.py
bilqis_mlx/learning/tests/test_atlas_engram_allocation.py`:
**13 passed, 0 failed, 0 skipped** after the child-frame
and empty-optional-frame review repairs.

Literal tests cover distinct fillers sharing structural type
keys, exact role-swap/scope/child differences, distinct child
occurrences with identical child content, NONE/UNKNOWN/
ALTERNATIVES, foreign release/schema/type rejection, exact
lookup priority, structural-first deterministic use/digest
ordering, 64-key cap, pending-key evidence, zero-budget
fallback, append-only manifest invariants and forced
bucket collision without false hits.

The tests currently use an exact-shape A03 v2 protocol fixture,
not a copy of A03 constructors. A real FrameInstance/FrameSchema
integration witness and authoritative source-grant boundary are
required after the upstream source reaches unified. This is a
bounded candidate, not a completed source-admission or
neural-memory release.

## Independent review findings and scoped repair

Goldfish worker-4 found two Majors at immutable `5c75f04`:
structural child relations retained an exact child content
digest, and legal A03 frames with zero bindings were rejected.
Both are reproduced and repaired locally. Exact child keys
retain occurrence/content identity, while structural relation
signatures use admitted child types and role/occurrence shape.
An empty frame with optional roles now receives distinct
canonical exact and structural keys. The focused suite passes
**13/13**; a fresh immutable-head review is required.

Independent adversarial review separately identified that
duck-typed protocol fixtures cannot prove A03 source/ABI
admission or canonical frame construction. This is an
**unresolved source-authority gate**, not a waiver. The
candidate must not be wired into a production training or
allocation path, pushed as accepted B07.1, or closed until
real A03/A13 source authority can be consumed through unified.

## 2026-10-29 source-authority integration candidate

The reviewed unified head `6b54600` now contains the actual A03
frame/schema and A13 context eligibility modules. The isolated
B07.2 continuation branch consumed that exact unified head at
`590c1cb`, then added `atlas_engram_source.py` as a narrow
**private integration probe**, not a production admission entrypoint.
It calls A13 `project_context` before
any motif preparation, returns a `ContextHold` without allocating
when rights or visibility fail, and reuses A03
`validate_frame_bindings` against the frozen source snapshot.
It requires exact native FrameInstance/FrameSchema records and
active admitted ABI identities. Atomic fallback positions remain
source-visible without minting a motif slot.

The new package-local `test_atlas_engram_source.py` uses real A03
FrameInstance/FrameSchema and A13 SourceGrant/SourceFrontier
records. **5/5 tests passed**, covering successful source-approved
allocation, revoked member grants, forged but role-allowed concept
types, inactive source-qualified ABI, and missing/foreign
schema or release. The pure B07.1/B07.2 planner remains separately
testable without importing the Atlas RDF dependency.

This provides a source integration testbed, but is **not B07.1
acceptance**. No public/source rights or neural custody were promoted.

## Independent adversarial disposition: BLOCKED

Goldfish review at immutable `db724ba`, using pinned EGM
`b3a3595`, reproduced **two Blockers** despite 5/5 source
integration tests passing:

1. A same-ID/revision caller-supplied FrameSchema can change
   `ast_construct` or `scope` and produce different motif keys.
   Neither A03's FrameInstance nor the current source snapshot
   carries a verified immutable schema-body authority for B07.
2. Caller-minted A13 SourceGrant records with recomputed evidence
   digests can authorize a forged frame. A caller-supplied formal
   source graph can likewise reassign types while matching its own
   digest. The current API lacks independently verified source
   issuer provenance for the schema/grants.

The experiment is therefore renamed `_probe_approved_motifs`
and explicitly forbidden as a production admission API.
Actual B07.1 closure requires A03-owned immutable released
schema authority and A13 source-issued grant provenance,
followed by fresh EGM and human-reviewed Lane B integration.
No acceptance was inferred from matching source IDs, local
hashes or synthetic grants.
