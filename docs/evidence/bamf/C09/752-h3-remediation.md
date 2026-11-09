# C09 / #752 H3 remediation receipt

Date: 2026-11-07

This receipt records implementation work performed after the immutable EGM episode
`C09-752-EGM-H3-20261107`. It does not revise that episode's historical verdict.

## Historical review boundary

- H3 reviewed head: `223d2c367e431dde93ce54dd9b1042690d187759`
- H3 reviewed base: `947a4ddda2c133cabec846b09d3b58d18732dcf1`
- H3 verdict: `FAIL - 3 Blockers, 4 Majors, 0 Nits`
- H3 report SHA-256: `6e390b4218a94f1725d51e7d0ec04ea6ce3560ee7c5c6a70e27aeb5010de2e3f`
- H3 remains immutable failed review history. No H4 review was started or implied.

## Reconciled repair candidate

- Repair implementation commit: `282ce3a863404f9b81f698b57a15644828c58e8b`
- Current unified consumed by merge commit: `bd3657e170c8bdc046a7bb28524c0fb829ca7ce9`
- Unified refresh merge: `5389b49e10d79fb0af6e8d3036daf7a0eddeb283`
- Merge-resolution correction: `97780aa3335b7197f31d040e91a4b202161e9d9e`
- Final exact M3 verified code candidate: `643dd73cd0d941728de1b5df53e3bca8ebfedd8a`

The unified refresh produced two rename/rename conflicts in custody test organization.
The competing file contents were identical. The resolution retained unified's current
`contracts/` compartment. A staged conflict marker in
`contracts/test_generation_acceptance.py` was detected by `quality:changed`, replaced
byte-for-byte from current unified, and committed before exact-head verification.

## H3 finding remediation

### Blocker 1 - cold correction branch ancestry

The support journal's "already actuated" state no longer doubles as correction branch
history. Accepted correction targets now reconstruct authenticated `CorrectionBranches`
from accepted lineage before `seen` suppresses duplicate owner actuation. A cold owner
therefore retains E1 ancestry and can accept a later signed E2 that supersedes E1.

Focused regression:
`test_cold_rehydrated_correction_remains_branch_ancestor_for_supersession`.

### Blocker 2 - cumulative learned-support provenance

Candidate transaction proofs remain transaction-local. Capability support instead walks
accepted generation ancestry newest-to-oldest and resolves each retained capability to
its newest accepted generation that actually carries source-qualified anchors for that
capability. Current support custody and source-qualification generation are represented
separately, so an unrelated B-only successor does not erase A's support provenance.

Focused regression:
`test_retained_capability_provenance_survives_unrelated_successor_acceptance`.

### Blocker 3 - historical fault release after fresh requalification

Persisted process-fault evidence remains in accepted history. Its live capability-support
hold is now generation-aware. A fault still applies when the current capability support
is the same source-qualified generation, but a proven newer accepted generation that
freshly source-qualifies that capability releases the ancestor live hold/update. Foreign
or unordered generations fail closed.

Focused regressions:
`test_stale_fault_requalifies_support_loaded_only_after_fault` and
`test_fresh_source_qualified_successor_releases_ancestor_support_fault`.

### Major 1 - accepted progression correction authority

Accepted progression no longer leaks an untyped replay exception when current support
cannot be reconstructed because correction authority is absent or rejected. Support
loading failures collapse into the existing typed fail-closed progression gate for
missing/current support. Accepted correction replay also explicitly rejects missing
correction authority before dereferencing a registry.

Focused regression:
`test_cold_accepted_correction_history_fails_closed_without_authority`, with the
mock-boundary witness `test_accepted_progression_fails_closed_when_support_replay_lacks_authority`
retained as a narrower unit check. The cold-history proof also verifies that providing
valid correction authority replays the persisted correction into a live
`CURRENT_CAPABILITY_SUPPORT_HELD` gate.

### Major 2 - F15 remediation-root proof

Stale-replay escalation now computes the transitive affected artifact closure from the
signed correction dependency through the accepted dependency index. Caller-asserted
`affected_artifact_ids` must be a subset of that proven closure before they can become
process-fault roots. An unrelated but internally graph-valid path is rejected.

Focused regression is embedded in
`test_post_remediation_stale_replay_escalates_but_new_evidence_does_not`.

### Major 3 - production expiry/as-of dependency

Packed-frame artifact ownership now retains the real compiler configs that produced the
rows it governs. For each packed frame, the owner resolves the approved envelope's exact
frame/member source handles back to their real `SourceGrant`s and derives a C09 `TIME`
dependency from the known `observed_at`, `effective_from`, and `effective_until`
boundaries plus the current `TaskScope.observed_frontier` and `effective_time` boundary
buckets. Ordinary clock movement inside one bucket does not churn dependency identity.
Crossing a known validity boundary changes the dependency deterministically. The
production `require_row(row, config)` read seam recomputes that dependency and installs a
fail-closed owner-local temporal hold before the packed artifact can be reused when only
its temporal dependency has changed. This uses the production context-eligibility
authority rather than a synthetic-only temporal fixture.

Focused regression:
`test_real_packed_frame_owner_holds_when_source_grant_expires`, which gives an approved
production source grant `effective_until=6`, advances the real task's `effective_time`
from 5 to 6, and proves `BAMF_C09_ARTIFACT_HELD` before reuse.

### Major 4 - crash recovery across successor publication

Accepted-ledger transaction recovery now recognizes an ancestor transaction's complete
record as a prefix of a longer shared-ledger suffix. It still validates the filtered
manifest-specific history against the transaction target before committing recovery.
Thus a legitimate successor append no longer turns an ancestor post-fsync/pre-history
crash into `BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT`. Recovery also validates that
later accepted-C09 tail records belong to the live accepted descendant lineage; a
well-formed record carrying a foreign manifest is rejected rather than silently filtered.

Focused regressions:
`test_ancestor_commit_crash_recovers_after_successor_append` and
`test_ancestor_recovery_rejects_foreign_manifest_suffix`.

## Verification

Exact M3 detached worktree:
`/Users/emilie/Code/bamf-752-h3-repair-verified-20261107`

Exact verified SHA:
`643dd73cd0d941728de1b5df53e3bca8ebfedd8a`

- Final exact-head deterministic ring, including frame-encoder construction, all focused
  H3 regressions, C09/custody/projection/authority preservation, and adversarial recovery:
  55 tests, PASS.
- `git diff --check`: PASS.
- `BILQIS_QUALITY_BASE_REF=bd3657e170c8bdc046a7bb28524c0fb829ca7ce9 npm run quality:changed`: PASS.
  - development structure: 0 violations
  - governance integrity: 0 violations
  - new changed-file smell findings: 0
  - legacy trainer authority: PASS; 7/7 tests PASS
  - canonical legacy-trainer source run:
    `/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`
  - BAMF flow control: PASS; 15/15 tests PASS
- `python3 -B scripts/verify_bamf_0_2_contracts.py`: 43/43 PASS.
- Global workstack validation remains `held`, with `issues: []` and
  `registry_integrity: valid`, on the same eight repository-global dependency keys:
  `A03.4`, `A05.4`, `A05.5`, `A08.1b.2`, `A08.1b.5`, `B02.4`, `B11.1a`, `C14.4`.

The global `held` result is not a C09 schema or validator failure.

The earlier GitHub remediation checkpoint comment `6705215565` was posted before the
post-implementation read-only audit completed. That audit correctly found the first M3
implementation insufficient because it merely labeled an approved-context digest as
`TIME` without making production validity change when an expiry boundary was crossed.
The final implementation and proof above supersede that provisional checkpoint. The
earlier comment remains historical evidence and is not edited or erased.

## Governed stopping boundary

- Issue #752 remains open and `EGM-Failed` until a separately authorized fresh review
  changes that state.
- H3 remains historical FAIL; this remediation receipt does not claim EGM PASS.
- No H4 review was automatically started.
- No final PR was created.
- No merge into unified or `main` was performed by this repair checkpoint.
- No issue closure was performed.
- No neural-state mutation or trainer run was performed.
- Prometheus was not used.

## Residual audit correction | 2026-11-07

This section supersedes the earlier remediation disposition where it conflicts,
without rewriting either the immutable H3 FAIL or the implementation history above.
A fresh residual audit against the repaired branch found that six H3 findings are
mechanically closed, while Major 3 still lacks the shared production authority seam
needed to claim closure.

### Major 4 hardening - accepted descendant suffix only

The original successor-crash repair accepted the ancestor transaction record as a
prefix of a longer shared-ledger suffix, but ancestor recovery filtered later manifest
records before proving that they belonged to the current accepted descendant lineage.
That permitted a validly encoded accepted-C09 record for a foreign/non-descendant
manifest to be ignored during ancestor recovery.

`recover_transaction()` now validates accepted-C09 records after the transaction line
against the current accepted manifest lineage. Every accepted-C09 tail record must be
complete, canonical under its own manifest, and owned by a manifest in that lineage;
non-C09 shared-ledger records remain opaque to this transaction recovery path.

Failing-before regression:
`test_ancestor_recovery_rejects_foreign_manifest_suffix` raised no error before the
repair. Passing-after exact M3 proof runs that negative together with
`test_ancestor_commit_crash_recovers_after_successor_append`, preserving the legitimate
successor path.

### Major 3 residual - A13 -> C09 temporal invalidation authority gap

The prior claim that a packed-frame `TIME` dependency over the approved-context digest
closed production expiry/as-of invalidation was too strong. The owner is production
code, but the focused regression obtains its `TaskScope` and `SourceGrant` frontier from
the synthetic context fixture and manually applies a correction. The actual Factory
training/evaluation source paths construct `TaskScope` with fixed
`observed_frontier=0` / `effective_time=0` and issue PUBLIC_FORMAL grants with
`observed_at=0`, `effective_from=0`, and no finite `effective_until`. No non-test caller
of `project_as_of()` / `bind_as_of_dependency()` supplies a production expiry boundary.

The existing A13.3 authority already defines the correct local semantic transition:
`transition_context()` emits typed `C09ContextInvalidation` when a previously approved
context changes or becomes held, including time-driven validity changes. Its accepted
A13.3 receipt explicitly states that the transition is pure and that downstream C09
owns durable delivery/consumption of that local invalidation event. C09 currently has no
such consumption contract: its accepted runtime and `RevalidationQueue` are built around
signed `CorrectionEvent` authority. There is no existing production signer, source-owned
expiry issuer, or accepted event mapping that permits C09 to reinterpret the A13 event
as a signed correction.

An experimental owner-local temporal-hold patch was tested during this audit, but it
required a test-only call that supplied a changed compiler config to an already-created
owner. Production never does that: changed `CompiledEncoderInput` authority constructs a
new owner. The experiment was therefore reverted in the effective candidate rather than
claimed as proof.

Residual classification: `SHARED_CONTRACT / AUTHORITY_GAP`, not a safely local patch.
Closing it requires an authoritative A13 -> C09 durable invalidation/consumption seam
(or an equivalent source-owned temporal authority) before another implementation can be
honestly claimed. This remediation does not fabricate a signer, wall clock, source
expiry, or new accepted-event ontology to make the test green.

### Residual exact-head verification

- Exact local candidate: `c39655c26f2889c6b5b7912bef6483f6fcbcb5d2`.
- M3 exact detached worktree: `/Users/emilie/Code/bamf-752-c39655c2`.
- Accepted-runtime custody suite: 14/14 PASS.
- Widened deterministic C09/custody/projection/authority ring: 51/51 PASS.
- `git diff --check`: PASS.
- `BILQIS_QUALITY_BASE_REF=bd3657e170c8bdc046a7bb28524c0fb829ca7ce9 npm run quality:changed`: PASS,
  with 0 structure/governance violations and 0 new changed-file smell findings;
  legacy-trainer 7/7 PASS and BAMF flow-control 15/15 PASS.
- `python3 -B scripts/verify_bamf_0_2_contracts.py`: 43/43 PASS.
- Global workstack remains the same eight-key dependency hold with `issues: []` and
  `registry_integrity: valid`; it is not a C09 validator failure.

Current truthful disposition: H3 remains historical FAIL; six findings are repaired;
Major 3 remains open on the authority seam above. No H4 is authorized or implied.

### Post-split exact-head verification addendum

The accepted-runtime recovery witnesses were subsequently split from
`test_accepted_runtime_custody.py` into
`test_accepted_runtime_recovery.py` without changing production recovery code.
The reorganized candidate was then re-run from the exact detached M3 head
`67c7eaed9371ab4112dd96750c6c76cef218d4da` in
`/Users/emilie/Code/bamf-752-67c7eaed`.

- Reconciled code/test candidate before documentation-only receipt update:
  `643dd73cd0d941728de1b5df53e3bca8ebfedd8a`.
- Exact M3 head including the residual-audit receipt: `67c7eaed9371ab4112dd96750c6c76cef218d4da`.
- Reorganized widened C09/custody/projection/authority ring: 53/53 PASS.
- The ring explicitly included both accepted-runtime custody and accepted-runtime
  recovery modules, the cold accepted-progression authority history regression,
  capability-support lineage/fault release, F15 stale replay, Akasha C10 projection,
  and the retained temporal projection test.

The passing temporal projection test remains preservation evidence for the currently
implemented context-digest dependency only; it does not override the Major 3 authority
gap documented above.

### Major 3 implementation checkpoint - durable A13 to C09 consumption

User-authorized blocker resolution resumed from exact remote-equal head
`5f2aa2c1fea34a25377654a903defe15866c09ce`. The semantic implementation head is
`c8c9675829e5d83a138fc33d8ca3d3dec05a1f12`. Historical H3 remains FAIL. This
checkpoint does not start H4 or claim merge readiness.

Lane C now consumes the accepted A13.3 transition without converting it into a
`CorrectionEvent`. `AcceptedRuntimeHost.record_context_transition()` re-runs the
authoritative A13.3 `transition_context()` operation under current accepted B13 custody.
Each resulting `C09ContextInvalidation` is stored as its own canonical
`BAMF_C09_CONTEXT_INVALIDATION` record in the existing crash-safe accepted-C09 ledger.
The record retains the original A13 event ID and binds it to the accepted manifest.

Live delivery and cold replay send that typed event to registered retained artifact
owners. C09 resolves the old approved-context digest to the existing
`TIME time:asof:context:<digest>` reverse edge, holds direct consumers, and walks only
declared `ARTIFACT` descendants in that owner's dependency index. Reads fail closed with
`BAMF_C09_ARTIFACT_HELD`. A newly materialized owner built from a different context
digest does not inherit the old hold merely because an older event exists.

Context invalidation replay does not require a correction-signing registry. Signed
source corrections still retain their existing registry requirement and branch/replay
path. The implementation therefore does not mint a signer, wall clock, source expiry,
or caller-owned correction authority.

The focused production regression in
`test_accepted_correction_runtime.py` uses an accepted B13 generation and the retained
motif owner. It records an A13 transition through `AcceptedRuntimeHost`, verifies that
the durable ledger contains the typed event and no correction payload, proves the live
artifact hold, clears process caches, then proves the hold survives cold replay without
a correction registry.

Local executable proof is limited by this worktree host. Default Python 3.14 lacks
`mlx`; system Python 3.9 has MLX but cannot execute the repository's Python 3.10+
typing syntax. Both attempts stopped during module import before the regression ran.
The bounded checks that do not require that unavailable interpreter combination pass:

- changed production/test modules compile under Python 3.14;
- `quality:changed` against `bd3657e1...`: PASS, with zero new changed-file findings;
- BAMF flow control: PASS, 15/15 tests;
- BAMF contract verifier: 43/43 PASS;
- `git diff --check`: PASS.

The remaining authority boundary is upstream of this consumer. A13/source authority
must supply the real changed task/frontier/policy inputs that cause
`transition_context()` to emit an invalidation. C09 does not infer elapsed time or
invent an expiry. The durable Lane-C consumption seam is implemented; review status
remains unchanged until a separately authorized review action occurs.

### Qualified M3 execution addendum

After the implementation/evidence head `e7ca7fb8ee49f69f4b6364d55b646dc91b19d73b`
was pushed and read back exactly, the new regression was re-run from a fresh snapshot
on the existing qualified M3 Ultra environment. This replaces the local interpreter
limitation above with executable product evidence without changing the historical H3
review state.

- focused `test_accepted_correction_runtime.py`: **11/11 PASS**;
- affected `runtime/tests/correction` plus accepted-runtime regression:
  **52 passed, 8 subtests passed**;
- no H4, EGM, PR, or merge was started.

This proves the new Lane-C typed-event ledger, live hold and cold replay behavior. It
does **not** prove the still-missing upstream production producer for real time-sensitive
task/frontier/policy changes, so Major 3 remains open at that authority boundary.

### Current-unified reconciliation checkpoint

The remediation branch was refreshed non-destructively against current reviewed unified
`5f8f3d4b42cc4656020e4427c7d8e822825a36f9` by merge commit
`69756136b03df34d689feaa92523cc6ef4ce3fe5`. The merge preserves the Lane-C typed
A13.3 invalidation consumer and also consumes the newer reviewed C12 package-import and
A09.5 event work from unified.

The newer unified tree does not close the remaining Major 3 authority boundary. A
non-test search finds `transition_context()` consumed only by C09's accepted runtime
consumer; no Factory or source-adapter production owner supplies a finite
`effective_until` boundary. The repository therefore still has no source/A13 producer
that can authoritatively cause a real retained artifact's time-sensitive context to
cross a validity boundary. Event timestamps introduced elsewhere are not silently
reinterpreted as rights expiry.

Merge-surface verification:

- merge-base with current unified: exact `5f8f3d4b42cc4656020e4427c7d8e822825a36f9`;
- `git diff --check`: PASS;
- BAMF contract verifier: 43/43 PASS;
- BAMF flow-control validation: PASS; tests 15/15 PASS;
- accepted-runtime semantic implementation remains `c8c9675829e5d83a138fc33d8ca3d3dec05a1f12`,
  whose qualified M3 proof remains 11/11 focused plus 52 passes and 8 subtests;
- the local default Python environment does not provide pytest, so that qualified M3
  proof was not falsely represented as freshly rerun during this merge-only checkpoint.

Truthful disposition remains unchanged: H3 is historical FAIL; six findings are repaired;
Major 3 remains open upstream on production temporal-authority production. No H4, final
PR, merge of #752 into unified/main, issue closure, neural mutation, trainer run, or
Prometheus use is authorized or implied.

### Major 3 closure after reviewed #906 integration

The upstream authority gap is now resolved through reviewed integration rather than
a branch-local synthetic time source. PR #907 merged #906 into reviewed unified at
`fd9ef2890149ab5ae395640ce980a20f13a388c6`, carrying semantic repair
`3b80a76c0acafce79a061174554fb8ade0c62618`.

The canonical #752 branch merged that reviewed unified at
`b177af8cd545d40454a9c7b26c9e4ab1f49fc640`. The only semantic integration
conflict was accepted-generation custody: #752 keeps the split
`accepted_runtime.py` owner while consuming #478's reviewed
`_require_published_acceptance(...)` check at both cold and in-memory accepted
generation boundaries.

The former synthetic Major-3 witness was replaced with the actual producer to
consumer path. The regression now:

1. obtains `SourceContextTransitionAuthority` from
   `issue_source_context_transition_authority(SELECTION)`;
2. derives task, policy, frontier and finite validity only from that hash-pinned
   source/policy authority;
3. retains a production `PackedFrameArtifactOwner` whose TIME edge names the
   approved context digest;
4. crosses only the owner-issued boundary using `source_lesson_expiry_task(...)`;
5. records the transition through `AcceptedRuntimeHost.record_context_transition(...)`;
6. persists `BAMF_C09_CONTEXT_INVALIDATION` without a `CorrectionEvent` or signer;
7. proves `BAMF_C09_ARTIFACT_HELD` before live retained-artifact reuse; and
8. clears process-local custody, rebinds the accepted generation, and proves the
   same hold after cold replay.

The integrated behavioral test landed at
`3c6d08cd119fbf47b87147b65121b9aad2e1edc6`. Current-unified structure policy
then required the accepted-runtime test module to be split below the 240-line
threshold. That behavior-preserving split and source-owned temporal fixture
extraction landed at
`cf1e46bb576be119fe99e48ad113d7319d42ef43`.

Post-integration proof:

- reviewed #478 acceptance and publication durability: **28/28 PASS**;
- accepted #752 correction runtime, including the real #906 temporal path:
  **9/9 PASS**;
- complete C09 correction directory: **37/37 PASS**;
- preservation ring across accepted-runtime custody/recovery, stale replay,
  motif ownership, capability-support lineage/ownership, exact-cache authority,
  and production cold-read custody: **45/45 PASS**;
- #906 source-authority contracts: **10/10 PASS**;
- exact mounted A01 source witness: **3/3 PASS, 0 skips**;
- `quality:changed` against reviewed unified: **PASS**, development structure
  and governance integrity 0 violations, 0 new changed-file smell findings,
  legacy-trainer authority 7/7 PASS, BAMF flow control 15/15 PASS;
- BAMF contract mirrors: **43/43 PASS**;
- `git diff --check`: **PASS**.

The legacy-trainer checker initially failed on pristine reviewed unified
`fd9ef289...` because the newly merged #906 receipt named a legacy-trainer
check without naming the canonical source run. The same failure reproduced on
an untouched detached unified worktree. The #752 integration therefore adds only
the missing canonical source path to that receipt; no #906 behavior changes.

Engineering disposition: all seven historical H3 findings now have integrated
repairs and the previously open Major 3 authority seam has an end-to-end
production-path witness. Historical H3 remains immutable **FAIL - 3 Blockers,
4 Majors, 0 Nits**. This section does not claim H4 PASS. The user explicitly
authorized continuation of #752 after #907 merged, satisfying the prior gate for
the next whole-candidate EGM review. No neural execution, trainer run, H4 verdict,
PR merge, or issue closure is implied.

### H4 current-unified freeze

Reviewed unified advanced once more after the first H4 freeze, from
`fd9ef2890149ab5ae395640ce980a20f13a388c6` to
`cc48ac40d875f0c2ae8ffbdc70001dbfc4815334` through reviewed B13.2 / #479.
That delta changes no #752 production owner, C09 runtime, source-context authority,
or correction contract. It adds B13.2 full-resume controls, one learning-layout
test adjustment, evidence, and Lane-B bookkeeping.

The canonical #752 branch consumed that reviewed delta without conflict at merge
head `0290f00ff4a1a6957bc82ff8786adf3646836204`. The newly introduced B13.2
local controls then ran **8/8 PASS**; the complete disposable full-resume witness
remained one intentional environment-gated skip requiring
`BILQIS_BAMF_FULL_WITNESS`. No #752 behavioral receipt was invalidated by the
disjoint delta, so the preceding 28/28, 9/9, 37/37, 45/45, 10/10 and real-A01
3/3 results are reused under the repository's passing-evidence reuse rule.

Changed-scope governance was rerun against exact reviewed unified
`cc48ac40...`: development structure and governance integrity PASS with zero
violations, code-smell audit reports zero new changed-file findings,
legacy-trainer authority and its 7/7 regressions PASS, BAMF flow control and
15/15 regressions PASS, BAMF contracts remain 43/43 PASS, and
`git diff --check` is clean.

This is the final engineering freeze before the explicitly authorized H4
whole-candidate review. H3 remains immutable historical FAIL until and after that
review; no H4 verdict is claimed here.

### H4 exact-head review and remediation checkpoint

Fresh isolated H4 review of exact candidate
`5480830d1ca8a762b58e676a6ab33218e1bea54e` against reviewed unified
`cc48ac40d875f0c2ae8ffbdc70001dbfc4815334` used pinned Elephant-Goldfish
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`. The exact-head verdict was
**FAIL - 0 Blockers, 2 Majors, 0 Nits**. This is append-only later review evidence;
historical H3 remains immutable **FAIL - 3 Blockers, 4 Majors, 0 Nits**.

The first H4 Major was an `AUTHORITY_GAP` at the accepted C09 temporal ingress.
The accepted host still accepted raw frames, task scope, source frontier and policy,
then reran `transition_context()` directly. A caller holding otherwise legitimate
finite #906 frames could therefore choose `effective_time == effective_until` and
bypass the source-owned `source_lesson_expiry_task()` boundary. A failing-before
regression reproduced the defect: the forged call emitted no `BilqisError`, so the
test failed exactly because caller-selected expiry was still admissible.

Semantic repair `4ff3294abfae8d39c25d6ba525dd1ba3bc6c7cf7` removes that raw authority seam.
`AcceptedRuntimeHost.record_context_transition()` now accepts the source-owned
`SourceLessonContexts` object and rejects raw caller state. C09 revalidates the
opaque #906 `SourceContextTransitionAuthority`, reconstructs the source frontier
from that authority plus its issued grants, derives the expiry task internally via
`source_lesson_expiry_task()`, and only then emits the existing typed
`C09ContextInvalidation`. No wall clock, TTL, evidence timestamp, correction signer,
`CorrectionEvent` conversion or replacement event ontology was introduced. The
adversarial regression now passes and proves the rejected forged call appends no
accepted-C09 record.

The second H4 Major was a `SHARED_CONTRACT` generation-identity mismatch in
capability-support custody. B11 correctly records the pre-update execution generation
that issued its training authority, and that source-generation identity remains valid
provenance. C09 had also reused that historical source generation as the live support
owner's generation binding, however, while progression asks for the current accepted
post-update execution generation. A failing-before retained-update regression proved
the mismatch by raising `BAMF_C09_CAPABILITY_SUPPORT_GENERATION_DRIFT` after a real
weight-changing retained candidate was accepted.

The same semantic repair preserves the historical source-generation anchor inside the
accepted provenance record but binds the live capability-support owner to the current
accepted execution generation, recomputed from the authenticated current accepted
student. The retained-update regression now passes, while source provenance and
correction ancestry remain unchanged.

Post-repair executable proof on the canonical branch:

- both new regressions demonstrated failing-before behavior for the intended reasons;
- accepted temporal ingress focused tests: **3/3 PASS** after repair;
- capability-support owner plus current-generation regression: **8/8 PASS**;
- capability progression plus cold accepted-history checks: **8/8 PASS**;
- widened correction, capability, accepted-runtime, custody, recovery and stale-replay
  ring: **72/72 PASS**;
- changed-scope development structure and governance: **PASS, 0 violations**;
- changed-file smell delta: **0 new findings**;
- legacy-trainer authority: **PASS, 7/7**;
- BAMF flow control: **PASS, 15/15**;
- BAMF contract mirrors: **43/43 PASS**;
- `git diff --check`: **PASS**.

Engineering disposition: the complete known H4 finding set is repaired at semantic
head `4ff3294a...`. H4 itself remains historical FAIL until a new fresh-context
whole-candidate review evaluates a newly frozen exact head. No PR, merge, issue
closure, or neural/trainer mutation is claimed here.

### H4 re-review round 2 and package-import custody repair

The next fresh whole-candidate review evaluated exact remote-equal candidate
`acc1500a4e36eed5de02dae6c280cef3d3e3ef6f` against unchanged reviewed unified
`cc48ac40d875f0c2ae8ffbdc70001dbfc4815334`, again under pinned EGM
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`. All three independent lenses
converged on **FAIL - 0 Blockers, 1 Major, 0 Nits**, with no additional severe
finding. Both Majors from the preceding H4 round were confirmed closed.

The new `PARENT_INTEGRATION` Major was a sibling-path custody gap. Normal Factory
retention already required `source_context.require_accepted_runtime(run_dir)` before
source draws and complete-solver work, but `evaluate_factory_package_import()` did
not. `screen_delta_candidate()` could therefore hand package-import C05 screening an
unbound source execution context; compiled-batch and solver-owner registration could
become inert, durable accepted C09 correction replay/holds could be skipped, and the
resulting C05 decision could later reach publication without repeating the screen
under accepted-runtime custody.

A failing-before regression proved the gap directly: the package-import owner test
expected `require_accepted_runtime(Path("unused"))` and failed because the call count
was zero. Semantic repair `f7537a0a5874ef031d992f71ee86f42ee9447d71`
places the same accepted-runtime custody boundary at the start of package-import
screening, before any live-parent load, source draw, instrument construction or C05
solver evaluation. A second regression makes the ordering explicit: if custody raises,
the package-import live-parent/C05 path is not entered.

Post-repair proof:

- package-import owner + source-execution custody ring: **11/11 PASS**;
- complete Factory capability directory: **50 PASS, 0 FAIL, 6 explicit A01-mount
  skips**;
- changed-scope development structure and governance: **PASS, 0 violations**;
- changed-file smell delta: **0 new findings**;
- legacy-trainer authority: **PASS, 7/7**;
- BAMF flow control: **PASS, 15/15**;
- `git diff --check`: **PASS**.

The prior fresh A01 real-source witness on the repaired lineage is also **3/3 PASS**,
including the explicit-policy-expiry crossing. Historical H3, H4 round 1, and H4
round 2 remain immutable failure receipts. This checkpoint asserts only that the
complete known round-two finding set has been repaired; a new fresh-context
whole-candidate review remains the merge-readiness gate.

### H4 round 3 exact-head acceptance

Fresh isolated whole-candidate H4 round 3 reviewed exact remote-equal candidate
`fa667a8b0ad1cb6dba628b0771f69a4965e98a2c` against reviewed unified
`cc48ac40d875f0c2ae8ffbdc70001dbfc4815334` using pinned Elephant-Goldfish
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`.

All three requested independent lenses passed:

- implementation-readiness: **PASS - 0 Blockers, 0 Majors, 0 Notes**;
- codebase/ownership: **PASS - 0 Blockers, 0 Majors**;
- semantic/comprehension: **PASS - 0 Blockers, 0 Majors**.

The round re-traced the repaired authority and integration seams rather than treating
the prior focused tests as sufficient by themselves. Review confirmed that #906's
source/policy-issued temporal authority is required at accepted C09 ingress; raw
caller-selected expiry cannot mint a durable invalidation; the event remains typed
`C09ContextInvalidation` and separate from `CorrectionEvent`; no wall-clock, TTL,
evidence-time, or signer authority is fabricated; historical source-generation
provenance remains distinct from current accepted execution eligibility; and both
ordinary and package-import C05 screening require accepted-runtime/C09 custody before
solver use. Live/cold holds, stale replay, correction ancestry, crash recovery,
dependency indexing and publication gates exposed no unsettled severe defect.

Mechanical evidence on the accepted lineage includes the previously recorded
**72/72** widened runtime/custody/capability ring, **11/11** package-import/source
custody ring, Factory capability **50 PASS / 0 FAIL / 6 explicit A01-mount skips**,
real mounted A01 source witness **3/3 PASS**, BAMF mirrors **43/43 PASS**, and green
changed-scope structure/governance/smell/legacy-trainer/flow/diff checks.

Review history remains append-only and immutable:

- H3: **FAIL - 3 Blockers, 4 Majors, 0 Nits**;
- H4 round 1: **FAIL - 0 Blockers, 2 Majors, 0 Nits**;
- H4 round 2: **FAIL - 0 Blockers, 1 Major, 0 Nits**;
- H4 round 3: **PASS - 0 Blockers, 0 Majors, 0 Nits/Notes**.

Engineering disposition: issue #752 is EGM-accepted for governed turn-in at exact
semantic/review head `fa667a8b...`. Subsequent evidence/flow/PR bookkeeping is
nonsemantic and does not invalidate H4 unless it changes implementation, tests, or
governing semantics. No neural/trainer mutation and no self-merge are authorized.
