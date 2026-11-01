# A09.1a immutable CurriculumSnapshot implementation receipt

Issue: #390; parent #389 / A09 #360; Lane A #342.
Replacement feature branch: `fix/bamf-a09-1a-390-clean-20261031`.
Clean source baseline: reviewed unified
`9104ce733e04fb9c82420428b18dfdbf5db49535`.
The replacement carries only A09.1a's final seven-path tree delta; the superseded
PR #613 branch is retained only as historical provenance and is not an integration
ancestor of this replacement.
Disposition: **implementation ready for review; not integrated or admitted**.

`bilqis_mlx.factory.atlas_frontier` exposes an immutable versioned
`CurriculumSnapshot`, canonical byte encoding and digest verification, a pure
initial builder, source-declared prerequisite DAG validation, and a consuming
boundary replay assertion. The snapshot records the frozen A01/A08 source
census, exact source-held and implementation-uncovered debt, staged and
admitted release identities, the verified CandidateFrontierRelease digest,
explicit READY candidate IDs, separate unverified EXPOSED and QUALIFIED
capability claims, retained mastery debt, rights/correction/policy/teacher/
qualification epochs, finite planner budgets, cursor/event generation, and
predecessor identity without conferring learner or source authority.

The mandatory structure interruption starts at
`523d4e2c134cca23ee4977a3ef2bfa7036a579c1`; compatibility cleanup is
`351393b`, and audit-exposed real-corpus test helpers are split at `92b302b`.
The current unified refresh converges on the reviewed canonical compartments
and removes four superseded pre-compartment shadow modules. The Factory and
Factory-test roots now contain 11 direct Python files each while preserving the
reviewed `bilqis_mlx.factory.<module>` import surface. The A09.1a production code is
split into a 290-line builder and 237-line immutable-contract module; its
companion test is 316 lines. No structure threshold or governance baseline was
weakened.

The repaired-schema real pinned A01 corpus replay passes with **9,307 source-eligible semantic
IDs, 12,351 required family obligations, and 1,052 source-held rows**. The
replay binds those real source artifacts to the test's valid synthetic
`CandidateFrontierRelease` fixture because accepted A08 frontier authority is
still an explicit open prerequisite. This does not claim an A08 release exists.
The replay identities are:

- semantic release `58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`
- Atlas bundle `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
- source bundle `f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`
- frozen census `09445728d79c6d1fa0dd4a1a0b061f2fd3c17ca4a1e8d91f17b456f1fbab7853`
- A08 frontier digest: derived and verified from the current pinned CSV and builder at test execution; the earlier synthetic fixture `1fac163890bd9de235bcba1201ff0967642839f6b6fd5d25690f3022d9eecc12` applies only to the historical test, not this proof
- repaired-schema initial snapshot: recomputed from the real A08 frontier, with canonical digest and consuming replay checked during the test (the preceding snapshot digest belongs to the superseded synthetic bridge)

The
snapshot replay preserves deterministic order and digest, keeps SOURCE_HELD
distinct from IMPLEMENTATION_UNCOVERED, keeps staged/admitted and unverified
learning state independently evidenced, binds the candidate frontier and named
READY/EXPOSED/QUALIFIED state, canonically orders retained evidence using every
identity/value field (including pass/contamination booleans), rejects invalid
schema/digest and unqualified/cyclic source prerequisites, and carries an
explicit qualification epoch.

Validation:

- `BILQIS_ATLAS_REAL_CORPUS=<pinned-a01-corpus> python3 -B scripts/run_tests.py bilqis_mlx/factory/tests/curriculum/test_atlas_frontier.py`
- `BILQIS_QUALITY_BASE_REF=9104ce733e04fb9c82420428b18dfdbf5db49535 npm run quality:changed`
- `python3 -B scripts/verify_bamf_0_2_contracts.py`

The focused A09.1a suite now contains 7 tests: **6 passed, 1 expected real-corpus
skip** when `BILQIS_ATLAS_REAL_CORPUS` is absent. Added regressions prove that
reversing otherwise key-equal retained evidence cannot change snapshot bytes and
that candidate-frontier / named learning-state changes are visible in snapshot
identity.

With the pinned A01 corpus mounted at `bilqis-a05-recut/.local/a05-5-conformance/f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`, the updated real A01/A08 bridge suite passed **7 tests, 0 failed, 0 skipped** on 2026-10-31. The real A08 builder currently emits 240 candidate records and 3,008 source senses. If the corpus is absent, the real test explicitly skips; if mounted but invalid, it fails. This does not imply a CI runner has the pinned corpus.

The full Factory unit surface retains baseline failure parity. Untouched
`9104ce7` runs 387 tests with 355 passed, 19 failed, and 13 skipped. The
refreshed feature worktree runs 392 tests with 359 passed, the same inherited
19 failures, and 14 skipped; no new
existing-test failure is introduced. The inherited architecture failure is
`bilqis_mlx/runtime/model_topology_v2.py:280 GENERIC_GRADE_IDENTITY_DISPATCH A,B`
on both baseline and feature worktrees.

Integration remains governed by A08 #358 and the normal independent review
gate. This receipt does not close #390, admit a Factory release, qualify
learning, mutate a student, or authorize neural training.
