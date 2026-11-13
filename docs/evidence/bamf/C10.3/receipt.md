# C10.3 | Private-safe staging, census and atomic pointer promotion

Issue #521, predecessor C10.2 #520, parent C10 #378.
Lane C `codex/bamf02-c-runtime`, reviewed unified
`6e83c0f6618f81a6d41f82503f16a80b8e14164f`.
Implementation commit:
`59f89ffc98b1f91f61c0f8d2aa42a69a90a7d0cf`.
Draft PR #550 remains human-controlled and unmerged.

## Exact owned behavior

- `bilqis.c10.public-event/v1` materializes only hashed
  event/subject/payload/source receipt and source/release/model/
  evaluator/rights identities plus source/effective/observed/
  recorded times. Raw private inputs, private paths and
  arbitrary source payload fields are never copied into
  the public staging representation.
- `bilqis.c10.staging-projection/v1` binds an immutable
  event census and deterministic stage digest. Bounded
  public queries cap at 100 events, respect recorded/effective
  as-of prefixes and expose no raw source fields.
- `bilqis.c10.verified-stage/v1` recomputes census and
  bounded-query digests before promotion.
- A separate SQLite WAL staging ledger appends immutable
  generations, with triggers forbidding historical UPDATE/
  DELETE. `promote_staging_projection` verifies the stage
  and atomically compares/updates the active pointer in
  one transaction. A stale expected pointer fails closed;
  prior generations remain readable.

## Verification and integration limits

`python3 -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_bamf_projection.py
bilqis_mlx/runtime/tests/test_akasha_outbox.py`:
**10 passed, 0 failed, 0 skipped**.
Tests cover private raw text/path exclusion, exact census,
bounded queries, future effective-time filtering, failed
compare-and-swap promotion, retained old staging generation
and successful atomic pointer update.

Static error-control and module-size checks found no new
C10-specific debt. This is a local, public-safe staging
projection ledger, not an actual FalkorDB/SKOS graph
mutation or external publication. The real SKOS projection
adapter, privacy authority, source rights and C10 parent
acceptance remain integration gates. Independent EGM is
pending. No private source, live learner, checkpoint,
network or public graph was changed.
