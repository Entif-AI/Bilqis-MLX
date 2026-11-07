# B12.2 completion receipt — 2026-11-06

Issue: #475 — BAMF-0.2 B12.2 | Commit or reject complete candidate optimizer and weight transactions

## Authority and lineage

This closeout is based on reviewed unified `b16941114dee33247ee9a9e6c013797b9d82af27`.
The fresh turn-in branch was created directly from that exact reviewed head.

Historical PR #695 is evidence only and is not being merged. Its final Google EGM finding was the execution-provenance seam: a caller-substitutable update mask could become candidate truth. That exact defect was split into remediation #710/#711, subsequently accepted and closed, and the consolidated remediation was merged to reviewed unified by PR #809. #710 and #711 both carry `EGM-Passed`.

No protected source text is reproduced here. IPR-0220 remains an opaque governing reference.

## Current B12.2 owner behavior on reviewed unified

The current owner is `bilqis_mlx.learning._retention.atlas_candidate` plus the
`_atlas_candidate` implementation package.

- `CandidateState` carries optimizer parameters, FP32 moments, uint64 per-row update counts,
  plasticity policy/counters, allocation snapshot, optimizer step, custody identity, and durable step proofs.
- `begin_candidate` validates the retained parent and starts a speculative transaction without mutating it.
- `candidate_step` accepts owner-issued `StepExecutionProvenance`, validates run/generation/manifest/topology/extents,
  parent-candidate identity, optimizer step, and candidate ordinal, derives the optimizer mask through the B09 owner,
  and only then invokes native AdamW.
- The mask therefore is no longer caller-authored final authority. This is the specific #695 EGM Major repaired by #710/#711.
- `_adamw_update` remains the numerical owner for mask-before-clip, FP32 accumulation/state, global norm clipping,
  per-row local clocks, decay, and no-loss behavior.
- `resolve_candidate(..., accepted=False)` returns the exact parent object.
- Accepted resolution publishes parameters, moments, counts, plasticity policy/counters and optimizer step together.
- Candidate state loaded from B13 custody is accepted only through validated immutable bundle parts and reconstructs
  the same step-proof/custody boundary.
- B12.2 does not independently mint or mutate motif allocation authority. The current transaction slice keeps allocation
  custody immutable and rejects caller-created non-genesis retained state; row/materialization authority remains with
  its upstream allocation/B01/B07/B13 owners rather than being reimplemented in B12.

## Acceptance reconciliation

1. **Whole candidate transaction** — parameters, moments, counts, policy/counters, allocation custody and optimizer step
   are represented together by `CandidateState`; acceptance returns one new state, rejection returns the exact parent.
2. **FP32 gradients + existing clip** — delegated to the existing native AdamW numerical owner; B12 does not duplicate it.
3. **New-row zero optimizer state** — B12 cannot self-author allocation/materialization. It consumes validated owner state;
   caller-created non-genesis allocation state is rejected. The zero-initialization invariant remains upstream-owned.
4. **Reject is all-or-nothing** — rejection returns the exact parent and therefore cannot publish partial weights,
   moments, counts, allocation or plasticity clocks.
5. **FAST/FULL and row age** — current candidate resolution advances plasticity only for an accepted candidate and derives
   participating rows from update-count deltas.
6. **Frozen vs zero-gradient participation** — final participation/update mask derives from execution-owned B09/B11
   provenance. The #710/#711 adversaries distinguish executed-zero-gradient from never-executed/frozen parameters.
7. **Durable publication/cold resume** — B13 rehydration is integrated into `CandidateState`; remediation #708/#709 and
   merged PR #809 supply accepted-generation authority and real cold-continuation proof without granting B12 independent
   publication authority.
8. **Prior EGM failure** — resolved by accepted #710/#711 remediation; both are closed with `EGM-Passed` and are present
   in the exact reviewed-unified ancestry consumed here.

## Verification evidence already bound to the delivered behavior

The accepted remediation lineage records the following focused proof before merge:

- #710/#711 focused owner/custody slice: 48 tests, 46 passed, 2 expected skips, 0 failures.
- affected retention + batch + B13 custody sweep: 139 tests, 128 passed, 11 expected skips, 0 failures.
- `quality:changed`: PASS, including structure, governance, smell audit and BAMF flow control.
- hosted semantic ABI integrity: SUCCESS after the final import repair.
- PR #809 exact semantic candidate received fresh pinned Goldfish/EGM review with 0 Blockers / 0 Majors / 0 Nits after its
  one mechanical mirror-policy finding was repaired.
- PR #809 merged these remediations into reviewed unified; issue #708, #709, #710 and #711 were closed only after merge readback.

This closeout branch intentionally makes no behavior mutation. Its purpose is to bind the now-merged implementation and
review evidence to #475 without resurrecting stale PR #695 code or weakening the newer provenance/custody design.

## Turn-in

The pull request opened from this branch must target `codex/bamf-unified-base-20261028` and use `Closes #475`.
No self-merge, live neural optimizer update, production student mutation, or main-branch mutation is authorized by this receipt.
