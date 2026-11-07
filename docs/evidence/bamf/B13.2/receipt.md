# B13.2 cold-resume continuation receipt

Issue: #709 (remediation of #479 / B13.2)
Lane: B
Branch: `codex/remediation-egm-708-711-integration-20261103`
Consumed unified head: `e9226be2f6a41f47109ca02a1103a363e64909a7`
Final candidate head: `537f4c62`

## What the previous witness proved and what it missed

The reviewed B13.2 witness saved and loaded an unbound synthetic candidate and
compared serialized state with three CPU backbone-group outputs. It never
reconstructed the Factory next-visit selection, never executed the next
controlled optimizer step, never consumed published accepted-generation custody
and never exercised the published generation pointer and lock path.

## What this receipt proves

`bilqis_mlx/runtime/tests/custody/bamf_bundle/test_cold_resume_continuation.py`
starts from an accepted generation published through the real pointer and lock
path and cold resumes it in a clean Python process
(`bilqis_mlx/runtime/tests/custody/bamf_bundle/cold_resume_probe.py`).

The witness proves:

1. The clean process reconstructs the accepted generation from the published
   pointer only, and its neural and optimizer state digest is identical to the
   in-process state that produced the generation.
2. The Factory next-visit state in custody, the teacher sidecar, survives the
   cold resume unchanged.
3. The next controlled optimizer step executes on the reconstructed state, and
   the published successor generation is byte-identical to the successor state
   computed independently in the parent process.
4. The successor generation is published through the pointer path with the
   parent manifest binding, and the published pointer then names generation 1.
5. Negative controls: a synthetic direct save-load without published custody
   cannot satisfy acceptance, and a run directory without published custody is
   refused by the custody owner before any continuation runs.

## Verification

- `python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/custody/bamf_bundle`
  → 60 passed, 0 failed, 3 skipped. The witness consumes the retention acceptance
  binding that PR #804 requires for any published generation.
- `python3 -m pytest bilqis_mlx/runtime/tests/custody/bamf_bundle/test_cold_resume_continuation.py`
  → 4 passed.

## Uninterrupted and cold continuation

The witness runs the same production continuation twice: once in the parent
process and once in a clean process that resumes from published custody only.
Both continuations publish the identical successor generation manifest, the
identical successor optimizer digest, the identical update counts and the
identical owner-bound step-proof digests, and both reach the same
retention-decision owner outcome. The probe no longer synthesizes a next
visit: it rebuilds the next-visit execution evidence from the published
custody, measures the retention evidence, and asks the retention decision
owner to decide before publication.

## Open limits

- The cross-backend, frozen-v1 and source-qualified retained-learning witness
  required by #479 remains open. It needs the externally supplied A01 source
  artifact and the frozen-v1 compatibility owner, which this witness does not
  stand in for.
- The fixture generation is not a source-qualified accepted release. The
  source-qualified feature binding of an accepted generation is owned by the
  accepted-generation feature authority delivered in PR #804.
- Issue #479 stays open; this receipt removes the cold-resume witness defect
  only.

## Authority

No student, optimizer, checkpoint lineage or live run was changed. No
self-merge is authorized. Fresh pinned EGM is reserved for the merge-ready
head.
