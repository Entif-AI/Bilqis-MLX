# C04 completion receipt — 2026-11-07

- issue_key: C04 / #373
- implementing children: #498, #499, #500
- lane: C / runtime-integration
- closeout branch: `codex/bamf02-c04-373-20261107`
- consumed reviewed-unified SHA: `58eb36bba1958e0b3ca5d6aa3080260ccac3e9a1`
- C04 implementation ancestor: `5daee1284bbce7461a104e2dfdadc0d646504daf`
- C02 requalification ancestor: `cc94a04a3959d6ab0546bb6b55e9d387b3b853c1`
- production-authority / solver proof ancestor: `aeeba85e7ff06a671d92bbb3d161bc963d96b470`
- protected authority: referenced by identifier only; no protected contents copied
- neural_training_started: false
- live_student_mutated: false
- self_merge_authorized: false

## Changed paths

- `docs/evidence/bamf/C04/parent-acceptance.md`
- `docs/evidence/bamf/C04/receipt.md`
- `docs/evidence/bamf/C04/egm.md` after fresh review

No production code change is required: the reviewed C04 implementation is already present on
the consumed unified base. This branch exists to perform the dependency requalification and
turn-in that the historical C04 receipts explicitly deferred.

## Consumed verification evidence

Historical implementation/review evidence:
- C04/C05 reviewed integration cut PR #561: targeted C04/C05 **70/70 PASS** and C04.3 EGM PASS.
- C02 post-merge repair PR #895: detached Studio acceptance **12/12 PASS**,
  CPU C02 authority **29/29 PASS**, source_mutated=false.
- Production-authority remediation PR #809: cognitive solver/replay/import/readout
  **19/19 PASS**; moved semantic core **31 PASS + 1 expected optional integration skip**;
  base-aware quality check PASS; hosted portable-core, portable and semantic-ABI-integrity PASS.

Current-tree source readback confirms:
- exact-first deterministic route ordering;
- TaskGoal/v1 source-lowered bounded DAG ownership;
- one bounded neural proposal plus bounded local refinement;
- deterministic verified fallback / typed unresolved;
- exact full score and replay-safe cost accounting;
- no assessment/gold import in the solver closure;
- literal `ADD(MUL(2,3),4) == 10` with two pure calls;
- live typed TaskGoal readout -> neural proposal -> pure solver route.

## Test command for human/CI replay

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/capability/factory/test_cognitive_solver.py \
  bilqis_mlx/runtime/tests/capability/factory/test_solver_replay.py \
  bilqis_mlx/runtime/tests/capability/factory/test_solver_import_boundaries.py \
  bilqis_mlx/runtime/tests/capability/factory/test_task_goal_readout.py \
  bilqis_mlx/semantics/tests/cognitive_dag
```

This chat execution surface cannot execute the mounted Studio repository inside the mandated
code-execution container, so it does not fabricate a new local test run. The closeout consumes
the exact upstream run receipts above and requires fresh hosted PR checks plus independent
review of this current-tree disposition.

## Observed outcome

C04 is no longer blocked by the upstream conditions named in its historical receipts.
The current reviewed unified tree contains the solver, current exact-operator/DAG authority,
typed neural readout integration, C02 repaired integration boundary, and later
execution-authority remediation. Parent acceptance is therefore satisfied at the software
and integration-contract level.

## Remaining owned defects

None identified in C04-owned scope. Any later retained-learning, persistent-student or
new-capability learning claim remains with its separate owner and is not manufactured here.

## Turn-in rule

The PR must target `codex/bamf-unified-base-20261028`, remain unmerged, and list
`Closes #498`, `Closes #499`, `Closes #500`, and `Closes #373` for human merge.
