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
- Exact M3 verified code candidate: `97780aa3335b7197f31d040e91a4b202161e9d9e`

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
`test_accepted_progression_fails_closed_when_support_replay_lacks_authority`.

### Major 2 - F15 remediation-root proof

Stale-replay escalation now computes the transitive affected artifact closure from the
signed correction dependency through the accepted dependency index. Caller-asserted
`affected_artifact_ids` must be a subset of that proven closure before they can become
process-fault roots. An unrelated but internally graph-valid path is rejected.

Focused regression is embedded in
`test_post_remediation_stale_replay_escalates_but_new_evidence_does_not`.

### Major 3 - production expiry/as-of dependency

Real packed-frame artifact ownership now projects the compiler's approved-context digest
as a first-class C09 `TIME` dependency. That digest is already derived from the real
`TaskScope`, policy, and exact relevant `SourceGrant` frontier, including
`observed_frontier`, `effective_time`, `observed_at`, `effective_from`, and
`effective_until`. This uses the production context-eligibility authority rather than a
synthetic-only temporal fixture. The generic `project_as_of`/`bind_as_of_dependency`
helpers remain available, but production validity is bound through the stronger existing
approved-context commitment.

Focused regression:
`test_real_packed_frame_owner_projects_context_time_dependency`.

### Major 4 - crash recovery across successor publication

Accepted-ledger transaction recovery now recognizes an ancestor transaction's complete
record as a prefix of a longer shared-ledger suffix. It still validates the filtered
manifest-specific history against the transaction target before committing recovery.
Thus a legitimate successor append no longer turns an ancestor post-fsync/pre-history
crash into `BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT`.

Focused regression:
`test_ancestor_commit_crash_recovers_after_successor_append`.

## Verification

Exact M3 detached worktree:
`/Users/emilie/Code/bamf-752-h3-repair-exact-20261107`

Exact verified SHA:
`97780aa3335b7197f31d040e91a4b202161e9d9e`

- Focused H3 regression set: 8 tests, PASS.
- Widened deterministic C09/custody/projection/authority ring: 49 tests, PASS.
- `git diff --check`: PASS.
- `BILQIS_QUALITY_BASE_REF=bd3657e170c8bdc046a7bb28524c0fb829ca7ce9 npm run quality:changed`: PASS.
  - development structure: 0 violations
  - governance integrity: 0 violations
  - new changed-file smell findings: 0
  - legacy trainer authority: PASS; 7/7 tests PASS
  - BAMF flow control: PASS; 15/15 tests PASS
- `python3 -B scripts/verify_bamf_0_2_contracts.py`: 43/43 PASS.
- Global workstack validation remains `held`, with `issues: []` and
  `registry_integrity: valid`, on the same eight repository-global dependency keys:
  `A03.4`, `A05.4`, `A05.5`, `A08.1b.2`, `A08.1b.5`, `B02.4`, `B11.1a`, `C14.4`.

The global `held` result is not a C09 schema or validator failure.

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
