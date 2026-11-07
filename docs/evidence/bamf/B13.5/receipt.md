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
- the repository static legacy-trainer check, whose current adaptation oracle is
  `/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`,
  also fails unchanged on pristine
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

### Reviewed-unified synchronization before the replacement aggregate

Before the replacement aggregate launched, reviewed unified advanced from
`cc48ac40d875f0c2ae8ffbdc70001dbfc4815334` to
`d4bad39a32a80acbffdb9f891a906892ab2e9fab`. The synchronized candidate merge
`b9438fa2d532bdf83663bc860f3d5230e4af9734` combines the pushed #697 repair and
evidence head `be379153753e58218b0ebe389da0824369e63bd7` with that exact reviewed
unified head. The merge is integration-only; the #697 semantic repair remains
`a211836f59a2a7c4949d585f2e30060473a53a38`.

Post-synchronization requalification against `d4bad39a`:

- feature receipt + lineage authority: **11/11 PASS**;
- generation acceptance/provenance: **20/20 PASS**;
- publication: **18/18 PASS**;
- expanded B13 custody package after the C09 integration: **138 PASS / 5 explicit
  skips / 0 failures**;
- governance integrity, Factory architecture, docs, error-control, changed-file
  smell, development structure, flow-control units and `git diff --check` remain
  **PASS**; error-control new debt 0 and changed-file smell findings 0.

The current legacy-trainer authority contract names
`/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`
as the adaptation oracle. B13.5's historical note about the earlier inherited #906
static failure is retained as chronology, while the current evidence names that
canonical run explicitly so the present static guard can validate this receipt.

### Replacement aggregate on reviewed unified `d4bad39a`

The required ADR-132/ADR-136 snapshot-isolated replacement premerge ran from exact
candidate `4d6f60901d12dcb9016776b3f4b43e9c4bda17da` with immutable source/snapshot
digest `207a2d236aded990ef23175de313c2a45be90aa15ac12cd3afca0d665bf24ef9`.
The detached runner completed without source mutation and reported:

- **3,620 total**;
- **3,448 passed**;
- **167 explicit skips**;
- **5 errors**;
- **450.733s**.

All five errors are the same C09 packed-frame ownership failure,
`BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT`, from the nested-frame fixture path in:

- `bilqis_mlx/learning/tests/frames/test_compiled.py`;
- `bilqis_mlx/learning/tests/frames/test_execution.py`;
- `bilqis_mlx/learning/tests/frames/test_members.py`.

The exact three-file selection was then run on a pristine detached worktree at the
reviewed-unified head `d4bad39a32a80acbffdb9f891a906892ab2e9fab`. It reproduced
the same **5 errors / 1 pass** with the same `BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT`
reason. Therefore the aggregate is not globally green, but its complete failing set
is inherited from the newly integrated C09 base and is not localized to the #697
diff. #697 does not modify the failing nested-frame fixtures or the C09 packed-frame
owner merely to make an unrelated base regression disappear.

The #697 authority queue itself remains clear: the post-sync B13.5 feature lineage,
acceptance, publication and full custody selections are green, repository quality
gates are green, and the preserved A02/#399 production consumer witness is green.
This base-vs-candidate classification is the deterministic qualification used to
enter fresh whole-candidate EGM round 2; it is not represented as a clean global
premerge pass.

### Exact-final candidate leaf and A02/#399 consumer witness

After the inherited C09 classification, the exact current #697 head was rechecked
with the forced serial differential leaf against reviewed unified. The leaf gate
completed with exit 0 on candidate `4d6f60901d12dcb9016776b3f4b43e9c4bda17da`.

The downstream A02/#399 consumption witness was also repeated against the exact
final B13 semantics in a disposable composition: current #697 candidate plus the
preserved #399 branch `ba1c366e8f583d1c0bb2676a7740c749707e7fa1`. The disposable
join retained current B13 authority files where the preserved A02 branch carried
older copies, while keeping A02's staging implementation and public export. No A02
branch was modified.

- full-topology production staging: **1/1 PASS in 190.636s**;
- ordinary A02 vocabulary planner: **5/5 PASS + 1 optional real-source skip**;
- caller-minted predecessor authority remains fail-closed.

Together with the focused B13 suites and inherited-base proof above, this closes the
deterministic engineering queue for fresh whole-candidate EGM round 2. The semantic
implementation remains `a211836f59a2a7c4949d585f2e30060473a53a38`; later receipt
bookkeeping is nonsemantic.

### Round-2 findings after concurrent exact-head reviews

Two independently launched fresh round-2 packets were recorded during concurrent
closeout orchestration. Their history is preserved rather than silently renumbered.
Both failed, so the next fresh whole-candidate review is round 3.

The first packet reviewed `d873cea0e448f8adddf1b74102529bb8872ca584` and found a
target-local unchanged-map defect: a valid accepted successor could retain the exact
same factor-map identity while advancing independent compiler/correction metadata,
yet B13.5 classified it as a changed feature map because it compared the whole
compiler sidecar. Failing-before
`test_retained_successor_allows_independent_correction_epoch_advance` reproduced the
defect. Semantic repair `9fb2b1308b22caab399289bed7a6250b11ebf880` now classifies
retained maps by the accepted factor-map identity, source-replays the child's own
recorded source/schema without inventing a feature-construction predecessor, verifies
the replayed digest equals the accepted parent map, and still binds the immediate
accepted parent as generation ancestry.

A second fresh round-2 packet reviewed `7046f0c7d160e3e6f81323f967c92fa796c90731`.
Its comprehension reviewer passed with no Blocker/Major, but codebase-details found
two target-local Majors. The same-map metadata Major overlapped the repair above. The
remaining Major exposed the pinned/pre-CAS writer compatibility fallback: after B13
had derived the exact live parent acceptance for a fresh generation > 0, a writer
that rejected the new `parent_acceptance_sha256` argument could be retried without
that argument, producing an accepted unbound v2 child that could never satisfy B13.5
historical lineage.

Failing-before
`test_pinned_old_writer_cannot_publish_fresh_accepted_successor` produced **2 PASS /
1 FAIL** because the expected `BilqisError` was not raised. Semantic repair
`142f6e01b54959c14ff40328c9e6b0b0c82b038f` preserves pinned old-writer genesis
compatibility and same-generation unbound replay, but fails closed for a fresh
generation > 0 when the writer cannot persist the immutable parent-acceptance anchor.
The round-2 `CompleteStudent` v2-only docstring Nit was also corrected.

Passing-after qualification on semantic head `142f6e01` against reviewed unified
`d4bad39a32a80acbffdb9f891a906892ab2e9fab`:

- pinned/pre-CAS compatibility: **3/3 PASS**;
- feature authority + lineage: **12/12 PASS**;
- generation acceptance/provenance: **20/20 PASS**;
- publication: **18/18 PASS**;
- complete B13 custody package: **140 PASS / 5 explicit skips / 0 failures**;
- governance integrity, Factory architecture, docs, error-control, changed-file
  smell, development structure, flow-control, static legacy-trainer guard and
  `git diff --check`: **PASS**; error-control new debt 0, changed-file smell findings
  0, flow-control unit suite **15/15 PASS**;
- forced-serial differential leaf: **100 passed + 68 subtests**, 137 deselected,
  exit 0 in 150.38s;
- exact-head disposable A02/#399 composition: full-topology production staging
  **1/1 PASS in 197.133s**; ordinary vocabulary planner **5/5 PASS + 1 optional
  real-source skip**; caller-minted predecessor authority remains fail-closed.

Because `142f6e01` changes publication behavior, the earlier aggregate cannot be
reused as final qualification. One fresh ADR-132/ADR-136 snapshot-isolated premerge
aggregate is required before #697 may return to `EGM-Pending` for round 3.

### Final deterministic qualification for round 3

The final behavior-changing semantic head remains
`142f6e01b54959c14ff40328c9e6b0b0c82b038f`; bookkeeping commit
`b701dac1c3934691d869fc505e85c5965d6e1c75` records the round-2 findings without
changing production semantics. Reviewed unified remains
`d4bad39a32a80acbffdb9f891a906892ab2e9fab`.

The required fresh forced-serial differential premerge completed on this final
semantic state and reported:

- **3,622 total**;
- **3,450 passed**;
- **167 explicit skips**;
- **5 errors**;
- **450.688s**.

The complete failing set is again exactly the five inherited nested-frame C09
`BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT` cases already reproduced on pristine
reviewed-unified `d4bad39a`; no new #697-local failure appeared. The aggregate is
therefore inherited-red rather than globally green, with exact base-vs-candidate
evidence preserved above.

The final-head forced-serial differential leaf also completed with exit 0:
**138 passed + 68 subtests**, 869 deselected, in **213.04s**. Its receipt binds
semantic head `142f6e01b54959c14ff40328c9e6b0b0c82b038f`.

The downstream A02/#399 consumer seam was repeated once more after both round-2
repairs, using a disposable composition with preserved #399 head
`ba1c366e8f583d1c0bb2676a7740c749707e7fa1` and without modifying the A02 branch:

- full-topology production staging: **1/1 PASS in 198.707s**;
- ordinary vocabulary planner: **5/5 PASS + 1 optional real-source skip**;
- coherent caller-minted predecessor authority remains fail-closed.

Together with the round-2 repair regressions, focused B13 custody and quality gates,
this closes the deterministic engineering queue for fresh whole-candidate EGM round
3. No EGM PASS is claimed by this qualification receipt.

### Round-3 finding and repair

Fresh round 3 reviewed exact candidate
`c54c5da7722d2091ceff3e6de1aae87f22fd72d9`. The comprehension / implementation-
readiness reviewer returned **PASS** with no target-local Blocker, Major or Nit. The
independent code-vs-contract authority reviewer returned **FAIL** with one
target-local Major.

The Major exposed a publication/replay capability mismatch. Fresh successor
publication could read a historical v1/v2 parent acceptance through the broad
custody reader and embed that legacy digest as immutable `parent_acceptance_sha256`
in a new v3 child. Recursive B13.5 lineage correctly refuses legacy acceptance
schemas as historical minting authority, so that freshly published child could not
later reconstruct accepted feature ancestry.

Failing-before `test_legacy_parent_acceptance_cannot_authorize_fresh_successor`
reproduced the seam: generation-acceptance tests reported **20 PASS / 1 FAIL**
because the expected `BilqisError` was not raised. Semantic repair
`7b5798b69ac6019219e0a697a6aeb9f30b5d0f6d` keeps historical v1/v2 records
readable, but requires the live parent acceptance to use current `ACCEPTANCE_SCHEMA`
before its digest may authorize and become the immutable parent anchor of a fresh
successor.

Passing-after:

- generation acceptance/provenance including the new legacy-parent adversary:
  **21/21 PASS**;
- focused feature authority + lineage + generation acceptance + pre-CAS
  compatibility + publication: **54/54 PASS**;
- the enlarged acceptance test module was split into
  `test_generation_acceptance.py` and `test_generation_acceptance_history.py` rather
  than bypassing the repository structural limit; combined acceptance tests remain
  **21/21 PASS** and development-structure reports **0 violations**;
- governance integrity, Factory architecture, docs, error-control, changed-file
  smell, flow-control and `git diff --check` remain green; error-control new debt 0,
  changed-file smell findings 0 and flow-control units **15/15 PASS**.

Semantic authority after this repair is `7b5798b6`; structural test split
`66cf30332173c69ad0909a4d3ad55a8186caa6fd` is nonsemantic.

### Final deterministic qualification for round 4

Reviewed unified remains `d4bad39a32a80acbffdb9f891a906892ab2e9fab` and the exact
candidate is `66cf30332173c69ad0909a4d3ad55a8186caa6fd` before final evidence
bookkeeping.

The final-head forced-serial differential leaf completed with exit 0:
**123 passed + 28 subtests**, 885 deselected, in **208.53s**. Receipt head is exact
candidate `66cf3033`.

The A02/#399 consumer seam was repeated against this exact state using preserved
head `ba1c366e8f583d1c0bb2676a7740c749707e7fa1` without mutating the A02 branch:

- full-topology production staging: **1/1 PASS in 188.110s**;
- ordinary vocabulary planner: **5/5 PASS + 1 optional real-source skip**;
- coherent caller-minted predecessor authority remains fail-closed.

The required fresh ADR-132/ADR-136 snapshot-isolated forced-serial premerge then
completed with source mutation guard intact (`source_mutated=false`) and reported:

- **3,623 total**;
- **3,451 passed**;
- **167 explicit skips**;
- **5 errors**;
- **447.451s**.

The complete failing set is exactly the same five inherited nested-frame C09
`BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT` cases already reproduced on pristine
reviewed-unified `d4bad39a`. No new #697-local failure appeared. This closes the
deterministic engineering queue for fresh whole-candidate EGM round 4. No EGM PASS
is claimed by this qualification receipt.

### EGM round 4 and final-cap repair set

Fresh whole-candidate round 4 reviewed exact candidate
`6e3bab9c68f7d63ff5c222e31318b0c4a2ccfbeb` and returned **FAIL** with one
`TARGET_LOCAL` Blocker and two `TARGET_LOCAL` Majors.

The Blocker exposed a three-generation retained-map lineage defect. A valid
`F0 -> F1(changed, predecessor=F0) -> F1(retained)` chain replayed the retained
grandchild as though F1 were root-constructed, dropping F0 from the feature
construction identity. Repair `fd739a12d7b65174225a7483b0b835e52314559c`
preserves the already-authenticated parent feature object when the child retains
the same factor-map digest, verifies the child's recorded source/schema/release
against that immutable map, and still binds the immediate accepted parent as
generation ancestry. The new cold-lineage regression failed before with
`BAMF_FEATURE_SOURCE_REPLAY_MISMATCH` and passes after.

The first Major showed that a live generation > 0 historical bundle/v2 parent
could carry a current acceptance sidecar and still authorize a fresh v3 child,
despite lacking the immutable `parent_acceptance_sha256` needed to authenticate
its own ancestry after the pointer advanced. Repair
`377c98c7a138c6fe610209b05b2829fdd4a051db` fails closed for that
non-genesis parent publication capability while preserving bundle/v2 genesis as
the bootstrap compatibility boundary.

The second Major showed that accepted feature-lineage replay recursively loaded
one generation per Python call even though B12/B13 impose no history-length cap.
Failing-before
`test_long_accepted_history_has_no_python_recursion_ceiling` used 1,100 accepted
history nodes and reproduced `RecursionError`. Repair
`68d3f287122b5ff8e70337e15655e225d073fa3a` walks and validates accepted
custody backward iteratively, then replays feature construction forward. It does
not invent a generation cap or weaken historical acceptance verification.

### Final deterministic qualification for round 5

The final behavior-changing semantic head is
`68d3f287122b5ff8e70337e15655e225d073fa3a`. Reviewed unified remains
`d4bad39a32a80acbffdb9f891a906892ab2e9fab`.

Exact-head qualification after all round-4 repairs:

- complete B13 bundle proof: **144 PASS / 5 explicit skips / 0 failures**;
- long-history regression: **1/1 PASS** after the recorded failing-before
  `RecursionError`;
- forced-serial differential leaf: **13 PASS + 3 subtests**, exit 0;
- governance integrity, development structure, current Microspenics legacy-trainer
  authority and `git diff --check`: **PASS**;
- disposable A02/#399 full-topology production staging: **1/1 PASS in 192.200s**;
- ordinary A02 planner: **5/5 PASS + 1 optional real-source skip**, with
  `BAMF_VOCABULARY_PREDECESSOR_FEATURE_AUTHORITY_REQUIRED` still fail-closed for
  caller-minted predecessor authority.

The final fresh ADR-132 snapshot-isolated premerge completed with its mutation
guard intact (`source_mutated=false`) and reported:

- **3,626 total**;
- **3,454 passed**;
- **167 explicit skips**;
- **5 errors**;
- **430.642s**.

Those five errors are exactly the same inherited C09
`BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT` cases already reproduced on pristine
`d4bad39a`: one in `test_compiled.py`, two in `test_execution.py`, and two
in `test_members.py`. No additional #697-local failure appeared.

The complete known engineering queue is therefore repaired and deterministically
qualified for fresh whole-candidate EGM round 5, the ADR-127 default episode cap.
No round-5 EGM PASS is claimed by this receipt.

### EGM round 5 — capped disposition

Fresh whole-candidate round 5 reviewed exact pushed candidate
`a459654341433e4a9397b17db6821096db876a03`, with semantic implementation
`68d3f287122b5ff8e70337e15655e225d073fa3a`, reviewed unified
`d4bad39a32a80acbffdb9f891a906892ab2e9fab`, and pinned EGM
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`.

The valid clean reviewer pair completed. Round 5 returned **FAIL**. One earlier
authority worker self-disqualified after opening historical review narrative, and
one replacement comprehension worker failed to start; neither contributes a
disposition. The final independent pair is the clean codebase-details reviewer
and the clean comprehension/implementation-readiness reviewer.

The codebase-details reviewer found one `TARGET_LOCAL` Blocker:

- **multi-release Atlas artifact resolution is missing from accepted feature-lineage
  replay.** `_accepted_feature_chain()` receives one `artifact_path` and reuses
  it while reconstructing genesis and every changed descendant. Each generation,
  however, may bind a different immutable Atlas bundle/release/source identity.
  The real Atlas loader interprets that path as the exact pinned bundle and checks
  its identity, so a genuine accepted
  `F0(bundle A) -> F1(bundle B)` lineage cannot source-replay both generations
  from one path. The existing changed-release regression patches the source loader
  and manifest builder and therefore does not exercise this real locator contract.
  A future repair, if authorized, needs an authority-safe per-generation artifact
  resolver or custody-bound mapping plus a real-loader multi-release cold-read
  regression.

Both clean reviewers independently found one `TARGET_LOCAL` Major:

- **pre-existing accepted non-genesis bundle/v2 lineages are stranded by the new
  acceptance-bound publication rule.** Reviewed unified publishes accepted BAMF
  generations as bundle/v2. The round-4 repair now rejects any live generation > 0
  v2 parent from authorizing a fresh successor, while historical feature-lineage
  replay also requires the new acceptance-bound manifest schema. Cold load itself
  still succeeds, but the accepted lineage cannot take and publish the next
  controlled optimizer step. B13/B13.2 explicitly require cold-resume continuation,
  and #697 requires their existing custody/cold-resume contract to remain intact.
  No v2-to-acceptance-bound sealing or migration path exists in this candidate.

Both reviewers initially examined whether acceptance criterion 7 required A02
consumer edits in this B13 branch, then independently retracted that as a
`TARGET_LOCAL` finding after applying #697's explicit ownership boundary: #399 is
the separately owned downstream A02 consumer. The preserved #399 composition is
cross-owner proof and does not authorize moving A02 implementation into #697.

The five aggregate C09 `BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT` errors remain
inherited/base-only and unrelated to the round-5 disposition.

Round 5 is the ADR-127 default episode cap. `EGM-Failed` remains correct.
Automatic repair/re-review stops here: no round 6, new episode, `EGM-Pending`
transition, or PR is authorized without a design return or explicit human
authority. Human-only merge authority remains unchanged.
