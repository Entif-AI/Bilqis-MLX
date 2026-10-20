# Code-smell review baseline — 2026-10-19

This file records the merge-time review state for the large curriculum-factory cutover branch. The code-smell audit reports review candidates, not proven defects. Regenerating the baseline does **not** assert that the findings are desirable or resolved; it establishes the exact reviewed debt that future changes must not increase silently.

## Current reviewed debt

- `branch-density`: 25
- `duplicate-error-code`: 58
- `long-function`: 37
- `module-mutable-literal`: 20
- `positional-grade-boundary`: 1

Total findings: **141** across **55** files.

## Highest-density files

- `bilqis_mlx/trainer.py`: 20
- `bilqis_mlx/diagnostics/observations.py`: 7
- `bilqis_mlx/presentation/school_telemetry.py`: 7
- `bilqis_mlx/presentation/spiral_dashboard.py`: 7
- `bilqis_mlx/factory/autonomy.py`: 5
- `bilqis_mlx/learning/championship_witnesses.py`: 5
- `bilqis_mlx/runtime/autonomy_state.py`: 5
- `bilqis_mlx/semantic_coverage.py`: 5
- `bilqis_mlx/cli.py`: 4
- `bilqis_mlx/curriculum/scheduler.py`: 4
- `bilqis_mlx/grade_transition.py`: 4
- `bilqis_mlx/diagnostics/event_evidence.py`: 3
- `bilqis_mlx/ni_construction.py`: 3
- `bilqis_mlx/pedagogical_parity.py`: 3
- `bilqis_mlx/registry_ast.py`: 3

## Merge disposition

- The branch introduces substantial new factory, autonomy, championship, stagnation, telemetry and grade-transition code. Several functions exceed the current review thresholds and repeated validation codes are common.
- These findings are accepted as explicit refactoring debt for this merge candidate, not reclassified as clean architecture.
- `scripts/code_smell_audit.py --check-baseline ...` remains a forward gate: any additional finding after this reviewed state fails CI until fixed or deliberately re-reviewed.
- This baseline does not supersede SPEC-0001 modularity requirements or the architecture guard. It only prevents the hygiene checker from treating the entire already-reviewed feature branch as an unbounded new regression on every run.
