# B13.6 / #904 generation-zero run custody checkpoint — 2026-11-07

## Scope

B13.6 assigns and implements the previously unowned production generation-zero boundary required by B13 and C16. The change removes test-only C05 retention acceptance from BAMF genesis, persists immutable run birth identity including the operator-selected `run_seed`, and keeps successor publication under the existing C05 `AcceptedCandidateBinding` authority.

This is conformance to existing B13/C16 requirements. It does not add a new learner, optimizer, visit selector, C07 lease, CLI trust root, or B06 policy.

## Exact identity

- reviewed unified base: `bd3657e170c8bdc046a7bb28524c0fb829ca7ce9`
- branch: `codex/904-b13-6-generation-zero-20261107`
- governance checkpoint: `9901f118e177f933c40bff995c833c7f2bc754f4`
- final implementation head: `1bba69e385f2666a5a185aa9114a3f64cd3f7685`

Canonical dependency order was additively repaired without rewriting original issue contracts:

`B13.6 #904 -> C16.1b #543 -> C16.1a #542`

## Production ownership

`BamfRunIdentity` is the immutable B13 run birth record. It binds:

- run ID and operator-selected integer `run_seed`,
- concrete origin checkpoint digest/path/optimizer step,
- admitted Factory release and semantic graph identities,
- initial candidate/topology/extents/implementation identity,
- initial source/release and teacher identity/epoch.

`InitialGenerationBinding` is a live issuer-controlled B13 capability for generation zero only. Persisted records deserialize as historical evidence and cannot regain live publication authority.

`prepare_initial_generation(...)` validates the real admitted Factory source boundary, initializes the B01-shaped BAMF state with zero AdamW moments/counts and FOUNDATION policy, constructs generation zero, and issues the live bootstrap capability. `publish_initial_generation(...)` reuses the existing B13 crash-safe bundle/pointer transaction. Public `publish_bamf_generation(...)` now rejects generation zero and remains successor-only under C05 retention acceptance.

Run identity is an optional sidecar for backward compatibility. New successors must inherit it unchanged; historical bundles without it remain readable.

## Proof

Exact-head, snapshot-pinned detached M3 Ultra proof:

- `e0377639f2e6a70f7c4c7305d63b31e6eefb9256`: affected custody/publication/feature/cold-resume ring **44/44 PASS** in 10.263s.
- `1bba69e385f2666a5a185aa9114a3f64cd3f7685`: final focused generation-zero authority **7/7 PASS** in 0.832s.

The final focused proof establishes:

- exact operator `run_seed` persists through accepted generation-zero load;
- initial optimizer step, moments, variances and update counts are zero; mode is FOUNDATION;
- generation zero refuses C05 candidate acceptance;
- persisted bootstrap evidence cannot be reused as live authority;
- a bootstrap token cannot authorize a successor;
- exact retry converges while a conflicting seed cannot replace genesis;
- admitted-source/checkpoint drift rejects before any run write;
- corrupted run-identity custody rejects cold read.

Repository/static gates on the implementation branch:

- `quality:changed`: PASS, zero new changed-file smell findings;
- legacy trainer authority tests: 6/6 PASS;
- flow-control tests: 15/15 PASS;
- BAMF contract verifier: 43/43 exact owner mirrors, 215 owner/child identities/fingerprints;
- module-size checks: zero violations;
- `git diff --check`: clean.

The workstack validator reports `status=held` and exits non-zero because dependency normalization intentionally holds B13.6/C16.1a/C16.1b; there is no cycle or registry-integrity defect.

## Failure history preserved

Three earlier affected rings exposed only fixture migration debt after replacing synthetic genesis with the production boundary:

- 36/44: old successor acceptance referenced synthetic parent state and old optimizer-step expectations;
- 39/44: old successor fixtures carried a stale motif allocation digest and the competing-genesis fixture reused the same default seed;
- 40/44: retained-state motif custody still referenced the synthetic parent.

Each was repaired in tests/fixtures without weakening production validation. The final affected ring is 44/44.

## Remaining authority boundary

#904 is **not merge-ready** because its direct B13.1 dependency is still authority-held. The required publication interface exists on reviewed unified, which was sufficient for implementation/proof, but final turn-in must consume an accepted B13.1 dependency receipt. Therefore no fresh EGM and no parking PR are justified now.

After reviewed integration, C16.1b #543 must bind the actual admitted Factory foundation/topology/teacher/optimizer to this B13 boundary; C03 remains the owner of the true teacher-visit identity. No `run_id`, `episode_id`, or `optimizer_step_seed` may substitute for the persisted `run_seed` or future visit identity.
