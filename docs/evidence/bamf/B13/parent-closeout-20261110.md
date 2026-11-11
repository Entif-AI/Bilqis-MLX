# B13 parent integration closeout - 2026-11-10

Issue: #372 `BAMF-0.2 B13 | Persist and cold-resume the complete BAMF learning generation`

Lane: B

Reviewed unified consumed before parent integration work:
`8b8625b85b571ae1eeecbc683157895db029a812`.

Exact semantic/test proof head:
`731286ef7f0041dd821a23ac5a6cc789a6a96f7e`.

PR: #983.

## Accepted child and dependency state

B13.1 #478, B13.2 #479, B13.3 #480, B13.4 #481, B13.5 #697, and B13.6 #904 are
closed and EGM-passed. B12 #370 and A02 #348 are closed. B07 parent #356 remains open,
but its B07.1-B07.4 implementation leaves and the motif-custody remediation consumed by
B13 are accepted in reviewed unified. The open B07 parent bookkeeping state does not
remove the executable dependency receipt that B13 consumes.

## Parent integration defect and repair

The first current-unified audit found no B13 production custody defect. It found stale
parent acceptance witnesses that predated later C07 and C09 authority integration.

The changed-feature tests still published an Atlas feature-map extension through generic
retention publication. Current production requires C07 authority for that transition and
requires the successor to inherit the accepted parent's C09 source-authority root. Those
tests therefore failed before feature-lineage replay. The selected changed-feature ring
was 12 passed and 10 errors on the reviewed base.

The repair changes test fixtures only. A changed feature-map successor now starts from
the accepted parent returned by `load_bamf_generation_authority`, preserves the parent's
source-authority custody, receives an `AtlasAdmissionBinding`, and publishes through
`publish_atlas_admission_generation`. The production publisher still revalidates C09
inheritance before pointer publication.

The cache-separation fixture had the same age problem. Genesis did not install the host
source-authority fixture, synthetic acceptance omitted the current registry digest, and
the model-swap specimen discarded accepted-parent sidecars. The repair supplies those
current prerequisites. Generic parameter extension still fails at the C07 boundary.
C07-authorized extension and model swap both invalidate the old execution cache and
rebuild to the same output as fresh execution.

The cold-cache witness also reached full-tensor validation before the stale-cache guard
because its tiny numerical fixture was no longer active at the assertion. Restoring that
fixture context makes the test reach the intended B13 validator. It still requires
`B13_EXECUTION_CACHE_STALE`; corrupt cache identity still fails separately.

No B13, C07, or C09 production code changed. No guard was removed or weakened.

## Original B13 acceptance reconciliation

| Parent acceptance | Current executable proof |
| --- | --- |
| Complete parameter, AdamW, row-count, teacher, ABI, and next-seed custody | Full schema and clean-process resume: 2/2 pass. The expanded witness covers 215 parameter tensors and 860 serialized arrays. |
| Crash before pointer preserves the old generation | Publication durability/recovery tests in the 79-test parent ring. |
| Crash after pointer before outbox delivery replays once without another optimizer step | Publication recovery tests in the 79-test parent ring. |
| Wrong motif map, bank extent, compiler identity, topology, or correction epoch fails before mutation | Sidecar and generation-authority contract tests in the 79-test parent ring. |
| Accepted candidate followed by rejected candidate resumes only accepted state | Publication rejection and cold-continuation tests in the 79-test parent ring. |
| Frozen historical v1 remains readable by the historical reader and fails as BAMF-v2 before v2 allocation | Canonical Microspenics frozen-v1 witness: 1/1 pass. |
| Source-qualified accepted state preserves motif slots and continues from exact bundle custody | Real pinned-A01 motif continuation: 2/2 pass. |
| Cold resume plus the next controlled optimizer step matches uninterrupted execution | Cold-continuation tests: 8/8 pass. |
| B01 parameter ledger is complete and singular | Full parameter-schema witness: 1/1 pass, included in the 2/2 full-custody result. |
| Derived execution caches never cross accepted-generation identity | Cache separation: 3/3 pass; stale-cache continuation is included in the 8/8 cold-continuation result. |
| Feature-map changes retain accepted source lineage across releases and relocation | Feature authority, lineage, migration, and portability: 22/22 pass. |
| Human-run lock and 100 GiB policy remain outside agent authority | This change is test/evidence only. No neural run or runtime-policy edit occurred. |

## Verification

The exact 13-module B13 parent ring that failed on reviewed unified now passes 79/79.
The same ring was 71 passed and 8 errors before this repair.

Additional exact-head results:

- feature authority, lineage, migration, and portability: 22/22 pass;
- cache separation: 3/3 pass;
- cold continuation: 8/8 pass;
- full parameter schema and clean-process resume: 2/2 pass;
- canonical frozen-v1: 1/1 pass;
- real pinned-A01 motif continuation: 2/2 pass;
- BAMF checked-in contract verification: 43/43 pass;
- flow-control validation: pass;
- governance integrity: pass;
- changed-file structure and smell checks: zero findings;
- legacy-trainer authority unit tests: 7/7 pass;
- flow-control tests: 15/15 pass;
- `git diff --check`: pass.

`npm run quality:changed` stops at two static legacy-trainer evidence violations in
`docs/evidence/bamf/C07.1b/atomic-adoption-20261109.md` and
`docs/evidence/bamf/C12.3/drift.md`. Exact reviewed unified reproduces the same two
violations. They are inherited base debt and are not changed by #372.

Hosted PR checks on semantic/test proof head `731286ef...` pass for
`semantic-abi-integrity`, `portable-core`, and `portable`.

## Independent EGM

The reviewer that found the current-unified feature-lineage Major re-reviewed exact head
`731286ef7f0041dd821a23ac5a6cc789a6a96f7e` against base
`8b8625b85b571ae1eeecbc683157895db029a812`.

Disposition: **PASS - 0 Blockers / 0 Majors / 0 Nits**.

The review confirmed that the prior Major is closed. Changed feature maps now cross the
live C07 admission seam and preserve C09 custody before pointer publication. It also
confirmed the two-release relocation and tamper negatives, stale-cache rejection, and
C07/model-swap cache invalidation without production changes.

A second independent reviewer inspected the same exact candidate and returned
**PASS - 0 Blockers / 0 Majors / 0 Nits**. It separately confirmed that the
test-only C07 binding is fixture-scoped, C09 inheritance remains production-enforced,
generic ABI-changing publication still fails at the C07 boundary, and the stale-cache
repair reaches the B13 cache guard without weakening it.

## Mutation boundary

This parent repair changes tests and evidence only. It does not change model parameters,
optimizer state, teacher state, accepted-generation bytes, source authority, runtime
policy, or training authority. Human merge remains external authority. Issue #372 stays
open until PR #983 is human-merged and the merged head is read back from reviewed unified.
