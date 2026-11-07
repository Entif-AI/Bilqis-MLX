# B13.5 accepted-generation feature authority receipt

Issue: #708 (remediation of #697 / B13.5)
Lane: B
Branch: `codex/remediation-egm-708-711-integration-20261103`
Consumed unified head: `e9226be2f6a41f47109ca02a1103a363e64909a7`
Final candidate head: `537f4c62`

## The defect

An ordinary caller-created `BamfBundleCandidate` could choose a factor-map
digest, keep its extents and compiler fields self-consistent, publish it, and
then have the accepted-generation feature receipt mint and verify that
caller-selected digest. Serialization of caller assertions had become
authority.

## What this receipt proves

### The feature identity is source-replayed

`bilqis_mlx/runtime/_custody/bamf_bundle/feature_authority.py` opens the
published generation under the custody pointer lock, reloads the admitted
source identity and feature schema recorded with the generation, rebuilds the
feature manifest through the A06 feature owner, and refuses to mint a receipt
unless the replayed feature digest equals the accepted generation's recorded
factor map. The receipt also binds the source release identity that the replay
authenticated.

### The generation is retention-accepted, not merely published

Publication is not acceptance. `resolve_candidate(... accepted=True)` states in
its own contract that the selection is neither a retention decision nor an
accepted-generation publication grant, so the accepted-generation authority
cannot rest on the pointer alone.

`bilqis_mlx/learning/_retention/atlas_retention_decision.py` is the retention
decision owner. It evaluates the measured retention evidence with the
repository's own precedence and issues an unforgeable accepted or rejected
decision. `bilqis_mlx/learning/_retention/atlas_acceptance.py` is the
retention-owner seam that mints the `AcceptedCandidateBinding` from such a
decision; the binding covers the exact accepted optimizer identity, the
accepted feature identity, the optimizer step, the retention reason the
decision owner derived, the decision digest, and the digests of the owner-bound
step proofs the accepted state carries. Neither the binding nor the decision
can be constructed outside their owner modules, and publication consumes an
already-issued decision instead of deciding acceptance itself.

`publish_bamf_generation(run, candidate, acceptance=...)` now refuses to
publish without a matching binding, refuses a binding minted for another
candidate state, and persists the binding in the run custody before the pointer
names the generation. The accepted-generation feature receipt reads that
binding back and re-verifies it against the accepted bundle before it mints.

### The adversaries

- A caller-created candidate with an arbitrary digest cannot self-ratify.
- A candidate published without a retention acceptance binding is refused.
- A binding minted for another candidate state is refused.
- A binding that names another feature identity is refused.
- A caller cannot construct an acceptance binding directly.
- A published generation whose acceptance custody is missing cannot mint an
  accepted-generation receipt.
- A forged receipt is rejected by live verification, and receipt tampering is
  detected on readback.

## Verification

- `python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle`
  → 56 passed, 0 failed, 11 skipped.
- `python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody bilqis_mlx/learning`
  → 637 passed, 1 failed, 44 skipped, 12 pre-existing loader errors. The single
  failure was the relocated-owner census, which this change refreshes from 32
  to the current 37 owners. The census was already stale at the consumed
  unified head, which carried 36 owners.
- `python3 -B scripts/check_module_size.py --changed-from origin/codex/bamf-unified-base-20261028`
  → DEVELOPMENT_STRUCTURE_CHECK OK.
- `python3 -B scripts/quality/check_governance_integrity.py --base-ref origin/codex/bamf-unified-base-20261028`
  → GOVERNANCE_INTEGRITY_CHECK OK.

## Open limits

- Only a generation whose feature map is the root map of an admitted source
  release can be authenticated today. Successor-generation chains stay
  fail-closed until a successor source release is registered and the chain
  replay is implemented.
- The source replay needs the externally supplied A01 artifact, exactly like
  the other source-replay proofs in this repository. The tests stand in for
  that artifact at the replay seam and do not claim a fresh external artifact
  replay.
- The retention binding proves that the retention owner accepted the exact
  optimizer state and feature identity of the published generation. It does
  not yet replay the retention gates themselves, which stay with the trainer
  and the retention policy owners.
- Issue #697 stays open. This removes the self-ratification defect but does
  not close the parent B13.5 acceptance.

## Authority

No student, optimizer, checkpoint lineage or live run was changed. No
self-merge. Fresh pinned EGM is reserved for the merge-ready head.

## Parent #697 completion reconciliation — 2026-11-07

Reviewed-unified base: `cc48ac40d875f0c2ae8ffbdc70001dbfc4815334`.
The #708 remediation above is now integrated, B13.1/#478 is closed, and B13.2
is integrated through #479/PR #909. The remaining parent-owned gap was the
successor feature-map lineage called out in the historical open limits above.

`feature_authority.py` now reconstructs a changed accepted generation's
feature map recursively from immutable B13 parent bundles and each generation's
retention-acceptance evidence. The current generation's source feature compiler
receives the rederived accepted predecessor map; no caller supplies that map.
Unchanged feature generations reuse the already authenticated map instead of
inventing a new predecessor edge. `read_accepted_generation_feature_lineage()`
returns the receipt plus the authenticated current and predecessor feature maps
for the downstream owner while `read_accepted_generation_feature_receipt()`
remains the narrow receipt API.

Focused parent proof on this base:

- B13.5 feature authority: **10/10 PASS**, including a real accepted generation-1
  source replay whose receipt binds the exact generation manifest and predecessor
  feature digest, a retained generation whose immediate parent uses the same
  feature map, and fresh-process cold-read receipt identity; forged generation,
  manifest, feature and predecessor identities fail live verification.
- generation acceptance/provenance: **20/20 PASS**, including rejected or
  unpublished authority, foreign candidate/feature identity, missing acceptance
  custody and re-signed acceptance drift.
- development structure: **PASS, 0 violations**; `git diff --check`: **PASS**.

The A02 consumer remains owned by #399. Its preserved production branch
`codex/bamf02-a-399-production-admission-20261106` at
`ba1c366e8f583d1c0bb2676a7740c749707e7fa1` consumes this B13 lineage before
calling the authenticated A02 planner. On that exact branch the full-topology
`test_stages_bank_extension_without_granting_admission` witness passed **1/1**
in **186.699s**: two accepted B13 generations were reconstructed, the genuine
predecessor-bearing source plan staged the next semantic bank, and generic
publication remained denied. The ordinary A02 planning suite passed **5/5**
with one optional real-corpus witness skipped, preserving the default
`BAMF_VOCABULARY_PREDECESSOR_FEATURE_AUTHORITY_REQUIRED` fail-closed path for
caller-minted predecessors.

This resolves the historical successor-chain limit without transferring A02 or
C07 authority into B13. No durable student start, optimizer update, admission,
or source promotion was performed by this reconciliation. Parent #697 still
requires its own fresh exact-head EGM before merge readiness; #708's prior EGM
PASS is not inherited.

### Merge-readiness proof before EGM

Semantic implementation commit: `584159e000a857bf7284d5ab5a3677a28702b316`.
Review episode: `697-b13-5-20261107`, round 1.

- differential leaf selection: **36 passed + 7 subtests**, 0 failures;
- flow-control tests: **15/15 PASS**;
- governance, Factory architecture, documentation, changed-file smell and
  error-control gates: **PASS**, with error-control new debt 0 and changed-file
  smell findings 0;
- `git diff --check`: **PASS**;
- full differential premerge selection: **3,470 total / 3,261 passed / 18
  errors / 191 skipped**. The 18 errors are unavailable legacy-fixture setup,
  not #697 behavior failures. Representative failures reproduce unchanged on
  pristine reviewed unified `cc48ac40`: missing
  `vendor/legacy-v16/.../student-116760-7e9af4651f28.pt` in the Grade-C source
  and generated-test setup paths, and missing `vendor/legacy-v16/runs` in the
  Grade-C trainer setup path. The targeted #697/B13.5 and A02 authority tests in
  the same premerge selection are green.
- the repository static legacy-trainer check also fails unchanged on pristine
  reviewed unified because `docs/evidence/bamf/906/receipt.md` omits the
  canonical run identity. #697 does not modify that unrelated #906 evidence;
  the legacy-trainer checker unit suite itself passes **6/6**.

No failing premerge observation is localized to the #697 diff. The exact
candidate is therefore eligible for its required fresh pinned whole-candidate
EGM; no PR is opened before that review.

### EGM round 1 and target-local repair

Round 1 reviewed exact candidate
`72a3e5891098adf0da2ea5b124483a394c0736f5` and returned **FAIL**. The
fresh comprehension Goldfish found one `TARGET_LOCAL` Blocker: an accepted
successor that retained the same feature map/compiler/release as its parent
reused the authenticated map object, but the receipt still treated that map's
own historical `predecessor_digest` as the generation-level predecessor. A
generation-1 child over a root feature map therefore failed with
`BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED`; later unchanged children could bind
the parent's predecessor rather than the immediate parent feature identity.
The requested codebase-details reviewer failed to start because the worker
substrate could not confirm its saved model/reasoning configuration, so round 1
could not have been a clean complete round independently of the Blocker.

The failing-before regression
`test_retained_successor_binds_the_feature_map_its_parent_consumed` produced
**9 PASS / 1 ERROR** on the round-1 implementation. Repair commit
`b85a96a86910ba7083fbef315ec31fe4c2cfc4a6` now keeps feature-map construction
ancestry separate from generation ancestry: unchanged successors retain the
already-authenticated current map but bind the immediate accepted parent's
feature digest in the generation receipt. Changed maps still require source
replay with that accepted parent map supplied as the compiler predecessor.

Passing-after evidence on the repaired semantic head:

- B13.5 feature authority: **10/10 PASS**;
- generation acceptance/provenance: **20/20 PASS**;
- the cold-resume receipt witness now launches a fresh Python interpreter and
  reproduces the exact receipt digest from persisted B13 custody;
- development structure: **PASS, 0 violations**; `git diff --check`: **PASS**.

The repaired candidate must clear current differential/premerge gates before
round 2 is requested. Round 1 remains a durable failed review; its PASS state is
not reused.

### Round-2 qualification boundary

Current reviewed unified remained exactly
`cc48ac40d875f0c2ae8ffbdc70001dbfc4815334` after a fresh fetch. The canonical
ignored legacy-v16 fixture relationship used by accepted B13.2 premerge proof
was bound locally as `vendor/legacy-v16/runs` ->
`/Users/emilie/Code/bilqis-mlx-retention-lab/vendor/legacy-v16/runs`; no fixture
bytes or symlink are committed.

Post-repair deterministic proof:

- feature authority: **10/10 PASS**;
- generation acceptance/provenance: **20/20 PASS**;
- differential leaf: **14 passed + 3 selected subtests**, 0 failures;
- flow control: **15/15 PASS**;
- governance, Factory architecture, docs, error-control, changed-file smell and
  `git diff --check`: **PASS**, with error-control new debt 0 and changed-file
  smell findings 0;
- full differential premerge: **3,545 total / 3,384 passed / 0 failed / 161
  explicit skips / 0 errors** in **392.741s**.

The clean aggregate supersedes the earlier environment-limited premerge receipt.
No production or test criterion was weakened to obtain it. Round 2 may therefore
review the repaired semantic head `b85a96a86910ba7083fbef315ec31fe4c2cfc4a6`
plus nonsemantic evidence/flow bookkeeping only.

### Round-2 pre-review authority audit: historical acceptance anchor

Before any round-2 Goldfish worker was created, a prime-side authority audit of
candidate `3218636f8c9f9d6ab9c3dfa110a31ca457eed941` found a second
`TARGET_LOCAL` B13.5 defect. The live pointer cryptographically named only the
current generation's `acceptance_sha256`. Historical ancestors were reopened by
manifest-named JSON sidecars whose self-digest and retained-state fields were
validated, but no immutable artifact committed the exact historical acceptance
digest after the pointer advanced.

Failing-before regression
`test_successor_rejects_resigned_historical_parent_acceptance` published an
accepted generation 0 and generation 1, changed the historical generation-0
acceptance `policy_sha256`, recomputed its `binding_sha256` self-consistently,
and left the immutable parent/child bundle DAG untouched. The exact candidate
still accepted the lineage: the feature-authority selection produced **10 PASS /
1 FAIL** because the expected `BilqisError` was not raised. The issue therefore
returned from `EGM-Pending` to `EGM-Failed` before any round-2 reviewer consumed
budget; round 2 remains the next whole-candidate review in episode
`697-b13-5-20261107`.

Semantic repair `a211836f59a2a7c4949d585f2e30060473a53a38` adds an
acceptance-bound published-bundle schema without rewriting generic historical
custody:

- ordinary/unbound bundle writes retain readable v2 semantics;
- accepted publication emits v3 and commits `parent_acceptance_sha256` inside
  the child manifest's content-addressed identity;
- the current generation remains rooted at the pointer's exact
  `acceptance_sha256`;
- recursive feature-lineage replay obtains each historical parent's exact
  acceptance digest from its immutable child manifest and requires the sidecar's
  binding digest to equal that anchor;
- a v2 historical bundle remains readable custody evidence but cannot be
  silently promoted into acceptance-bound recursive authority where no immutable
  historical acceptance anchor ever existed.

Passing-after proof on the semantic repair:

- feature receipt + lineage authority: **11/11 PASS**;
- all B13 bundle contracts: **42 PASS / 1 explicit opt-in skip / 0 failures**,
  including pinned pre-CAS writer compatibility;
- complete B13 custody package: **113 PASS / 5 explicit fixture or opt-in skips /
  0 failures**;
- package-import plus production-authority selection: **20/20 PASS**;
- module-size/development structure, governance integrity, Factory architecture,
  docs, error-control, changed-file smell, flow-control and `git diff --check`:
  **PASS**; error-control new debt 0, changed-file smell findings 0, flow-control
  unit suite **15/15 PASS**;
- disposable composition with preserved A02/#399 production work produced the
  real full-topology vocabulary staging witness **1/1 PASS in 190.290s** and the
  A02 planner **5/5 PASS + 1 optional real-source skip**. Generic/caller-minted
  predecessor authority remains fail-closed.

The differential leaf's parallel pytest selection reported 16 failures caused by
Python 3.14 `xdist`/`execnet` attempting to serialize `unittest.subTest()` lambda
values (`DumpError: can't serialize <class 'function'>`). A representative exact
test reproduces the same failure on pristine reviewed-unified
`cc48ac40d875f0c2ae8ffbdc70001dbfc4815334` under `-n 4` and passes serially
with its subtests. This is inherited runner behavior, not a candidate regression;
no unrelated test was changed from #697 to mask it.

Because the authority semantics changed, the earlier 3,545-test aggregate is not
reused as final round-2 qualification. A fresh isolated premerge aggregate is
required before the issue may return to `EGM-Pending` and fresh round-2 review.
