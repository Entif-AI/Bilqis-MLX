# A09.1a immutable CurriculumSnapshot implementation receipt

Issue: #390; parent #389 / A09 #360; Lane A #342.
Feature branch: `codex/a09-1a-390-worker3-20261030`.
Starting sync: `e024b9b405b7097bcefe962283c71a91a392dcd5`, whose parents are
Lane A `66e907bc54beba63ed4a8dea943076d0797f401d` and reviewed unified
`d468b1af1c70a8dc0c0a7aa5ffa6d19b55cb2e18`.
Refreshed on 2026-10-30 by merge commit
`3d771b34354784b5fedeca835a6b2feaa18dbd0b` against current unified
`9104ce733e04fb9c82420428b18dfdbf5db49535`.
Source candidate: `765b9b2749fa0ef60b0fbde244784e76b79d0a23`.
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

The real pinned A01 corpus replay passes with **9,307 source-eligible semantic
IDs, 12,351 required family obligations, and 1,052 source-held rows**. The
replay identities are:

- semantic release `58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`
- Atlas bundle `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
- source bundle `f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`
- frozen census `09445728d79c6d1fa0dd4a1a0b061f2fd3c17ca4a1e8d91f17b456f1fbab7853`
- initial snapshot `4e0671a62c0cb51e72dd4af1330623bb9f7977a94abb22708b53a27df4c5a1d0`

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
