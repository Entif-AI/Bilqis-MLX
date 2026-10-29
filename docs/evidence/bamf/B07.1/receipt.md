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
**10 passed, 0 failed, 0 skipped**.

Literal tests cover distinct fillers sharing structural type
keys, exact role-swap/scope/child differences, NONE/UNKNOWN/
ALTERNATIVES, foreign release/schema/type rejection, exact
lookup priority, structural-first deterministic use/digest
ordering, 64-key cap, pending-key evidence, zero-budget
fallback, append-only manifest invariants and forced
bucket collision without false hits.

The tests currently use an exact-shape A03 v2 protocol fixture,
not a copy of A03 constructors. A real FrameInstance/FrameSchema
integration witness is required after the upstream source
reaches unified. This is a bounded candidate, not a completed
source-admission or neural-memory release.
