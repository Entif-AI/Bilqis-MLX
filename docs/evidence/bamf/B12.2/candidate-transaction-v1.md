# B12.2 in-memory candidate custody

Issue #475 remains open. This provisional slice composes existing AdamW,
B07 motif snapshots and B09 plasticity policy into one in-memory candidate.
The issue branch starts from Lane B and unified
`9104ce733e04fb9c82420428b18dfdbf5db49535`. No sibling branch is consumed.

## Behavior and ownership

`learning/_retention/atlas_candidate.py` holds `CandidateState` and
`CandidateTransaction` under explicit provisional-v1 schema identities.
`begin_candidate` stages deterministic motif observations/pending keys through
B07's existing snapshot constructor. The motif manifest and aliases must stay
unchanged: slot allocation/page growth require materialized parameter rows and
remain blocked in this slice.

`candidate_step` validates the transaction, delegates supplied masks and FP32
gradients to B12's existing mask-before-global-clip/native AdamW owner, and
increments the speculative optimizer step only when that owner produces an
update. Each step has its own mask. Participating zero gradients still count;
no-loss and wholly frozen steps preserve the candidate object.

`resolve_candidate(accepted=False)` returns the exact parent, including its
weights, moments, counts, motif snapshot, establishment ages, optimizer step
and FAST/FULL counter. An accepted nonempty candidate returns all components
in one `CandidateState`. Establishment ages derive from the changed local
counts and advance once per accepted candidate. B09's existing policy owns
the cadence: eight accepted FAST candidates make FULL due; rejected FULL
remains due; accepted scheduled or teacher-requested FULL resets the counter.
Teacher observations and retention decisions stay with their existing owners.

Transactions are process-local handles issued only by `begin_candidate` and
`candidate_step`. Public construction and `dataclasses.replace` fail closed;
the handle carries a private owner-issuance marker checked at each transition.
This is an internal Python API contract, not a sandbox against arbitrary code
that mutates private module internals. It is not a serializable B13 receipt.

There is no production caller or durable publication. Execution-derived masks,
B01 complete-tree binding, newly activated row initialization, motif slot/page
materialization, B11 differentiation, source admission, B13 serialization and
accepted-generation pointer/outbox publication remain open. The provisional
API cannot be used as evidence that #475 or parent B12 is complete.

## Structural interruption

While tracing B07, the inherited 584-line motif-allocation test file triggered
the repository's mandatory structure rule. Commit `6741be88` moves its source
fixtures and three test classes into `_engram/tests/` alongside the existing
motif owners. All 25 test-method ASTs are identical and occur exactly once.
All 25 pass before and after; replacement files contain 100/114/208/163 lines.
No production definition or historical source/policy epoch changes.

## Reproduce

Use native MLX and run through the finite validation runner:

```sh
node ~/.codex/hooks/validation-output-runner.mjs -- python3 -B scripts/run_tests.py \
  bilqis_mlx/learning/_retention/tests/test_atlas_candidate.py \
  bilqis_mlx/learning/_engram/tests/test_atlas_engram_keys.py \
  bilqis_mlx/learning/_engram/tests/test_atlas_engram_preparation.py \
  bilqis_mlx/learning/_engram/tests/test_atlas_engram_transaction.py
```

The red run fails because the candidate module does not exist. The first green
run passes all eight candidate tests. They cover two-step rejection/acceptance,
changing masks, zero-gradient participation, no-loss/frozen identity, once-per-
candidate ages, scheduled/teacher FULL, FOUNDATION, malformed state/decisions
and rejection of unmaterialized motif allocations. Review and final validation
receipts are in `egm.md` and `validation.md` in this directory.

IPR-0220 remains open. Existing PM-2026-10-29-006 parent-identity controls apply.
Disposable tests do not measure learning or retention. No durable student,
matching AdamW, teacher, champion, original checkpoint or human-run is changed.
Human review/integration and persistent neural initiation remain separate.
