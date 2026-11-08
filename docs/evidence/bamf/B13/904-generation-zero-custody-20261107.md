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

## Dependency refresh and merge-readiness checkpoint — 2026-11-07

The prior WAITING condition is now satisfied. B13.1/#478 passed its final EGM review, PR #885 merged into reviewed unified as `9301e41ef215b9d035449c3260c7cd0f8ee0b5a7`, and #478 is closed with `EGM-Passed`. The current reviewed unified consumed by this refresh is `cc48ac40d875f0c2ae8ffbdc70001dbfc4815334`; ancestry verification confirms that it contains the #885 merge.

The parked #904 branch was reconciled with accepted B13 authority and then merged with the current reviewed unified without rewriting history:

- accepted-authority reconciliation: `29058d3bde6d3913a04e8849950eac8572fc4df4`;
- reviewed-unified merge: `918694f83b9e4773a0ba6affcdcaa6563b8da94b`;
- refreshed semantic/test candidate: `f8a47e4d434d96f4d53ba08ddfb5ae844d7a8e5a`.

The dependency-sensitive proof on the refreshed candidate is green:

- complete B13 custody tree: **123 total / 118 passed / 0 failed / 5 explicit optional/environment skips**;
- opt-in complete clean-process numerical custody witness: **1/1 PASS**;
- generation-acceptance publication witnesses: **10/10 PASS**;
- generation-acceptance authority witnesses: **10/10 PASS**;
- generation-zero authority: **8/8 PASS**;
- publication transaction: **18/18 PASS**;
- publication durability: **8/8 PASS**;
- cold-resume continuation: **8/8 PASS**;
- full-resume non-environment controls: **3/3 PASS**;
- post-split acceptance-contract package: **39 passed / 0 failed / 1 explicit opt-in skip**.

Repository gates are also green against reviewed unified `cc48ac40...`: module-size check has zero violations; error-control reports new debt 0; changed-file smell audit reports zero findings; Factory architecture, BAMF flow-control and governance-integrity checks pass; `git diff --check` is clean.

The only implementation-side adjustment after the unified refresh is a behavior-preserving split of the enlarged acceptance-provenance test module into publication, authority and shared-fixture files so each companion test remains below the repository's structure threshold. No production behavior or acceptance criterion was weakened.

#904 is therefore no longer dependency-held. Its remaining merge-readiness gate is fresh exact-head EGM plus hosted verification/PR turn-in. Human merge and issue closure remain outside this checkpoint's authority.

## EGM round-3 Major remediation — 2026-11-07

The round-3 codebase-details review failed exact candidate
`c609cd3a264444717f8aa59d65c5f0ce0a15c295` with two Majors. This repair
consumed reviewed unified `d4bad39a32a80acbffdb9f891a906892ab2e9fab`
before mutation. The semantic repair candidate is
`4bad7631eca877ee660bca72b0505cc34ad72fe7`.

Major 1 is closed by moving generation-zero model identity back under the
accepted B01 owner. `prepare_initial_generation(...)` no longer accepts
caller-selected topology, extents, or implementation SHA. It derives generation
extents from the already-bound semantic ABI/compiler sidecars plus the internal
motif allocation, independently regenerates B01's canonical `ParameterCensus`,
fingerprints the accepted B01 topology implementation surface, and rejects any
supplied B01 authority mismatch before model allocation. C16 may carry the
already-authorized declaration but cannot become its trust root.

Major 2 is closed at the shared mutation boundary itself.
`_publish_authorized_generation(...)` validates the exact live generation-zero
bootstrap capability for generation 0 and the exact C05
`AcceptedCandidateBinding` for successors before staging or pointer mutation.
Direct import/call therefore cannot bypass either generation-specific authority
gate.

The current reviewed-unified correction/replay surface also required one
integration repair: C09 accepted-support loading now authenticates B13 bootstrap
evidence for generation zero without misclassifying it as C05 retention
acceptance. Generation zero contributes no C05 source anchors; source-qualified
support begins with the first accepted successor as before.

Exact snapshot-pinned M3 Ultra proof:

- literal generation-zero source/B01/shared-sink negatives: **4/4 PASS** at
  `4bad7631eca877ee660bca72b0505cc34ad72fe7`;
- generation-zero authority: **9/9 PASS** at the Major-repair candidate;
- successor acceptance authority, including direct shared-sink bypass:
  **12/12 PASS**;
- reviewed-unified accepted correction/replay integration: **26/26 PASS**;
- complete B13 custody tree: **155 total / 150 passed / 0 failed / 5 explicit
  optional/environment skips**;
- opt-in B01 parameter-schema plus complete clean-process cold-resume witnesses:
  **2/2 PASS**.

The first complete-tree run after the Major repair failed 26 reviewed-unified
accepted-correction tests because those fixtures still attempted generation-zero
publication through the successor-only C05 API. That failure was preserved and
repaired by routing fixture genesis through the production B13 bootstrap and by
teaching accepted-support replay to distinguish bootstrap evidence from C05
source-qualified acceptance. The next focused integration ring passed 26/26 and
the complete custody tree passed 150/150 runnable tests.

Current legacy-trainer adaptation authority, when legacy behavior is materially
consulted, is exclusively:

- branch: `codex/337-replay-349-20261026`;
- worktree: `/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026`;
- canonical run:
  `/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`.

Prometheus remains historical evidence only and is not a current BAMF adaptation
oracle. No actual learner, persistent optimizer, or human-owned training run was
started by this remediation.

## EGM round-4 Blocker remediation — 2026-11-07

Fresh round-4 EGM reviewed exact candidate
`8d7819ad9e2275a793863f6b3d3b89b868aac45d` against reviewed unified
`d4bad39a32a80acbffdb9f891a906892ab2e9fab` and returned **FAIL — 1 Blocker / 0
Majors / 0 Nits**. Both independent review lenses converged on the same authority
gap: a caller could directly mint an `InitialGenerationBinding` for a
self-consistent caller-built generation-zero candidate, and the shared publication
sink treated that binding's value consistency as sufficient live mutation authority.
The same lower-level issuance path also replayed Factory/source authority without
independently rebuilding the candidate's B01 numerical identity.

The failure is preserved in canonical incident `PM-2026-11-07-006`, reusing root
cause `RC-139` and pattern `PAT-100`: caller-synthesized authorization must not gain
issuer authority merely because its values are self-consistent.

Semantic repair head `6df4dcb2710492f1ac53ec86391dbf701b0baa69` closes the gap at the owner and
mutation boundaries rather than hiding the mint helper:

- generation-zero publication now requires the complete live
  `PreparedInitialGeneration`, not an `InitialGenerationBinding` alone;
- the shared publication sink independently replays Factory/source authority,
  canonical B01 topology/extents/implementation authority, the exact seeded
  generation-zero optimizer state, FOUNDATION policy/allocation state, and the
  bootstrap binding before any staging or pointer mutation;
- `_issue_binding(...)` performs the same B01 replay before it may mint bootstrap
  evidence, so a valid Factory record cannot bless caller-authored B01 state;
- a caller cannot relabel a seeded genesis state under another `run_seed`;
- exact B01 error identities are now enum-backed without changing their emitted
  strings, leaving the error-control plane at new debt 0.

Exact detached M3 Ultra proof at `6df4dcb2710492f1ac53ec86391dbf701b0baa69`:

- focused generation-zero source/B01 + generation-zero + successor acceptance
  authority: **28/28 PASS**;
- complete B13 custody tree: **158 total / 153 passed / 0 failed / 5 explicit
  optional/environment skips**;
- opt-in complete B01 parameter-schema plus clean-process full-resume witnesses:
  **2/2 PASS**;
- `quality:changed`: PASS, zero structure/governance/smell findings, canonical
  microspenics legacy-trainer authority green, legacy authority tests **7/7**, BAMF
  flow-control tests **15/15**;
- full `quality:check`: PASS, Factory architecture and docs green, error-control
  **new debt 0**, changed-file smell findings **0**, legacy/flow gates green;
- BAMF contract verifier: **43/43** exact issue mirrors, **215/215** indexed
  owner/child identities and **172/172** recursive child mirrors; retained
  dependency-normalization holds are not integrity failures;
- `git diff --check`: PASS.

No learner, persistent AdamW, teacher, champion, soup, checkpoint lineage, or
durable training run was started or mutated. Round-4 failure remains append-only;
this repair is eligible for a new fresh exact-head EGM, not retroactive acceptance
of the failed candidate.

## EGM round-5 Major remediation and exact-head proof — 2026-11-07

Fresh pinned round-5 EGM reviewed exact candidate
`de50c30d9112169b856bc48660d806383c861104` against reviewed unified
`d4bad39a32a80acbffdb9f891a906892ab2e9fab` and returned **FAIL — 0 Blockers / 1
Major / 0 Nits**. Both review lenses converged on one remaining target-local
authority gap: generation zero still accepted caller-supplied foundation sidecars
(`semantic_abi`, `compiler_features`, `correction_frontier`, `teacher_state`, and
`evaluation_contract`) even though Factory/source/B01 authority was independently
replayed.

Semantic repair head `14b53a81d952e763a8c26dda6e49d65d5b6be63a` closes that gap without
weakening the successor model:

- generation-zero foundation sidecars are derived from verified Factory state
  rather than copied from caller mappings;
- when A06 feature authority is supplied, B13 independently re-enters registered
  A01 source authority and source-pinned A06 feature authority, then reconstructs
  the exact feature schema and factor-map identity before binding compiler state;
- altered caller foundation sidecars cannot be substituted into publication;
- feature-authority tests now cover source-owned reconstruction while keeping
  historical generations without recorded source bindings readable but unable to
  mint accepted feature authority;
- the oversized shared custody fixture helper was split into a bounded publication
  helper instead of exempting the repository's changed-file structure ceiling.

The first broad detached proof on `14b53a81...` failed **151 passed / 3 errors / 5
explicit skips**. Those three errors were stale successor-test fixtures exposed by
the stricter owner-derived genesis identity, not production authority failures:

- the parameter-extension cache fixture carried synthetic pre-repair sidecar and
  extents identity;
- the package-import fixture carried synthetic topology/extents rather than exact
  accepted-parent custody;
- the tensor-CAS generation-2 fixture advanced from retained state still carrying
  generation-0 custody.

Production validation rejected all three fail-closed. No production guard was
relaxed. Test-only correction head `42fc68f01a4cf91f4a27a87035685939a027671f`
aligns successor fixtures with the accepted parent while preserving only each
test's intended transition delta. The formerly failing successor ring then passed
**15/15**.

Fresh exact-head detached M3 Ultra proof at `42fc68f01a4cf91f4a27a87035685939a027671f`:

- complete B13 custody tree: **159 total / 154 passed / 0 failed / 5 explicit
  optional/environment skips**;
- opt-in complete B01 parameter-schema plus clean-process full-resume witnesses:
  **2/2 PASS**;
- detached receipt status: **PASS**, command return code `0`;
- source/snapshot digest remained
  `8a126a9bd93205beaf7618edf1770ccd16fe2efcdc7996f8c7dc2e7aca044e82`
  before and after the run, with `source_mutated=false`;
- focused post-fixture successor ring: **15/15 PASS**;
- changed-scope structure/governance/smell checks: PASS, zero findings;
- legacy-trainer authority tests: **7/7 PASS**;
- BAMF flow-control tests: **15/15 PASS**;
- `git diff --check`: PASS.

No learner, persistent AdamW, teacher, champion, soup, checkpoint lineage, or
durable training run was started or mutated. Round-5 failure remains append-only;
this exact candidate is eligible for a genuinely fresh pinned EGM round and is not
retroactively accepted by the passing proof.
