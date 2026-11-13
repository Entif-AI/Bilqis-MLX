# C04.1 | Source-qualified exact, cached and neural DAG routing

Issue #498, parent C04 #373. Lane C
`codex/bamf02-c-runtime` consumed reviewed unified
`6b5460032fc0b19115843cce95fe8be9582af141`
at merge `ecc4b7656dc3f2ff7a806fe71c151d86efb8840c`.
This includes the actual reviewed A07.1–A07.3 operator
registry, source-visible DAG executor and memo authority.
Implementation commit:
`39c1d95a708f12baf25b8cff3bb8750ca61def7d`.
Draft PR #550 remains unmerged.

## Exact owned behavior

- `bilqis.c04.route-registry/v1` registers deterministic
  applicability order: source-qualified exact operator,
  verified cached composition, bounded neural DAG proposal,
  then typed unresolved.
- `solve_task(task, context, generation, budget)` consumes
  actual A07 `TaskGoal`, `OperatorBinding`, `execute_dag`,
  `DAGBudget` and optional source-bound memo. It never
  inspects grade labels, assessment answers or gold data.
- Exact applicable source-qualified operators receive one
  typed answer and full score 1.0. Cached compositions
  require the same source-binding digest, rights epoch,
  correction generation and a host-owned qualification
  verifier; unverified cache receipts are skipped.
- Only unresolved work may invoke the B11 neural proposer,
  at most once. The request carries goal/unresolved signature,
  source-binding digest, generation and allowed operator IDs,
  not raw private source values. A neural proposal must be
  another typed source-visible DAG constrained to the original
  task's operator and binding scope, then is evaluated by
  the actual A07 executor. Neural scores remain unset for
  C04.2 evaluator qualification.
- Opaque input handles are never dereferenced outside
  A07's receiving operator/signature checks.

## Verification and remaining gates

`PATH=/Users/emilie/Code/bamf-planning-20261027/.venv/bin:$PATH
python -B scripts/run_tests.py
bilqis_mlx/runtime/tests/test_cognitive_solver.py
bilqis_mlx/semantics/tests/test_cognitive_dag.py
bilqis_mlx/semantics/tests/test_cognitive_operators.py`:
**53 passed, 0 failed, 0 skipped**.

Tests cover exact answer 5 from 2+3, cache-before-neural
selection, refusal of unverified cache, one neural DAG
proposal for ambiguous unresolved composition, rejection
of a foreign source handle and typed unresolved fallback.
Static scans found no new C04-specific error-control or
module-size debt beyond inherited findings.

The actual B11 neural proposer, source-owned cache
qualification service, C04.2 scoring/uncertainty and
C04.3 replay/negative-evidence policy remain integration
gates. Independent EGM is pending. No live neural
inference, optimizer write, private source or merge occurred.
