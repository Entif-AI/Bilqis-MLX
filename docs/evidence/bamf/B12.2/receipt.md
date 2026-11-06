# B12.2 execution-provenance binding receipt

Issue: #710 (remediation of #475 / B12.2)
Lane: B
Branch: `codex/remediation-egm-708-711-integration-20261103`
Base: `codex/bamf-unified-base-20261028`
Consumed unified head: `e9226be2f6a41f47109ca02a1103a363e64909a7`
Final candidate head: `537f4c62`

## What the previous owner allowed

`candidate_step` accepted a raw caller `update_mask` and the candidate custody
replayed that mapping directly. The numerical mask adapter never attested that
the mask came from an actual model execution, so a caller could substitute an
alternate mask and keep a self-consistent candidate.

## What this receipt proves

`bilqis_mlx/learning/_retention/atlas_execution_provenance.py` is the new owner
seam. It derives the executed participation and the final legal mask from the
execution observation and seals them into `StepExecutionProvenance`. The record
is minted only inside that module, so no caller can construct one.

`bilqis_mlx/learning/_retention/atlas_candidate.py` now binds every optimizer
step to that provenance:

- `candidate_step` refuses anything that is not owner-issued provenance, so a
  raw caller mask is no longer an execution authority.
- The numerical mask is materialized from the owner-derived mask through the
  B09.2 owner's `optimizer_participation_mask`, which also checks the mask
  against the update-count ledger.
- The transaction records a `CandidateStepProof` per step that stores the
  digests of the owner-issued provenance, the derived participation and the
  derived mask. It never stores a caller mask mapping.

The adversarial regressions in
`bilqis_mlx/learning/_retention/tests/test_atlas_execution_provenance.py`
prove that a raw caller mapping is refused, a directly constructed or
tampered provenance is refused, a provenance that names another parameter set
is refused, that the recorded proof equals the owner-issued provenance digest,
and that unparticipating rows never advance.

## Verification

- `python3 -B scripts/run_tests.py bilqis_mlx/learning bilqis_mlx/runtime/tests/custody`
  → 631 passed, 0 failed, 44 skipped, 12 pre-existing loader errors. The loader
  errors are the known relative-import collection failures owned by #784 and
  are unchanged by this work.
- `python3 -m pytest bilqis_mlx/learning/_retention/tests/test_atlas_execution_provenance.py`
  → 5 passed.
- `python3 -m pytest bilqis_mlx/learning/_retention/tests/test_atlas_candidate.py`
  → 10 passed.
- `python3 -m pytest bilqis_mlx/runtime/tests/custody/bamf_bundle`
  → 44 passed, 11 skipped.

The learning-layout owner census is refreshed from 32 to the current 39
relocated owners. The census was already stale at the consumed unified head,
which carried 36 owners, so this repair also closes that pre-existing drift.

## Open limits

- The proof lives in the candidate transaction custody. The accepted
  `CandidateState` still carries no step-proof field, so the proof is not yet
  replayable from a persisted generation. That persistence belongs to the
  B12.2 candidate lineage on #475.
- The owner derives participation from the execution observation. Until the
  trainer calls the B09.2 owner on real execution output, the fixture proves
  the binding and not a live training path.
- Issue #475 stays open. This removes the caller-substitutable mask defect
  only.

## Authority

No student, optimizer, checkpoint lineage or live run was changed. No
self-merge. Fresh pinned EGM is reserved for the merge-ready head.
