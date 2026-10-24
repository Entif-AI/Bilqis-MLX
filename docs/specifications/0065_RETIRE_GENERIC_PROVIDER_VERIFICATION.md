# SPEC-0065: Retire generic provider verification logic

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `provider-custody`.  
**Wave:** `23` (derived from dependencies).  
**Dependencies:** `SPEC-0063`, `SPEC-0064`

## Invariant

bilqis_mlx.factory.verification contains no provider-specific executable truth logic after source owners migrate.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

A generic factory module is acting as a second source-domain owner and imports concrete providers.

## Predetermined design

Exact-reference-check remaining exports; delete the module only when consumers are zero, otherwise leave a zero-logic compatibility re-export facade.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/factory/verification.py`
- `bilqis_mlx/verification/copular.py`
- `bilqis_mlx/verification/event_frames.py`
- `bilqis_mlx/source_adapters/school.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/factory/verification.py`
- `bilqis_mlx/source_adapters/school.py`
- `bilqis_mlx/source_adapters/tests/test_copular.py`
- `bilqis_mlx/source_adapters/tests/test_event_frames.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `check_copular`
- `COPULAR_ORACLE`
- `EVENT_FRAME_ORACLE`
- `check_numeric`
- `check_predicate`
- `check_connective`
- `check_boolean_composite`

## Behavior that must remain unchanged

- verification.numeric/copular/event_frames remain independent from generators

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `bilqis_mlx/source_adapters/tests/test_copular.py`
- `bilqis_mlx/source_adapters/tests/test_event_frames.py`

Commands:
- `rg -n 'factory\.verification|check_numeric|check_predicate|check_connective|check_boolean_composite' bilqis_mlx tests`
- `python -m pytest bilqis_mlx/source_adapters/tests/test_copular.py bilqis_mlx/source_adapters/tests/test_event_frames.py`

**Verification tier:** `T1_INTEGRATION`.

## Stop conditions

- independent verification oracle is merged into a generator
- nonzero consumer is hidden by deletion

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- `EXACT_SYMBOL_SEARCH_ONLY`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
