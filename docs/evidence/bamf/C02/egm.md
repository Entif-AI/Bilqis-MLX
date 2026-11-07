# C02 | EGM review and repair record

Issue [#371](https://github.com/Entif-AI/Bilqis-MLX/issues/371). Lane C.
Pinned Google EGM: `b3a35956759bf7f024af2ff061b2e0b44b438e4c`.

## Round 1 | exact behavior head `eb486d0125e92ad59d8532e4f0657f4c3d080773`

Fresh read-only `codebase-details` and `comprehension` Goldfish reviewed the
whole candidate against the C02 contract and implementation-readiness standard.
Disposition: **FAIL, 3 Blockers / 5 Majors / 1 Nit.** No reviewer mutated source
or ran tests.

The material findings were:

1. The C02 Factory bridge had no ordinary production BAMF learner consumer; the
   historical visit path still called legacy `_train_step` directly.
2. Fallback `source_family_id` included the draw seed, so siblings from one
   declared source family could appear independent.
3. Structured B10 target authority was caller-substitutable and omitted the
   canonical `OPERATOR` / `OPERAND` route kinds.
4. C08 resource planning was represented only by provisional/test callbacks,
   not consumed by the production composition seam.
5. Realized delivery/cost evidence was not connected from the candidate training
   transaction into #333 observation capture.
6. Turn-in evidence omitted the exact executable Studio command, fixture binding,
   changed-path/dependency attribution, source/topology bindings and remaining
   continuation boundary. C08 was also referenced without its concrete owner
   links ([#374](https://github.com/Entif-AI/Bilqis-MLX/issues/374),
   [#513](https://github.com/Entif-AI/Bilqis-MLX/issues/513)).

## Repair

Repair commits:

- `96e443d44e8a089fc20429e9b888a2789e6556cb` — compose the successor-only
  production training transaction and repair source/B10/C08/#333 authority.
- `daaabc2872d4da624f34c22c1a842c20cee7a508` — correct the numeric construction
  witness to the source owner's legal `each >= 3` scope and export the resolver.
- `dc67a3c8d2d6edbf9ca63dcd6ed105d9fed4909c` — bind C02 compilation to the
  actual `ModelTopologySpecV2`, pass the accepted candidate topology through the
  Factory bridge, and enforce `input positions + maximum decisions <= topology.context`.

The repaired production seam is explicit and dormant: `student_ops` exposes
`train_bamf_factory_step`. The stale historical Prometheus trainer is not an
activation path for BAMF and is not used by this C02 transaction. The BAMF path
authenticates the accepted parent, compiles one exact
source-owned Factory delivery, derives stable family/episode identity, resolves
training-only B10 route truth through the registered source TaskGoal lowerer,
uses the canonical B10 `OPERATOR`/`OPERAND` decisions, derives measured A05 frame
statistics into C08 `ResourceRow`/`MemoryBudget`/`BatchPlan`, executes one B11
gradient, admits one speculative candidate optimizer step through existing B13
custody, and immediately records exact delivered rows plus realized cost through
#333 observation capture. It publishes no candidate and starts no live learner.

C08 split-gradient accumulation remains a downstream owner boundary. C02's own
acceptance separately proves plural Factory-row compilation/identity preservation
and a finite disposable MLX gradient step. C08 depends on C02+B11 and owns the
stronger one-logical-batch -> weighted microbatch accumulation -> one B12 AdamW
step contract. Until that downstream C08/B12 integration exists, C02 fails closed
instead of fabricating multirow optimizer custody. Live durable launch/iteration
remains C16 operator authority.

## Round 2 | pre-merge disposition

Fresh pinned `codebase-details` and `comprehension` Goldfish reviewed exact
candidate `f9f87d8b613a128d672cfbb6ca7c15dc4b839f90` against reviewed unified
`3899649586b105b075e92f0ee3c51e80c379b473`. Both returned **PASS, 0
Blockers / 0 Majors / 0 Nits**. That disposition authorized turn-in only. It
did not authorize self-merge.

PR #893 was later updated to consume reviewed unified
`db7fd553a2e5deac65574851a16f34e8303a1b90` plus the changed-file hygiene
repair, producing feature head
`3e959177314fbd43def41547fd34a1e1701c8909`. Because that exact head/base pair
differed from the reviewed pair, #371 was correctly returned to `EGM-Pending`
before the new Studio witness completed.

## Post-merge integration correction

PR #893 was externally merged into the reviewed unified trunk as
`53eba37e5c9dd6ad065b1980fa4850c484aaa624` while the detached exact-head
Studio proof for `3e959177...` was still running. The merge is historical
state, not acceptance evidence.

That detached witness failed **11 passed / 1 error** with
`source_mutated=false`. The only failing predicate was the real production
candidate step:

`TypeError: admit_uninterrupted_candidate_step() got an unexpected keyword argument 'decay'`.

B12.4 had intentionally moved weight-decay authority into
`reconcile_b01_optimizer_manifest(...)` inside the candidate transaction.
C02 still carried the obsolete caller-supplied `decay` argument. The
post-merge repair therefore removed that duplicate authority instead of adding
a compatibility shim.

Repair branch:
`codex/bamf02-c02-371-postmerge-20261107`.

Exact repair implementation head:
`0a5d0343085a4e18cd64bf00fe25e74eb76f5cac`.

The exact previously failing Studio test then passed **1/1**. The complete
detached acceptance proof on the same repair head passed **12/12**, zero
skips/errors, return code 0, with
`source_mutated=false`.

Detached repair receipt:
`/Users/emilie/Code/371-c02-complete-20261106/.local/c02-371-postmerge-repair-proof/receipt.json`.

Detached repair snapshot SHA-256:
`9d26c9def8fcff4cdabc18172770b1713fe42ea99803846f667204faa24265b3`.

The failure and containment are also preserved as
`PM-2026-11-07-003` in the canonical Entif Post-Mortem Ledger. #371 remains
open and `EGM-Pending` until a fresh whole-candidate review binds to the final
post-merge repair/evidence head.

## Exact repair proof

CPU authority proof remains valid on the post-merge repair implementation head
`0a5d0343085a4e18cd64bf00fe25e74eb76f5cac`: the repair changes only the
obsolete optimizer-authority call boundary and its direct tests.

```bash
/Users/cr8s/Code/bilqis-skos-19/.venv/bin/python -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/batch/test_atlas_training_adapter.py \
  bilqis_mlx/runtime/tests/batch/test_atlas_training_compilation.py \
  bilqis_mlx/runtime/tests/batch/test_atlas_training_delivery.py
```

Result: **29 passed, 0 failed, 0 skipped, 0 errors**.

Deterministic repository gates:

```bash
python3 -B scripts/check_bamf_flow_control.py
python3 -B scripts/verify_bamf_0_2_contracts.py
python3 -B scripts/code_smell_audit.py \
  --changed-from 53eba37e5c9dd6ad065b1980fa4850c484aaa624 \
  --check-baseline docs/evidence/development/code_smell_baseline.json
git diff --check 53eba37e5c9dd6ad065b1980fa4850c484aaa624..HEAD
```

Results: `BAMF_FLOW_CONTROL_OK`; **43/43** checked-in issue mirrors and **214**
owner/child identities/fingerprints verified; changed-file smell audit **0
findings**; diff check clean.

Mac Studio repair proof used the repository detached-runner snapshot, with the
accepted A01 artifact fixture mounted explicitly:

```bash
/usr/bin/env \
  BILQIS_A01_ATLAS_BUNDLE=/Users/emilie/Code/371-c02-complete-20261106/.local/c02-a01-rebuild/5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7 \
  /usr/local/bin/python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/batch/test_factory_training_bridge.py \
  bilqis_mlx/runtime/tests/capability/factory/test_task_goal_readout.py
```

Current detached exact-head receipt:
`/Users/emilie/Code/371-c02-complete-20261106/.local/c02-371-postmerge-repair-proof/receipt.json`.
Result: **12 passed, 0 failed, 0 skipped, 0 errors**, return code 0. Snapshot
SHA-256 `9d26c9def8fcff4cdabc18172770b1713fe42ea99803846f667204faa24265b3`
was unchanged after execution (`source_mutated=false`).

## Runtime lineage clarification

The operator runtime lineage relevant to later C16 activation is the existing
read-only run:

`/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`

Its current `state.json` reports generation **24254**, node
`4b7c27690474b2ac48b90a74dcbe8cbb3e66da4681d5a898ea128117e63335cc`,
receipt
`5a9f680246b5f073e5aa387d8cacfe4e3a67e21fe1bb308f92dc4af7436e1895`.
C02 did not mutate, resume, or train that run. The disposable exact-head proof
above remains isolated. No Prometheus trainer path is part of this handoff.

The next review is a fresh whole-candidate re-audit of the post-merge repair
plus this evidence successor. Its final disposition is recorded in the
issue/repair-PR receipt only after independent reviewers return; no
Blocker/Major is silently waived.
