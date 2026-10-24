# SPEC-0076: Direct-v2 twelve-cap Grade-Z proof

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `proof-closeout`.  
**Wave:** `25` (derived from dependencies).  
**Dependencies:** `SPEC-0019`, `SPEC-0020`, `SPEC-0021`, `SPEC-0033`, `SPEC-0048`, `SPEC-0051`, `SPEC-0068`

## Invariant

A synthetic twelve-capability grade compiles, admits, schedules, assesses, persists, cold-reads, and resumes directly through v2.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

Unit/integration contracts do not prove the reusable factory as a live whole.

## Predetermined design

Extend the existing Grade-Z system proof to the settled twelve-capability target.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `tests/system/test_factory_grade_z.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `tests/system/test_factory_grade_z.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `DisposableGradeZSystemProof`

## Behavior that must remain unchanged

- preserve current external receipt/event/state behavior unless this leaf explicitly changes the contract

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `tests/system/test_factory_grade_z.py`

Commands:
- `python -m pytest tests/system/test_factory_grade_z.py`

**Verification tier:** `T2_SYSTEM`.

## Stop conditions

- proof needs legacy Course in current path

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- `NO_SEMANTIC_ROOT_TICKETS`
- `NO_UNDECLARED_FILES`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
