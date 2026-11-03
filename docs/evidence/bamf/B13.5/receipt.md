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

`bilqis_mlx/learning/_retention/atlas_acceptance.py` is the retention-owner
seam. The owner mints an `AcceptedCandidateBinding` that covers the exact
accepted optimizer identity, the accepted feature identity, the optimizer step
and the retention reason. The binding cannot be constructed outside the owner
module.

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
