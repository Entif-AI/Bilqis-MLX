# C10.3 staged-projection continuation

## Scope and status

Issue #521; parent #383; Lane C #344. Feature
`codex/bamf02-c10-521-staging-20261030` begins at Lane C
840e6ce0664c98ffb6d190ca9581b99d3e19ab9b, consuming unified
a02b9ed4. Local staging remains provisional. Actual Rosetta/FalkorDB service,
source/rights qualification, accepted-generation producer coverage and the
unmerged #520 atomic-batch repair remain outside this patch's acceptance.
No closing keyword is appropriate for the full leaf yet.

## Changes

Encountered directory interruptions reduced runtime from 67 to 12 direct Python
files and tests from 69 to 12. Physical grouping follows existing draft #614;
it does not import its atomic-batch behavior. Canonical module names and class
identities remain stable. Teacher fingerprint keys remain stable while source
bytes resolve through canonical modules in both Runtime and Learning.

The organically encountered 393-line staging module is now a 39-line facade
plus cohesive contracts, queries and storage owners. Staging tests mirror those
owners and remain below 240 lines. The extraction retained exact canonical JSON
and digest f2e8dd9fd48787ceb1d360798f77011bf84be2ff574ff9fa127d8c693901cd90
captured from the pre-extraction code.

Two red/green repairs follow the committed extraction:

1. Verification previously minted a fresh proof over mutated census/domain/stage
   identity fields. Invalid nested events also escaped typed error handling.
   Verification now revalidates the stage and every public event before computing
   any proof. Rejected candidates preserve the prior active stage.
2. Cold reads previously accepted a different, internally valid stage stored under
   the requested stage's key. Reads now bind the requested key and persisted census
   digest to the decoded canonical stage. Active reads fail closed on substitution.

## Reproduction

Use Python >=3.11 with cryptography, numpy, rdflib and pyshacl installed. Run:

```sh
python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/projection
```

Current local result: 28 passed, zero failed/errors, one explicit Rosetta contract
workspace skip. This is CPU/local-ledger evidence, not external service replay or
retained-learning acceptance. Existing canonical import checks cover module
lookup, rejection of alternate names, teacher byte fingerprints, source class
identity and the qualification command's repository root.

The new regression methods are in test_akasha_staging_queries.py and
 test_akasha_staging_store.py. The first red run had two failing methods with
seven subtest failure/error outcomes; scripts/run_tests.py printed a negative
passed count for that failing subtest run. This pre-existing reporting defect is
not interpreted as a valid test total. The store substitution test failed before
its repair. Both regression suites pass after repair.

## Review

Pinned EGM b3a35956759bf7f024af2ff061b2e0b44b438e4c readiness found three Majors
in the extraction dispatch. The plan was amended with exhaustive symbol/test
ownership and the extraction checkpoint. One targeted re-audit returned PASS,
zero remaining Blockers/Majors. Fresh implementation review is pending.

## Rollback and integration

Review may reject this feature branch without changing unified. Existing feature
branches #610/#614 and old staging generations remain intact. SQLite pointer
conflicts and invalid verification leave the prior stage readable. Runtime/test
layout overlaps #614 intentionally; choose one reviewed structural lineage at
integration and resolve duplicate moves rather than reverting either feature.

## Observable staging contract

`PublicEvent` contains event_id, subject_digest, payload_digest,
source_receipt_sha256, release_digest, model_digest, evaluator_digest and
rights_digest, each a lowercase 64-character SHA-256 hex string; an
`AkashaEventKind` kind; nonnegative integer source_time, effective_time,
observed_at and recorded_at; and schema_version `bilqis.c10.public-event/v1`.
observed_at must not exceed recorded_at. Explicit owner-fixture categories
cannot enter this public schema. No raw subject, payload or source path is copied.

`StagingProjection` contains a tuple of PublicEvent records sorted by unique
event_id, a sorted tuple of `(kind.value, count)` census pairs, domain_digest,
stage_digest and schema_version `bilqis.c10.staging-projection/v1`. Counts are
recomputed from the complete event tuple. Canonical JSON uses sorted keys,
compact separators, UTF-8 without ASCII escaping and rejects NaN. Tuples serialize
as JSON arrays; kind serializes as its enum value. The stage identity payload
contains schema_version, domain_digest, census and public_events. stage_digest
is SHA-256 of that canonical payload. canonical_json adds stage_digest to the
same payload. Subject identity is SHA-256 of the canonical JSON subject string.
Domain identity comes from ProjectionDomainContract, excluding its local path.

`VerifiedStage` contains stage, census_digest, bounded_query_digest, proof_digest
and schema_version `bilqis.c10.verified-stage/v1`. The census digest hashes the
canonical census. The bounded-query digest hashes one `(kind.value, event_ids)`
result for every AkashaEventKind in enum order, limited to 100 per kind. Proof
identity hashes stage_digest, census_digest and bounded_query_digest. Verification
revalidates the stage and every nested public event before minting this proof.

`query_public_projection(stage, limit, kind=None, as_of=None)` requires an integer
limit in 1..100 and returns records in event_id order. Optional kind filters by
enum identity. Optional as_of is a nonnegative integer and includes an event only
when both recorded_at <= as_of and effective_time <= as_of. This conjunctive
inclusive boundary is distinct from source_time/observed_at. Query results expose
only PublicEvent fields. This local read API does not grant source rights or
external graph query authority.

`PromotionReceipt` contains optional previous_digest, active_digest,
census_digest and schema_version `bilqis.c10.promotion-receipt/v1`.
`promote_staging_projection(path, verified, expected_active_digest=...)` recomputes
the proof, starts SQLite BEGIN IMMEDIATE, compares the active pointer, inserts
an immutable stage if absent and updates one pointer in the same transaction.
None as expected_active_digest means the caller expects no existing active
pointer; it is not a wildcard. A stale expectation fails without changing the
pointer or stage history. Existing rows must match canonical JSON and census
identity exactly. SQLite uses foreign keys, WAL and append-only stage triggers.

`read_staging_projection(path, digest)` returns None for a missing database or
missing stage. Otherwise it validates canonical records, requested digest and
persisted census_digest. `read_active_projection(path)` returns None for a
missing database or missing active pointer; otherwise it uses the same verified
stage read. Neither API guesses a replacement on invalid storage.

Boundary errors use BilqisError through SCHOOL.BAMF_AKASHA.INVALID. Specific
reasons retained by this patch include BAMF_C10_PUBLIC_EVENT_INVALID,
BAMF_C10_STAGING_PROJECTION_INVALID, BAMF_C10_STAGING_CENSUS_DRIFT,
BAMF_C10_STAGING_DIGEST_DRIFT, BAMF_C10_STAGING_STORED_INVALID,
BAMF_C10_STAGING_PROOF_INVALID and BAMF_C10_STAGING_POINTER_CONFLICT.
Source wrappers that disagree with the selected domain reject with
BAMF_C10_STAGING_DOMAIN_DRIFT; queued envelope rebinding rejects with
BAMF_C10_STAGING_DURABLE_BINDING_DRIFT. These checks are local consistency
boundaries, not a substitute for accepted source/rights/service qualification.
