# A02.2 capacity-expansion integration qualification — 2026-11-09

Issue #400. Lane A branch `codex/bamf02-a-semantics`.

Reviewed unified consumed at final qualification:
`516725b6170f258ad86b0c5d4ca050907238e59d`.

Current remotely verified post-merge candidate head:
`8b3f071215b27b98f8ae15a9d0b02fc72b7fc80d`.

Status: **READY_FOR_HUMAN_REVIEW**.

Human-review PR: **#952** into
`codex/bamf-unified-base-20261028`. No self-merge is authorized.

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
   pre-pointer crash/cold load, and after accepted extension.
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

## Generation-zero capacity-ownership repair

Detached witness v4 reached the real B13 pre-pointer crash but then exposed a
second production defect: generation zero had already allocated every bank named
by the complete A01 ABI snapshot, including banks containing only inactive future
identities. With an inactive identity at ABI index 8192, generation zero therefore
started with two physical banks and A02 could only activate an existing row; it
could not exercise the issue-owned capacity-expansion transition.

That behavior contradicted the BAMF-0.2 identity contract: the ABI namespace is
append-only, but physical semantic-bank capacity is generation-scoped; a fresh
lineage starts with the minimum capacity needed by its accepted active ABI and
additional 8192-row banks are allocated at accepted admission boundaries.

Head `09b3b7df` repairs generation-zero ownership by deriving initial
`semantic_bank_count` from the highest **active** ABI bank, with a minimum of
one bank, instead of from the complete source ABI census. The source snapshot and
stable future ABI indices remain unchanged; only unadmitted neural capacity is
deferred until A02 admission.

A direct owner-sidecar regression uses a two-bank source ABI with only index 0
active. It failed before the repair with generation-zero bank count 2 and now
proves generation zero exposes exactly one bank and one `bank:0` identity.
The widened post-repair ring passed 29 generation-zero/feature-authority tests,
8 cold-resume tests, 8 C07 adoption tests and 6 persisted-lease policy tests.

## Current verification

```text
A02 semantic planning/factors/resources/staging/transaction: 14 PASS; 2 opt-in skips
generation-zero / feature authority + cold resume:           38 PASS
C07 executor/publication/composed retry + lease policy:      14 PASS
post-merge full-topology A02 -> C07/B13 witness v6:           1 PASS in 633.718s

error-control:                     PASS, new debt 0
changed-file smell audit:          0 findings
development structure/governance: PASS
flow-control tests:                15/15 PASS
BAMF exact issue mirrors:          43/43 PASS
docs check:                        PASS
git diff --check:                  PASS
```

No live learner, shared AdamW update, or neural training workload was started by
this qualification.

## Full composed proof

The issue-specific disposable full-topology witness is intentionally detached
because constructing and validating the complete B01 state is expensive. The
post-merge v6 run proves, in one real composed path:

1. real accepted B13 generation zero;
2. real `stage_vocabulary_extension(...)` owner issuance;
3. a simulated failure immediately before B13 pointer publication;
4. cold readback still at the exact old generation and bank extent with identical
   old bank weight/m/v hashes;
5. retry through live C07/B13 publication of the exact staged handoff;
6. accepted generation 1 has the expanded bank extent, identical old bank
   weight/m/v hashes, and zero new-row moments;
7. accepted Factory authority resolves to the C07-bound successor.

Detached v6 ran from immutable snapshot
`eed6f34fbf7b1eac9b1265def50dbd8f8e3c8ee169592cdc306e40e5a847558f`
after conflict-free synchronization with reviewed unified `516725b6`. It
returned `status: PASS`, `command_returncode: 0`,
`source_mutated: false`, and `Ran 1 test in 633.718s — OK`. Its real A02
staging receipt records `previous_bank_count: 1`,
`next_bank_count: 2`, and allocation of ABI index 8192 to bank 1 row 0.

A fresh independent exact-head review remains required before normal
human-review PR turn-in. This issue does not authorize self-merge.

## Independent exact-head review

Fresh independent review of evidence head
`7011f83d74b31c925f2ad9f9695671b5d88d7348` over post-merge semantic head
`8b3f071215b27b98f8ae15a9d0b02fc72b7fc80d` returned:

`0 Blockers / 0 Majors / 0 Nits; PASS; READY_FOR_HUMAN_REVIEW`.

The reviewer confirmed that `8b3f..7011` is evidence/flow bookkeeping only,
that v6 closes the prior evidence-only Major, and that the sole A02-owned
post-merge overlap preserves B09 `mode_transition` authority exactly. No
remaining semantic, retry, capacity, tensor-custody, uint32, projection, or
full-witness defect was identified.

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

Detached witness v4 then reached the intended B13 pre-pointer crash. Its
post-crash cold read correctly followed the accepted generation-zero pointer, but
that generation still reported two banks because the then-current genesis owner
preallocated all ABI banks. This was not a witness-only mismatch: it exposed the
generation-zero capacity-ownership defect repaired at `09b3b7df`. The next
detached witness therefore exercises the repaired real one-bank -> two-bank
transition rather than weakening the expected old extent.

Detached witness v5 then passed the repaired one-bank -> two-bank path before
the final reviewed-unified synchronization. After reviewed unified advanced to
`516725b6`, Lane A merged that head conflict-free. The only overlapping A02
successor-policy change preserved B09's accepted `mode_transition` field.
Detached witness v6 reran the complete proof on that post-merge tree and passed
without source mutation, making v6 the final runtime receipt for turn-in.
