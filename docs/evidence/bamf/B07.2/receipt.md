# B07.2 | Candidate-only motif page growth and seeded rows

- Issue: #457; parent B07 #356; Lane B.
- Isolated branch: `codex/bamf02-b07-pages-candidate-20261029`.
- Source candidate: B07.1 `5fab1ec`.
- Reviewed unified consumed: `6b5460032fc0b19115843cce95fe8be9582af141`.
- Candidate base merge: `590c1cb`.
- Independent EGM: **PASS**, scoped to B07.2 planner/page growth
  at immutable `39554896decaf66821e69f632e3e656acc500556`.
- Shared Lane B push and integration: **NOT PERFORMED**.

## Implemented bounded contract

The immutable B07 motif planner can add **one** 16,384-row page
when the candidate's requested new slots would exhaust the
existing page and its explicit resource budget covers the
minimum **25,165,824 FP32 state bytes** for weights and AdamW
first/second moments. It never exceeds four pages or 65,536
slots. Without budget, the accepted parent stays untouched,
unallocated keys remain pending, and the miss retains the
`FACTORIZED_FALLBACK` disposition. A partial last page can
fill and trigger the next page in the same candidate.

The new `bilqis.motif-page-growth/v1` record captures parent
capacity, candidate capacity, page count, reserved state bytes
and declared budget. The candidate-view schema advances to
`bilqis.motif-candidate-view/v2` while the B07.1 motif-key,
manifest and allocation-plan v1 schemas remain unchanged.
`candidate_motif_manifest` builds an immutable candidate
without publishing or mutating the parent; it rejects a
foreign parent, noncontiguous new slots or fabricated
unneeded growth.

`initialize_planned_motif_slot` consumes B01's exact
`ModelTopologySpecV2`, `GenerationExtents`,
`expected_bamf_shapes` and `initialize_bamf_row` for
the declared `motif.page.N` tensor. The seeded FP32
128-channel vector depends on the full canonical key digest,
run seed and page parameter name. No second parameter
registry, trainable allocation during forward, optimizer
write or acceptance transition was introduced. Full-key
comparison after bucket lookup remains enforced by B07.1.

## Verification

Owner `test_atlas_engram_allocation.py`: **17 passed,
0 failed, 0 skipped**
including original B07.1 exact/structural collision tests,
full-page and mid-candidate growth, insufficient resource
fallback, max-four-page validation, parent immutability,
candidate parent binding and B01 seeded-vector byte digest.
Adjacent B01 `test_model_topology_v2.py`: **18 passed,
0 failed, 2 optional large/historical witnesses skipped**.
Combined **35 passed, 0 failed, 2 skipped**.
`git diff --check`: passed. Static error-control and module-size
checks retain inherited findings, with no new finding in
`atlas_engram.py`.

## Deliberate integration boundaries

This is a **staged local implementation candidate**, not
an accepted B07.2 release. B07.1 still requires real
A03/A13 source-grant admission through reviewed unified;
B07.3 owns atomic publication, optimizer moments, rejected
candidate rollback and cold resume; B07.4 owns both gated
motif read sites and miss-equivalence proof. The resource
number here is a minimum state-byte reservation, not
proof that B13's full checkpoint/disk reserve has been
authorized. No live student or optimizer was started.

## Independent review result

Fresh Goldfish reviewed immutable `3955489` against pinned
EGM `b3a35956759bf7f024af2ff061b2e0b44b438e4c`
and returned **B07.2 scoped EGM PASS, zero Blockers/Majors**.
The reviewer independently executed the owner 17/17
and adjacent B01 18 pass/2 optional skips, plus a
72-case capacity/budget adversary spanning all four
capacity tiers, zero/one/64 free slots and requested
slots, and exact 25,165,823/25,165,824-byte thresholds.
No source admission, B07.3 publication, B07.4 tensor
custody or Lane B integration was inferred from this PASS.
