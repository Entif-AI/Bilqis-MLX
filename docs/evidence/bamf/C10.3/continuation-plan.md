# C10.3 continuation: staging verification and safe replay

Issue #521 owns staging census, bounded public queries, atomic active-pointer
promotion, and exclusion of raw private inputs and paths. The external graph
adapter, source/rights authority, and full parent C10 acceptance remain separate.

This feature branch was created from Lane C at
840e6ce0664c98ffb6d190ca9581b99d3e19ab9b, consuming reviewed unified
a02b9ed4. The user requires a separate feature branch and PR per issue.
No learner, optimizer, graph service, or existing feature branch is modified.

## Mandatory encountered structure repairs

Runtime had 67 direct Python files; runtime/tests had 69. Reuse the physical
owner layout already proposed in PR #614, preserving canonical runtime module
names with package search paths and rejecting alternate physical module names.
Both directories now have 12 direct Python files. These are layout changes,
not adoption of the unmerged #520 atomic-batch implementation. Existing #610
and #614 remain preserved. Teacher source fingerprints retain canonical keys
and resolve current module paths, including the reviewed Learning layout.

The next encounter is akasha_staging.py at 393 lines. Split it into imported
akasha_staging_contracts.py (immutable public/stage/promotion records),
akasha_staging_queries.py (build, queries, proof), and
akasha_staging_store.py (SQLite staging and promotion). Retain akasha_staging.py
as the canonical API facade below 240 lines. Preserve schema versions, canonical
JSON, digest payloads, error reasons, and public dataclass module identities.
Move staging-focused tests into corresponding package-local test files, each
below 240 lines, with shared fixture builders in staging_helpers.py.

## Verification and next behavior slice

Run existing staging/outbox behavior before and after the split. Assert exact
cold-read stage and pointer equality, census and bounded query results, failed
compare-and-swap rollback, and private text/path exclusion. Add regression tests
before behavior repairs. Inspect mutated immutable objects and stored data at
promotion/read boundaries, because recomputing a proof must validate its source.
Changes must preserve fail-closed historical reads and prior active pointers.

Run pinned fresh-context implementation-readiness, codebase-details, and
comprehension reviews using Google EGM b3a35956759bf7f024af2ff061b2e0b44b438e4c.
Record exact commands, test totals and unresolved upstream acceptance. Publish a
PR to unified with reproducible validation steps; do not self-merge or close
#521 on local-only projection evidence. Update all twelve tracker worksheets
where this continuation affects their existing records, preserving formulas,
validation, formatting and unrelated lane state.

## Extraction dispatch and checkpoint

Extraction is a behavior-preserving commit before any mutation regression fix.
The following symbol map is exhaustive for the original module:

- `akasha_staging_contracts`: `PUBLIC_EVENT_SCHEMA`,
  `STAGING_PROJECTION_SCHEMA`, `PROMOTION_RECEIPT_SCHEMA`, `_SHA256`, `_invalid`,
  `_sha`, `_time`, `_canonical`, `_digest`, `PublicEvent`, `_public_event`,
  `_public_payload`, `StagingProjection`, `PromotionReceipt`.
- `akasha_staging_queries`: `VERIFIED_STAGE_SCHEMA`, `MAX_PUBLIC_QUERY_LIMIT`,
  `build_staging_projection`, `query_public_projection`, `VerifiedStage`,
  `_query_digest`, `verify_staging_projection`. VerifiedStage stays beside its
  query-dependent validator; contracts never import queries or storage.
- `akasha_staging_store`: `_STAGE_SCHEMA_SQL`, `_stage_connection`,
  `promote_staging_projection`, `read_staging_projection`,
  `read_active_projection`. Storage imports contracts and queries only.
- `akasha_staging`: facade imports the existing public names and helpers from
  these owners. The moved dataclasses set `__module__` to
  `bilqis_mlx.runtime.akasha_staging` at their owning module, preserving pickle
  and API identity without importing the facade back into the owners.

Mirrored test ownership:

- `staging_helpers.py` owns `_event`, `_contract`, `_projected` copied verbatim
  from the current test file. Tests import these through
  `bilqis_mlx.runtime.tests.projection.staging_helpers`.
- `test_akasha_staging_contracts.py` owns
  `test_staging_census_bounded_queries_and_private_payload_exclusion` plus a
  literal pre-extraction canonical JSON/digest and canonical class-module test.
- `test_akasha_staging_store.py` owns
  `test_atomic_staging_promotion_preserves_old_generation_and_pointer`.
- `test_bamf_projection.py` retains the mixed durable-domain-binding test, which
  directly calls both outbox and staging. It also retains deduplication,
  domain-drift and graph-independent queue tests, importing shared builders.
- Future query regression tests belong in `test_akasha_staging_queries.py`.

Baseline: existing 11 staging/outbox tests and five canonical-import tests pass.
Capture a concrete one-event stage's canonical JSON and digest from the committed
pre-extraction source. After extraction, run all projection tests plus literal
compatibility checks. Require original module and every companion test below
240 lines, record the proof in Work Stack, commit extraction, and mark the
interruption complete. Only then resume #521 behavior inspection. Any subsequent
failure gets a separate red test and separate behavior commit; extraction itself
must not change query, validation, error, transaction, or privacy behavior.
