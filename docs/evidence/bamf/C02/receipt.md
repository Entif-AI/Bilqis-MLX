# C02 | Completion receipt

`issue_key`: C02 / #371
`lane`: C
`reviewed_integration_base`: `53eba37e5c9dd6ad065b1980fa4850c484aaa624`
`implementation_head`: `0a5d0343085a4e18cd64bf00fe25e74eb76f5cac`
`feature_branch`: `codex/bamf02-c02-371-postmerge-20261107`
`prior_turn_in_pr`: #893, externally merged as
`53eba37e5c9dd6ad065b1980fa4850c484aaa624`

## Consumed authority and dependencies

- Reviewed unified baseline `53eba37e5c9dd6ad065b1980fa4850c484aaa624`
  is the actual PR #893 merge result and direct parent of the post-merge repair
  implementation head; no `main` or sibling lane branch was merged directly.
- C02.1 #490 exact accepted PR #884 head
  `2d8993c7aa654378b13ce9e14e7f0bf0986083b4`, merged to unified as
  `aef69dae9179bb09f85f955b8a494f6582eac942`, is an ancestor of this branch.
- C02.2 #491 accepted head `b9b38e2ddb64121bbaa24f0a06004e1951d58087`,
  C02.3 #492 accepted head `1920f6c931237022c5aebc56ee787891173e228b`,
  and C02.4 #493 accepted head `98c6e43cea16130cf240c14ad293e8c6f8d82088`
  are consumed through the reviewed unified chain.
- Direct owner contracts A05 #357, A06 #352, B10 #367, B11 #369, C01 #347 and
  A13 #354 are consumed from the same reviewed unified baseline plus the exact
  C02.1 repair above. Open/stale issue labels were not treated as authority over
  exact merged code receipts.
- C08 resource owner is parent #374 / C08.1 #513. #333 remains the teacher
  observation owner. C16 retains live durable learner-start authority.
- The operator runtime lineage for later C16 work is
  `/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`.
  It was inspected read-only at generation 24254. C02 did not mutate or resume it,
  and historical Prometheus trainer evidence is non-authoritative for adaptation
  and is not a BAMF activation path.

## Changed paths

Implementation changes relative to reviewed unified touch:

- `bilqis_mlx/learning/_teaching/student_ops.py`
- `bilqis_mlx/runtime/_batch/atlas_training_adapter.py`
- `bilqis_mlx/runtime/_batch/atlas_training_contracts.py`
- `bilqis_mlx/runtime/_batch/batch_training_authority.py`
- `bilqis_mlx/runtime/_batch/factory_candidate_training.py`
- `bilqis_mlx/runtime/_batch/factory_training_bridge.py`
- `bilqis_mlx/runtime/_batch/factory_training_context.py`
- `bilqis_mlx/runtime/_batch/training_input_authority.py`
- `bilqis_mlx/runtime/_batch/training_request.py`
- `bilqis_mlx/runtime/_capability/factory_task_authority.py`
- `bilqis_mlx/runtime/_capability/task_goal_readout.py`
- `bilqis_mlx/runtime/_model/atlas_training_authority.py`
- `bilqis_mlx/runtime/_model/cache/atlas_cache_eligibility.py`
- `bilqis_mlx/runtime/_model/cache/atlas_cache_runtime.py`
- `bilqis_mlx/runtime/_source/source_execution.py`
- `bilqis_mlx/semantics/atlas_features/formal.py`
- `bilqis_mlx/source_adapters/_task_goals/answer_choice_task_goal.py`
- `bilqis_mlx/source_adapters/_task_goals/numeric_task_goal.py`
- `bilqis_mlx/source_adapters/_task_goals/task_goal_registry.py`
- affected package-local behavior regressions under
  `bilqis_mlx/runtime/tests/` and `bilqis_mlx/learning/source_atoms/tests/`.

The post-merge repair relative to
`53eba37e5c9dd6ad065b1980fa4850c484aaa624` changes only:

- `bilqis_mlx/runtime/_batch/factory_candidate_training.py`
- `bilqis_mlx/runtime/tests/batch/test_factory_training_bridge.py`
- this C02 evidence successor.

The repair removes caller-supplied optimizer decay authority. B12/B01 now owns
decay derivation exclusively through
`reconcile_b01_optimizer_manifest(...)` inside the candidate transaction.

## Source and topology bindings

- Exact A01 artifact fixture mounted for real MLX proof:
  `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`.
- Default `ModelTopologySpecV2` digest used by the parent witness:
  `4ea0a04087596dc243a667ed17138ff0ffb3df8b4339759ddf533cdad7e0bd96`.
- Factory delivery identity binds release SHA-256, delivered-content SHA-256,
  capability, row content SHA-256, stable source-family ID, episode ID, requested
  and delivered counts, teacher strategy, rehearsal provenance and optimizer-step
  seed. B11 generation binding is rederived from the accepted parent's actual
  retained parameters/topology/extents before the candidate step.
- B10 route truth is training-only source authority. Model input receives the
  gold-blind TaskGoal; the registered source lowerer resolves its own route hole,
  then the canonical readout owner projects that resolution to exact
  `OPERATOR`/`OPERAND` decision targets.

## Verification

Exact CPU command:

```bash
/Users/cr8s/Code/bilqis-skos-19/.venv/bin/python -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/batch/test_atlas_training_adapter.py \
  bilqis_mlx/runtime/tests/batch/test_atlas_training_compilation.py \
  bilqis_mlx/runtime/tests/batch/test_atlas_training_delivery.py
```

**29 passed, 0 failed, 0 skipped, 0 errors.**

Exact detached Studio command and fixture are recorded in
`docs/evidence/bamf/C02/egm.md`. Result: **12 passed, 0 failed, 0 skipped, 0
errors**, with source snapshot unchanged. Current receipt:
`/Users/emilie/Code/371-c02-complete-20261106/.local/c02-371-postmerge-repair-proof/receipt.json`.

Repository gates: BAMF flow-control OK; **43/43** issue mirrors and **214**
owner/child identities/fingerprints verified; changed-file smell audit **0
findings**; `git diff --check` clean.

The immediately preceding detached witness on merged PR #893 head
`3e959177314fbd43def41547fd34a1e1701c8909` is intentionally retained as
failure evidence: **11 passed / 1 error**, `source_mutated=false`, failing only
because C02 supplied the B12.4-removed `decay` keyword. Incident
`PM-2026-11-07-003` records that post-merge integration defect.

## Observed outcome and remaining boundary

Current A/B/C Factory rows compile and score through the one BAMF adapter/B11
backend. Inference does not receive target fields. Stale release/generation and
source/frame substitution are rejected. Grade permutations preserve behavior;
domain changes alter released rule coverage without a grade branch. Known source
siblings remain siblings across different draw seeds and cannot be admitted as
independent evidence. A source-owned arithmetic operator hole produces canonical
B10 `OPERATOR` training supervision. A real disposable accepted generation can
execute `student_ops -> C02 -> C08 -> B10/B11 -> candidate custody -> #333`,
producing one finite speculative optimizer step and realized row/cost evidence
without publishing the candidate.

The deliberate remaining boundary is downstream C08/B12 multi-microbatch
gradient-tree accumulation. C02 consumes C08 planning and fails closed before
neural execution when a logical batch requires more than the currently admitted
one-group B11 witness. This is not a C02 dependency: C08 depends on C02+B11 and
owns weighted logical-batch accumulation before one B12 AdamW step. C02 does not
counterfeit that owner or perform one AdamW step per microbatch. Live learner
start and sustained iteration remain human/C16-owned.

## EGM

Report: `docs/evidence/bamf/C02/egm.md`. Round 1 failed on the production seams
listed there; all C02-owned Blocker/Major findings received concrete repairs.
Fresh pre-merge round-2 review on exact candidate `f9f87d8b...` passed both
personas at **0 Blockers / 0 Majors / 0 Nits**. That review was invalidated for
merge-readiness when the feature head/base changed. The merged result then
exposed the B12.4 call-boundary failure described above. The current post-merge
repair is therefore held at `EGM-Pending` until a genuinely fresh
whole-candidate review binds to the final repair/evidence head.

`next_ready_issue`: none claimed by C02; the post-merge repair turns in to the
reviewed unified trunk only after independent merge-readiness acceptance. No
self-merge, manual issue closure, `main` mutation or live learner start is
authorized here.
