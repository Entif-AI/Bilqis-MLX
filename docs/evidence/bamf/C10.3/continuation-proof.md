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
