# A02.2 capacity-expansion integration qualification — 2026-11-09

Issue #400. Lane A branch `codex/bamf02-a-semantics`.

Reviewed unified consumed before issue-owned edits:
`6a770f10074df6f4f8889d439f783ad42f5efe63`.

Current remotely verified production-repair head:
`4f5972b12fe933ee19701b17ba138a93a5bb7404`.

Status: **IMPLEMENTATION_RECONCILED; FULL COMPOSED WITNESS AND FINAL INDEPENDENT REVIEW PENDING**.

## Integrated ownership boundary

The historical A02.2 staging adapter is no longer an isolated prospective API.
Reviewed A02.1/#399 now issues an exact `A02StagedVocabularyExtension`, and
reviewed C07.1b/#510 consumes only that owner-issued handoff before issuing the
live C07/B13 admission binding. A02 still grants no publication authority.
Generic C05/B13 vocabulary or active-set publication remains fail-closed at
`BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED`.

This issue therefore qualifies the current integrated sequence:

`A01/B13 source authority -> A02 plan/stage -> owner-issued staged handoff ->
C07 persisted-lease/precommit replay -> B13 accepted generation`.

It does not revive the historical direct-A02 publication design.

## Owned clause map

1. **Prepare tensors, active mask, output-domain map and Registry mirror together,
   then pass them to admission.** `CandidateState` carries the staged bank
   tensors/moments, active mask, ordered output domain and Registry mirror delta.
   `stage_vocabulary_extension(...)` seals the complete successor candidate plus
   plan/mirror/resource evidence in the owner-issued staged handoff. Native C07
   requires that exact issued object and publishes its exact candidate through
   B13.
2. **Preserve all old row bytes and optimizer state.** Detached bank staging
   preserves untouched bank objects and copies only a touched bank before row
   initialization. Full-tree staging validates the complete B01 parameter/AdamW
   tree, preserves old parameter/moment bytes and optimizer scalars, and creates
   zero moments/counts for new identity rows. Parameter-extension issuance rejects
   changes to pre-existing optimizer rows. The final issue-specific full witness
   additionally hashes bank-0 weight/m/v before staging, after a simulated
   pre-pointer crash/cold load, and after accepted extension; that witness is the
   remaining expensive gate.
3. **Continue beyond 65535 with uint32 indices and validate bounds.** Existing
   source-replayed planning proves ABI index 65536 maps to bank 8, row 0 without
   aliasing. This qualification adds a direct `UINT32_MAX + 1` rejection witness
   at `BAMF_VOCABULARY_UINT32_EXHAUSTED`.
4. **Full output logits are ordered active-bank projections, never modulo
   aliases.** `staged_tied_logits(...)` walks the globally ordered active ABI,
   selects exact bank/row addresses and concatenates only active projections.
   Boundary coverage includes 8191/8192 and proves an inactive row cannot enter
   the competing output domain.

## Admission-time resource repair

Current reconciliation found one real production gap not closed by the historical
staging proof. A02 measured live free space at staging and sealed a conservative
requirement containing the unchanged 100 GiB reserve, additional planning space
and complete-checkpoint lower bound, but C07 did not consume that requirement
again immediately before first publication. Free space could therefore shrink
between staging and commit while generic B13 write headroom still passed.

Head `4f5972b1` closes that seam:

- C07 first validates the exact owner-issued A02 handoff and all accepted
  parent/runtime anchors.
- After exact accepted-retry detection, but before the first successor Factory or
  B13 persistent write, it validates the sealed resource record against the A02
  receipt and re-reads live free space.
- If current free space is below the sealed
  `required_available_bytes_lower_bound`, publication fails closed with
  `BAMF_VOCABULARY_ADMISSION_DISK_BUDGET_EXCEEDED`.
- Exact already-accepted retries deliberately bypass this live-space gate and
  reuse the accepted pointer, preserving retry convergence after the commit
  already exists.

The regression proves insufficient current space fails before the successor
Factory artifact exists and before B13 publication is called.

## Current verification

```text
A02 semantic planning/factors/resources/staging/transaction: 14 tests PASS; 2 opt-in skips
A02 staged-handoff / generic-publication boundary:             4 tests PASS; 1 opt-in skip
C07 executor/publication/composed retry ring:                  8 tests PASS
C07 persisted-lease policy ring:                               6 tests PASS
focused integrated total:                                     32 tests PASS; 3 opt-in skips

error-control:                         PASS, new debt 0
changed-file smell audit at 4f5972b1: 0 findings
development structure/governance:     PASS
docs check:                            PASS
git diff --check:                      PASS
```

No live learner, shared AdamW update, or neural training workload was started by
this qualification.

## Remaining exact gates

The issue-specific disposable full-topology witness is intentionally detached
because constructing and validating the complete B01 state is expensive. It
must prove, in one real composed path:

1. real accepted B13 generation zero;
2. real `stage_vocabulary_extension(...)` owner issuance;
3. a simulated failure immediately before B13 pointer publication;
4. cold readback still at the exact old generation and bank extent with identical
   old bank weight/m/v hashes;
5. retry through live C07/B13 publication of the exact staged handoff;
6. accepted generation 1 has the expanded bank extent, identical old bank
   weight/m/v hashes, and zero new-row moments;
7. accepted Factory authority resolves to the C07-bound successor.

After that witness passes, a fresh independent exact-head review must inspect the
complete #400 candidate before normal human-review PR turn-in. This issue does
not authorize self-merge.

### Detached witness resource receipt

The first real full-topology composition attempt that reached the current
production staging path, detached witness v3, failed before staging with
`BAMF_VOCABULARY_DISK_STAGING_BUDGET_EXCEEDED`. The host had approximately
131.2 GiB free at the time, which is below the A02 requirement after combining
the unchanged 100 GiB reserve, the 30 GiB planning allowance and the complete
checkpoint lower bound. The detached runner recorded `source_mutated: false`;
the failure is therefore retained as positive evidence that production staging
fails closed on real insufficient capacity, not as a semantic acceptance
failure.

The replacement full witness supplies an explicitly ample disposable observed
capacity only inside the test environment so it can exercise neural-state,
crash/pointer and retry semantics independently of host disk pressure. Observed
free bytes and the derived `fits` boolean are deliberately excluded from the
sealed resource requirement identity; the sealed requirement itself remains
unchanged and is still revalidated by C07 before first persistence. The tracked
low-space regression separately proves that real insufficient admission
headroom fails before successor Factory or B13 persistence.
