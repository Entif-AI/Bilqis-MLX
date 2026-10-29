# B07.3 candidate-only motif allocation transaction

Issue: [#458](https://github.com/Entif-AI/Bilqis-MLX/issues/458)
Lane: B, isolated single-writer candidate `codex/bamf02-b07-transaction-20261029`
Consumed Lane B: `7b70b0d4f70c2df7d79ddd69db91a2eaf1da78ae`
Consumed reviewed unified: `7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4`
Direct prerequisite: B07.2/#457 scoped candidate intake `84a10e9`;
source/accepted-generation custody still pending.

## Scoped software

`learning/atlas_engram.py` extends the existing deterministic motif
planner with optional parent-observed usage counters and pending keys.
Structural-before-exact allocation still respects the same 64-slot
candidate limit and page-growth resource contract. Cumulative counts
determine future allocation priority without changing the parent.
Pending full canonical keys survive candidate boundaries and can be
allocated later even without re-observation. No hash-only match or
slot reassignment is introduced.

`learning/atlas_engram_transaction.py` introduces a frozen
`MotifAllocationSnapshot` of manifest, cumulative allocation counts,
pending keys and explicit source-attested alias *artifacts*. It
constructs `CandidateMotifSnapshot` copy-on-write, binding the exact
parent digest and source-derived plan. `verify_candidate_motif_snapshot`
replays the entire proposal from its parent, source frames, budget and
explicit alias artifacts. A changed counter, slot, parent or alias
cannot pass replay. An alias never rewrites an old key or slot, and a
new alias target must exist in the candidate manifest.

This is **candidate preparation and verification, not acceptance**.
Only the B13/C retained-generation owner may stage and atomically
publish a candidate together with its tensor pages, AdamW moments,
source/rights frontier and retained-learning acceptance. A
source-attestation digest on an alias is not by itself proof of
semantic equivalence; that evidence must be verified by its owner
before the generation may accept the alias.

## Verification

```
python3 -B scripts/run_tests.py \
  bilqis_mlx/learning/tests/test_atlas_engram_allocation.py \
  bilqis_mlx/learning/tests/test_atlas_engram_parameters.py \
  bilqis_mlx/runtime/tests/test_model_topology_v2.py
```

**49 total, 47 passed, 0 failed, 2 existing optional skips.**
New owner tests cover rejection leaving parent slots/counters intact,
deterministic replay, cumulative use priority, pending keys surviving
without re-observation, forged candidate/parent rejection, explicit
alias artifact boundaries, page-growth preservation of every old slot
and counter, and full-capacity fallback. Existing B07
hash-collision, page-growth, seeded-row, B01 ledger and B07.4
parameter-sharing tests remain green. `git diff --check` passes;
error-control-plane inspection found no new B07 findings.

## Disposition

**SCOPED_EGM_PASS_SOURCE_AND_RETAINED_COMMIT_PENDING.**
Independent Goldfish review at immutable pushed
`242972c99bbac7f65dbe1d3f524c11bac5c6797c`
returned **EGM PASS, zero Blockers/Majors** for candidate
preparation/replay. The reviewer inspected source, tests and exact
Git objects but did not independently execute the tests; the
47-pass/2-optional-skip counts are prime execution evidence.
The review expressly did not grant source-equivalence or B13/C
retained-generation acceptance.

No accepted-generation pointer, model/optimizer state, source release,
teacher, live student or training run was changed. B07.1/.2 source
authority and the B13/C atomic retained-generation boundary must
qualify this proposal before any publication. The parent B07 issue
and unified integration remain open.
