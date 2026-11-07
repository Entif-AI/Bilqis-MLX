# C04 parent acceptance requalification — 2026-11-07

Issue: #373  
Children: #498, #499, #500  
Status: **REQUALIFIED_COMPLETE_PENDING_HUMAN_MERGE**  
Reviewed integration target: `codex/bamf-unified-base-20261028`  
Fresh closeout branch base: `58eb36bba1958e0b3ca5d6aa3080260ccac3e9a1`

## Why this is a closeout, not a rewrite

The complete C04 implementation already entered reviewed unified history through PR #561. Its
historical child receipts truthfully remained `IMPLEMENTED_PENDING_UPSTREAM_REQUALIFICATION`
because B06/B10/B11, C02, actual typed readout, and disposable MLX integration evidence were
not yet mature enough to close the parent.

Current unified now contains that implementation plus the later prerequisite realizations and
production-authority repairs. Reimplementing the solver would create a second authority and
violate the issue's reuse/ownership contract. This closeout therefore requalifies the existing
C04 implementation against the current reviewed tree.

## Exact ancestry consumed

- C04 reviewed integration cut: `5daee1284bbce7461a104e2dfdadc0d646504daf`
  (PR #561), ancestor of the closeout base.
- A07 bounded TaskGoal/DAG/operator implementation: `6b7f4daaf89293f5a12a1381e016d01e877128f4`
  with final reviewed receipt `fadbe684140220776f906627a1c4ec28b41ba216`, present in unified.
- C02 exact post-merge repair candidate:
  `cc94a04a3959d6ab0546bb6b55e9d387b3b853c1` (PR #895), ancestor of the
  closeout base. Its detached Studio acceptance was 12/12 and CPU C02 authority 29/29.
- Later execution/custody remediation:
  `aeeba85e7ff06a671d92bbb3d161bc963d96b470` (PR #809), ancestor of the
  closeout base. Its current-head proof included cognitive solver/replay/import/readout
  **19/19 PASS**, moved semantic-core **31 PASS + 1 expected optional skip**, base-aware
  quality checks PASS, and fresh hosted portable / semantic-ABI checks PASS.
- Current reviewed unified base consumed by this closeout:
  `58eb36bba1958e0b3ca5d6aa3080260ccac3e9a1`.

The historical receipts remain historical evidence. This document supersedes only their
pending-upstream disposition.

## Current implementation surfaces inspected

- `bilqis_mlx/runtime/cognitive_solver.py`
- `bilqis_mlx/runtime/cognitive_solver_contracts.py`
- `bilqis_mlx/runtime/_operator/operator_registry.py`
- `bilqis_mlx/semantics/cognitive_dag.py`
- `bilqis_mlx/semantics/_cognitive_dag/{contracts,goals,prepare,execution,topology}.py`
- `bilqis_mlx/semantics/cognitive_operators/`
- `bilqis_mlx/runtime/tests/capability/factory/test_cognitive_solver.py`
- `bilqis_mlx/runtime/tests/capability/factory/test_solver_replay.py`
- `bilqis_mlx/runtime/tests/capability/factory/test_solver_import_boundaries.py`
- `bilqis_mlx/runtime/tests/capability/factory/test_task_goal_readout.py`
- `bilqis_mlx/runtime/tests/capability/test_capability_evaluation.py`
- `bilqis_mlx/runtime/tests/batch/test_factory_training_bridge.py`
- `bilqis_mlx/semantics/tests/cognitive_dag/test_execution.py`
- `bilqis_mlx/semantics/tests/cognitive_dag/test_planning.py`

The physical grouping is the current repository structure; the public import surfaces remain
stable through the runtime/semantics package paths.

## Parent acceptance map

### Exact role / exact operator route

The solver registry orders EXACT before cache, neural, fallback and unresolved.
The current complete-solver witness
`test_fresh_role_fillers_and_two_node_structure_use_actual_source_operators`
exercises fresh `ROLE_LOOKUP` cases through `CompleteSolver` and asserts the role
results. Separately,
`test_applicable_exact_operator_wins_with_full_score_no_neural` verifies exact-first
routing, full score, and zero neural calls. Source/release/generation drift is rejected
before routing.

### Two-operation deterministic composition

The current A07 DAG execution witness
`test_two_node_add_mul_returns_ten_and_counts_compute` executes
`ADD(MUL(2,3),4)`, returns literal **10**, records exactly **2** pure operations,
and proves memo replay separately.

### Neural interpretation followed by a pure operator

The current B10 TaskGoal readout witness
`test_live_decoder_route_becomes_scope_preserving_neural_proposal` converts live typed
decoder output into a source/scope-preserving neural proposal. The same current suite's
`test_fixed_selector_routes_only_source_visible_answer_operand` feeds that typed proposal
through `solve_task` and proves `NEURAL_COMPOSITION` returns the selected legal source-visible
value.

The closeout repair adds
`FactoryTrainingBridgeTests.test_live_b11_proposer_routes_source_binding_into_pure_operator`.
That regression uses a source-owned `A.IDENTITY` Factory row and its
`FactoryTaskAuthority`, constructs the real `b11_task_goal_proposer`, calls the actual
B11 `forward_bamf` path, then requires `solve_task` to execute the selected legal
source-visible Boolean binding through the pure `SELECT_BOOLEAN` operator with exactly
one neural call and one pure operation. It does not force logits or consult evaluator gold.
C04 therefore exercises the actual B11 proposer seam without adding a second neural executor.

### Bounds and fallbacks

- TaskGoal/v1 remains the only source-lowered route contract.
- DAG limits remain 64 nodes/operations, depth 8, and 64 decisions.
- One backbone proposal is allowed; local refinement is separately bounded.
- Exact and verified cached/fallback routes preserve the original fixed question.
- Invalid decoder output or rejected neural DAG proceeds only to a qualified deterministic
  fallback or typed UNRESOLVED.
- Operation allowance is shared across exact/cache/neural/refinement/fallback attempts.
- Wrong type, missing/forged binding, cycle, depth and operation-budget failures remain
  fail-closed in the A07 DAG contract and tests.

### Gold separation and replay

The solver's transitive-import test forbids assessment/oracle/factory gold dependencies.
`CapabilityResult.replay_record()` exports only replay identity, selected bindings,
dependencies, measured/reserved costs and typed outcome digest. Raw source payloads, score
and gold are absent.

## Safety / custody

No live learner was started, resumed, trained or mutated for this closeout. No optimizer,
checkpoint, private source, graph service or external effect is touched. Protected authority
is referenced only by identifier; no protected content is reproduced.

## Closeout decision

The original C04 software behavior is present on current reviewed unified, the formerly
missing upstream interfaces are now present in the consumed ancestry, the actual typed
readout path is exercised, and later production-authority remediation re-ran the
solver/replay/import/readout surface successfully.

Children #498, #499 and #500 were already closed under ADR-121 after their reviewed implementation landed. Parent #373 is now **implementation-complete and ready for human-reviewed integration of this closeout receipt**. #373 remains open until the human merges the closeout PR; no self-merge or manual early closure is authorized.
