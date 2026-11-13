# SPEC-0057: Decouple topology from ABI geometry

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `prepared-successor`.  
**Wave:** `24` (derived from dependencies).  
**Dependencies:** `SPEC-0034`, `SPEC-0056`

## Invariant

Schedule topology chooses append-grade versus same-grade transition independently from ABI geometry.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

_adopt_jit_proposal routes every APPEND_ONLY_EXPANSION to _adopt_catalog_profile, which assumes append-grade topology.

## Predetermined design

Always determine school transition from program topology; use semantic geometry only for learner materialization.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/runtime/release_adoption.py`
- `bilqis_mlx/curriculum/scheduler.py`
- `bilqis_mlx/factory/executable_release.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/runtime/release_adoption.py`
- `bilqis_mlx/curriculum/scheduler.py`
- `bilqis_mlx/runtime/tests/test_prepared_successor.py`
- `bilqis_mlx/factory/tests/test_executable_release.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `_profile_transition`
- `SemanticGeometryChange`

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
- `bilqis_mlx/runtime/tests/test_prepared_successor.py`
- `bilqis_mlx/factory/tests/test_executable_release.py::ExecutableReleaseTests::test_append_only_semantic_geometry_is_carried_by_successor_release`

Commands:
- `python -m pytest bilqis_mlx/runtime/tests/test_prepared_successor.py bilqis_mlx/factory/tests/test_executable_release.py::ExecutableReleaseTests::test_append_only_semantic_geometry_is_carried_by_successor_release`

**Verification tier:** `T1_INTEGRATION`.

## Stop conditions

- schedule behavior still branches on semantic geometry

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- `NO_SEMANTIC_ROOT_TICKETS`
- `NO_UNDECLARED_FILES`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
