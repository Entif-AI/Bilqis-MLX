# SPEC-0037: Explicit debt cadence policy

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `scheduler-policy`.  
**Wave:** `14` (derived from dependencies).  
**Dependencies:** `SPEC-0034`

## Invariant

ADR-094 debt cadence is immutable serialized school-state policy data, not grade-letter inference or ScheduleProgram identity.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

`curriculum/scheduler.py` currently derives the ADR-094 B/C/four-turn behavior from concrete grade identities and counters, so future schedule topology can accidentally inherit a historical exception.

## Predetermined design

Introduce an explicit frozen `DebtCadencePolicy` owned by school state. It carries the historical bounded-debt role, progression-priority role, and four completed non-debt-turn cadence as data. Historical receipts translate their existing B/C fields into that policy without changing old receipt bytes. Generic scheduler code consumes roles/cadence only. A later grade append clears the historical policy unless a successor explicitly supplies another policy. Do not put ADR-094 policy into `ScheduleProgram`, and do not change release/schedule identity merely to relocate this state policy.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/curriculum/scheduler.py`
- `bilqis_mlx/runtime/state.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/curriculum/scheduler.py`
- `bilqis_mlx/runtime/state.py`
- `bilqis_mlx/curriculum/tests/test_staged_school.py`
- `tests/integration/teaching/test_thin_boolean_numeric_debt.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `DebtCadencePolicy`
- `SchoolState`
- `read_state`

## Behavior that must remain unchanged

- preserve ADR-094 semantics exactly: debt exists in both bounded-debt and priority grades, priority grade is active frontier, four completed non-debt training queues make one debt run due, that run includes every currently imperfect admitted eligible debt capability, completion resets cadence, and every completed non-debt queue increments cadence
- pre-ADR-094 migration makes one full debt run immediately due
- future grades receive no historical B/C cadence unless an explicit policy supplies it

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `bilqis_mlx/curriculum/tests/test_staged_school.py`
- `tests/integration/teaching/test_thin_boolean_numeric_debt.py`

Commands:
- `python -m pytest bilqis_mlx/curriculum/tests/test_staged_school.py tests/integration/teaching/test_thin_boolean_numeric_debt.py`

**Verification tier:** `T1_INTEGRATION`.

## Stop conditions

- any historical B/C/four-turn behavior changes
- policy becomes inferred from grade order or capability prefixes
- moving the policy changes ScheduleProgram or release identity

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- `NO_SEMANTIC_ROOT_TICKETS`
- `NO_UNDECLARED_FILES`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
