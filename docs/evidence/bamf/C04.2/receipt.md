# C04.2 | Bounded local refinements and safe neural fallback

Issue #499, predecessor C04.1 #498, parent C04 #373.
Lane C `codex/bamf02-c-runtime` consumed reviewed unified
`6b5460032fc0b19115843cce95fe8be9582af141`
at merge `ecc4b7656dc3f2ff7a806fe71c151d86efb8840c`.
Implementation commit:
`d5a5885a6a087f3ac6fcad41abdcc7bd47ab66c7`.
Draft PR #550 remains unmerged.

## Exact owned behavior

- The actual A07 `DAGBudget` caps pure DAG operations at
  64. C04's `SolveBudget/v2` caps backbone proposals at
  one per solve and explicitly bounds B06 local refinement
  attempts by the task's decision budget.
- Exact source-qualified operators and verified cached
  compositions receive full score 1.0. Neural answers
  remain unscored pending C04.3/B11 evaluator authority.
- Invalid neural proposals, foreign source handles,
  rejected DAGs or unresolved neural output cannot
  become accepted answers. The solver first permits
  bounded typed local refinements, then a source/rights/
  correction-verified deterministic fallback if supplied.
  Otherwise it returns explicit typed UNRESOLVED with
  a stable reason, never an invented answer.
- `bilqis.c04.route-registry/v2` orders exact, cached,
  neural, deterministic fallback, unresolved. The
  `bilqis.c04.capability-result/v2` records one backbone
  call count, bounded local refinement count, score and
  fallback reason.

## Verification and remaining gates

`PATH=/Users/emilie/Code/bamf-planning-20261027/.venv/bin:$PATH
python -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_cognitive_solver.py
bilqis_mlx/semantics/tests/test_cognitive_dag.py
bilqis_mlx/semantics/tests/test_cognitive_operators.py`:
**55 passed, 0 failed, 0 skipped**.

Tests cover one backbone plus one bounded refinement,
invalid neural payload returning source-qualified
deterministic fallback with full exact score, foreign
source proposal returning typed unresolved, and no
neural call when exact/cached routes suffice.
No new C04-specific static error-control or module-size
debt beyond inherited findings.

Actual B06 refinement implementation, B11 neural
backend, evaluator scoring, C04.3 replay receipts and
C04 parent integration remain pending. Independent EGM
is pending. No live model inference, optimizer write,
private source or merge occurred.
