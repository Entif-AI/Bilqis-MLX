# #752 C09 cognitive artifact owner continuation — 2026-11-05

## Scope

This continuation consumes reviewed unified
`22314c413ba137df69b3d6b35768fe65e1556bfe` on top of preserved #752 head
`b4ce2c5562b34dc5b38a5b216c4b9f0d1a45496e`. It extends the already-produced
`ATLAS_FEATURE` and `PACKED_FRAME` owners with two additional production owner
paths and one bounded composition seam:

- `EXACT_CACHE` from real `PureOperationMemo` writes and reads in `execute_dag`,
  including the canonical task time scope;
- `OPERATOR_COMPOSITION` is indexed only after the existing solver qualification
  contract accepts and successfully executes a supplied `QualifiedComposition` for
  the current source/rights/correction/time scope, and subsequent reuse is gated.
  Current reviewed unified still has no non-test producer/deserializer that publishes
  `QualifiedComposition`, so this is a real consumer/materialization seam but not yet
  a complete production producer/consumer lifecycle;
- `CAPABILITY_SUPPORT` from a completed assessment and the artifact IDs actually
  used by each immutable solver result. `evaluate_capabilities` now materializes and
  binds that ledger at the production assessment boundary; a signed correction fed
  to its owner runs the existing C09.2 transition into `REQUALIFICATION_REQUIRED`,
  targeted source tasks, and C10 invalidation intent. This artifact is the C09.2
  correction ledger: its non-test readers mark or publish stale-support state.
  Those invalidation/requalification reads are intentionally not treated as reuse of
  qualified cognition, because blocking the notification on the hold it reports
  would prevent the recovery path itself.

No caller can register an arbitrary `ArtifactNode`. The owner derives IDs, content
digests and immediate dependency edges from the production objects it receives.
Correction state stays in one `CognitiveArtifactOwner` retained by `CompleteSolver`.
Exact memo hits and qualified-composition reuse call the owner before the value is
used. New unrelated cache artifacts may still materialize while another correction is
pending; owner registration precedes the memo write so a failed registration cannot
leave an unindexed cache entry. Per-evaluation support is sealed under the canonical
solver replay identity, preventing a later run of the same task from contaminating a
frozen earlier assessment. Learned support is materialized as immutable
`CapabilitySupport` records linked to the frozen assessment history and its actual
support artifacts. Existing
C09.2 `mark_affected_capabilities` / C10 invalidation-intent readers consume those
records only to preserve and communicate the fact that support requires fresh
qualification; they do not use the stale support as permission for inference.

`MOTIF` remains unimplemented here because current reviewed unified still has no
non-test production motif consumer that can own a before-next-use gate. Creating a
synthetic consumer or caller-supplied authority would violate the #752 acceptance
contract.

Owner index, pending queue, sealed result-support map and capability ledgers remain
process memory. `CompleteSolver` now accepts an externally restored owner and rejects
context-owner drift rather than silently replacing it, but current B13
`correction_frontier` custody does not serialize this C09 owner state. Cold-resume
hold continuity therefore remains an explicit blocker outside this tranche.

## Structural interruptions

Two already-reviewed byte-matching structural repairs were consumed before the
behavioral work:

- `semantics/cognitive_dag.py`: 754 -> 177 LoC, with focused production/test owners;
- `runtime/cognitive_solver.py`: 494 -> 40 LoC, followed by the existing route/session
  decomposition so changed-scope code-smell checks remain clean.

The new `cognitive_artifact_owner.py` is 304 LoC. No touched or added code file
crosses the repository structure threshold.

## Verification

Focused and owner integration proof on the final working tree before commit:

- new production-path C09 tests: 5/5 PASS, including unrelated-work continuity and
  assessment-scoped support provenance;
- complete `runtime/tests/correction` discovery: 23/23 PASS;
- complete split solver-route discovery: 14/14 PASS;
- capability/evaluation/history/authority/retention selection: 19/19 PASS;
- championship integration: 10/10 PASS;
- frame encoder: 2/2 PASS;
- source-atom discovery: 65 tests pass with 33 expected source-bundle skips and one
  inherited hard-coded owner-count failure (`36 != 32`). The same assertion fails on
  clean reviewed unified `22314c41`;
- solver transitive-import boundary: inherited failure reproduced on clean reviewed
  unified with the same 92 forbidden-module family;
- DAG transitive-import boundary: inherited failure reproduced on clean reviewed
  unified and was already independently baseline-proven during the #810 structural
  continuation;
- `npm run quality:changed` from reviewed unified: structure 0, governance 0,
  code-smell 0, BAMF flow-control valid, 15/15 flow-control tests PASS;
- `scripts/quality/check_docs.py`: PASS;
- `git diff --check`: PASS.

The actual A01 bundle is not mounted on this host, so source-bundle-dependent tests
remain skips rather than being represented as fresh real-source proof. The preserved
#752 head already carries its prior real-source ATLAS_FEATURE/PACKED_FRAME evidence.

Fresh ordinary independent review of the earlier immutable behavior head found four
Majors and no Blocker. This continuation repaired two Majors directly: unrelated
pending corrections no longer poison new exact-cache entries, and capability support
is no longer test-only or solver-lifetime task history. The remaining reviewed gaps
are preserved below rather than being disguised as completion.

## Review state and remaining gap

Fresh pinned Google EGM is intentionally not consumed for this intermediate repair.
`docs/tasks/bamf-0.2/EGM_EXECUTION.md` reserves Goldfish for an otherwise merge-ready
whole candidate. #752 is not yet eligible to request that whole-candidate review
because production `MOTIF` ownership is absent, `OPERATOR_COMPOSITION` still lacks a
non-test publisher, and C09 owner/hold state lacks a B13 cold-resume custody binding.
The ordinary independent review does not substitute for Goldfish merge-readiness
review or authorize the `EGM-Pending` label.

IPR-0220 remains an opaque controlling authority. This work does not run or mutate the
human student, AdamW, teacher, source admission, checkpoints, or excluded #708/#709/#809
surfaces.
