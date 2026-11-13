# SPEC-0031: Resume crosses compatibility once

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `legacy-decoupling`.  
**Wave:** `10` (derived from dependencies).  
**Dependencies:** `SPEC-0025`, `SPEC-0030`

## Invariant

Historical resume may decode legacy authority once; after v2 qualification all current execution uses admitted v2 authority.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

Resume can keep re-entering compatibility projection after v2 admission.

## Predetermined design

Make compatibility a one-way migration boundary.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/runtime/session.py`
- `bilqis_mlx/compatibility/executable_projection.py`
- `bilqis_mlx/runtime/admission.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/runtime/session.py`
- `bilqis_mlx/compatibility/executable_projection.py`
- `bilqis_mlx/runtime/tests/test_admission.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `resolve_legacy_resume_course`
- `verify_legacy_resume_binding`
- `_migrate_executable_release`

## Behavior that must remain unchanged

- preserve current external receipt/event/state behavior unless this leaf explicitly changes the contract
- preserve sealed legacy artifact decoding and historical compatibility behavior

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `bilqis_mlx/runtime/tests/test_admission.py::ExecutableMigrationTests::test_legacy_live_rubric_rebinds_without_changing_parent_evidence`

Commands:
- `python -m pytest bilqis_mlx/runtime/tests/test_admission.py::ExecutableMigrationTests::test_legacy_live_rubric_rebinds_without_changing_parent_evidence`

**Verification tier:** `T1_INTEGRATION`.

## Stop conditions

- historical sealed resume loses verifiability

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- `NO_SEMANTIC_ROOT_TICKETS`
- `NO_UNDECLARED_FILES`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
