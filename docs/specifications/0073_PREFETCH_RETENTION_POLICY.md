# SPEC-0073: Prefetch consumes generic preservation policy

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `provider-custody`.  
**Wave:** `25` (derived from dependencies).  
**Dependencies:** `SPEC-0029`, `SPEC-0069`, `SPEC-0071`

## Invariant

Source prefetch preserves its exact request/response wire and deterministic output while owning no Boolean preservation semantics.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

The worker path currently knows concrete fragile Boolean behavior instead of invoking generic policy/selector contracts.

## Predetermined design

Preserve fragile_fixed_rows/fragile_requested/fragile_seeds/fragile_rotation and preservation wire; resolve policy and generic selector in the worker.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/runtime/source_prefetch.py`
- `bilqis_mlx/profiles/retention.py`
- `bilqis_mlx/learning/fragile_replay.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/runtime/source_prefetch.py`
- `bilqis_mlx/runtime/tests/test_source_prefetch.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `_fragile_rows`
- `prepare_step_sources`

## Behavior that must remain unchanged

- worker isolation, seed order, rotation, and response preservation payload remain byte-compatible

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `bilqis_mlx/runtime/tests/test_source_prefetch.py`

Commands:
- `python -m pytest bilqis_mlx/runtime/tests/test_source_prefetch.py`

**Verification tier:** `T1_INTEGRATION`.

## Stop conditions

- prefetch wire key or serial parity changes

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
