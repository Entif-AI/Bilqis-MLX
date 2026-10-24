# SPEC-0038: Runtime consumes cadence policy

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `scheduler-policy`.  
**Wave:** `15` (derived from dependencies).  
**Dependencies:** `SPEC-0035`, `SPEC-0036`, `SPEC-0037`

## Invariant

The generic scheduler/runtime consumes `DebtCadencePolicy` roles and counters without knowing B, C, or the number four as semantic constants.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

Historical ADR-094 scheduling helpers still branch on concrete B/C identities even after the policy state becomes explicit.

## Predetermined design

Replace B/C identity dispatch with policy-role predicates and generic queue/cadence helpers. Keep priority recovery restricted to the policy's progression-priority role; do not infer that role from grade order. Adoption only carries or clears an explicitly supplied policy and never synthesizes one for a future grade.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/runtime/release_adoption.py`
- `bilqis_mlx/curriculum/scheduler.py`
- `bilqis_mlx/runtime/state.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/runtime/release_adoption.py`
- `bilqis_mlx/curriculum/scheduler.py`
- `bilqis_mlx/runtime/state.py`
- `bilqis_mlx/curriculum/tests/test_staged_school.py`
- `tests/integration/test_numeric_staircase.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `_b_debt_run_due`
- `_b_debt_run_queue`
- `_enter_due_b_debt_run`
- `_frontier_recovery_queue`
- `DebtCadencePolicy`

## Behavior that must remain unchanged

- exact ADR-094 queue order, reset/increment behavior, withheld-debt handling, and C-frontier-only recovery remain unchanged
- historical event/error/receipt wires remain unchanged

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `bilqis_mlx/curriculum/tests/test_staged_school.py`
- `tests/integration/test_numeric_staircase.py`
- `tests/integration/test_thin_boolean_numeric_debt.py`

Commands:
- `python -m pytest bilqis_mlx/curriculum/tests/test_staged_school.py tests/integration/test_numeric_staircase.py tests/integration/test_thin_boolean_numeric_debt.py`

**Verification tier:** `T1_INTEGRATION`.

## Stop conditions

- scheduler still dispatches on B/C identities for the cadence contract
- existing staircase/debt wire behavior changes

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- `NO_SEMANTIC_ROOT_TICKETS`
- `NO_UNDECLARED_FILES`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
