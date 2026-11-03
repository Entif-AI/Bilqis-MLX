# Public B05 producer-admission hold — #757

Consumed reviewed unified `2800946729e484875f7d1f57f0e6d85078936394`;
branch `codex/757-public-selector-admission` also carries the independently
recorded #756 numerical witness. Scoped admission repair:
`f596a71173fb7c7080cc2e4e501e2ffba1e6b6bb`.

## Defect and repair

Both public selector paths accepted caller-created `DepthSummary` records and a
shape-compatible parameter view. The g2-as-g1 regression constructed a legitimate
g2 tensor, relabeled it as `DepthSummary('g1', 4, ...)` and expected rejection.
Before repair, both public paths reached feature composition and numerical
selection. The new three-test admission selection recorded eight assertion
failures across caller, relabeling, ordering and future-source cases.

Public `depth_select` and `depth_select_with_diagnostics` now raise the existing
typed topology error before any feature composition or selector arithmetic.
Neither path accepts raw summaries as evidence of model, generation, prediction
boundary, parameter tree or producer origin.

The previous raw-array implementations remain private as
`_numerical_depth_select` and `_numerical_depth_select_with_diagnostics`.
Their numerical/source-feature unit callers were migrated without removing
equation, gate, feature, gradient, normalization or malformed-input assertions.
The public admission regressions separately assert rejection before both feature
composition and depth computation. There are no other production selector callers
on this reviewed unified source.

This implements the issue's required pre-qualification hold. It does not integrate
an unreviewed B11 candidate or pretend that public selection is operational.
Qualified production selection must later consume the independently accepted #586
producer and its #747/#748 repairs, replay actual boundaries and preserve B05
compute/gradient custody. Parent #577 remains open for that integration and its
whole-candidate EGM.

## Verification

Native Apple Silicon/MLX 0.32.4, NumPy 2.5.4, disposable fixture arrays:

```sh
python -B scripts/run_tests.py bilqis_mlx/runtime/tests/depth
```

At repair source `f596a71173fb7c7080cc2e4e501e2ffba1e6b6bb`:
`TEST_TOTALS total=18 passed=18 failed=0 skipped=0 errors=0`.
This includes the numerical oracle, all-completed-source and parameter gradients,
gate/adapter order, paired future-state executions and intentional future-read
mutation rejection, source-feature composition, and both public-path holds.

All four changed Python files pass structure and hygiene with zero findings.
Factory architecture and governance checks pass; error-control reports
`new debt 0`; whitespace is clean.

The repair does not qualify caller tensors, invent a receipt/token or establish
retained-generation custody. No fresh per-fix EGM or PR is opened. Fresh pinned EGM
remains the complete merge-ready parent's gate after dependency/repair consumption.
No self-merge, persistent student start/resume/stop, learner/optimizer/teacher,
champion, checkpoint, semantic admission or graph mutation occurred.
