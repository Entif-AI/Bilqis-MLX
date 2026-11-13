# SPEC-0011: Compatibility writer quarantine guard

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `guards`.  
**Wave:** `2` (derived from dependencies).  
**Dependencies:** `SPEC-0009`

## Invariant

compatibility/ may decode, translate, and verify historical artifacts but may not own current runtime mutation.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

compatibility/trainer_transitions.py still calls admission, checkpoint, adoption, and outbox writers.

## Predetermined design

Reject compatibility calls to the current writer denylist while allowing read/verification helpers.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `scripts/check_factory_architecture.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `scripts/check_factory_architecture.py`
- `bilqis_mlx/factory/tests/test_architecture.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `inspect_factory_architecture`

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
- `bilqis_mlx/factory/tests/test_architecture.py`

Commands:
- `python -m pytest bilqis_mlx/factory/tests/test_architecture.py`

**Verification tier:** `T0_UNIT`.

## Stop conditions

- read-only compatibility helper would be blocked
- writer set cannot be expressed structurally

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- `NO_SEMANTIC_ROOT_TICKETS`
- `NO_UNDECLARED_FILES`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
