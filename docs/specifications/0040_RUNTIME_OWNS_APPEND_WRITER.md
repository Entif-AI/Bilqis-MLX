# SPEC-0040: Runtime owns append writer

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `compatibility-quarantine`.  
**Wave:** `13` (derived from dependencies).  
**Dependencies:** `SPEC-0011`, `SPEC-0033`

## Invariant

Historical next-grade mutation is runtime-owned with identical durable semantics.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

compatibility/trainer_transitions currently performs admission, advance, persist, and outbox reconciliation.

## Predetermined design

Move the exact transaction and event builder into runtime without signature/wire changes.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/runtime/release_adoption.py`
- `bilqis_mlx/compatibility/trainer_transitions.py`
- `tests/system/test_grade_b_trainer.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/runtime/release_adoption.py`
- `bilqis_mlx/compatibility/trainer_transitions.py`
- `tests/system/test_grade_b_trainer.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `_activate_next_admitted_grade`
- `activate_next_admitted_grade`
- `_next_grade_admission_event`

## Behavior that must remain unchanged

- preserve current external receipt/event/state behavior unless this leaf explicitly changes the contract
- preserve existing student parameters and own-AdamW state except explicit append-only row growth

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `tests/system/test_grade_b_trainer.py`

Commands:
- `python -m pytest tests/system/test_grade_b_trainer.py`

**Verification tier:** `T2_SYSTEM`.

## Stop conditions

- generation/event/student/optimizer behavior changes

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- `NO_SEMANTIC_ROOT_TICKETS`
- `NO_UNDECLARED_FILES`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
