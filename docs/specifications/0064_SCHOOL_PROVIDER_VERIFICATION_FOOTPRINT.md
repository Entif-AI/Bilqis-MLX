# SPEC-0064: School provider owns verification and footprint

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `provider-custody`.  
**Wave:** `22` (derived from dependencies).  
**Dependencies:** `SPEC-0025`, `SPEC-0061`, `SPEC-0062`

## Invariant

Micro/Boolean source ownership supplies its own independent row verification and canonical semantic footprint without grade-specific logic in generic factory code.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

Generic factory verification imports current Boolean implementations while source rows have no canonical runtime footprint callback.

## Predetermined design

Move predicate/connective/composite verification to source_adapters.school; derive micro footprints from inspect_source_query and IDBOOLOPS footprints from inspect_boolean_identification.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/factory/verification.py`
- `bilqis_mlx/source_adapters/school.py`
- `bilqis_mlx/source_adapters/structure.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/source_adapters/school.py`
- `bilqis_mlx/factory/verification.py`
- `bilqis_mlx/source_adapters/tests/test_source_adapters_micro.py`
- `bilqis_mlx/source_adapters/tests/test_boolean_composite.py`
- `bilqis_mlx/source_adapters/tests/test_boolean_identification.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `check_predicate`
- `check_connective`
- `check_boolean_composite`
- `check_b_composite_release`
- `check_b_idboolops_release`
- `inspect_source_query`
- `inspect_boolean_identification`
- `live_source_registry`

## Behavior that must remain unchanged

- all current Boolean acceptance/error behavior remains exact
- syntax/entity/literal representation terminals stay out of semantic footprints

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `bilqis_mlx/source_adapters/tests/test_source_adapters_micro.py`
- `bilqis_mlx/source_adapters/tests/test_boolean_composite.py`
- `bilqis_mlx/source_adapters/tests/test_boolean_identification.py`

Commands:
- `python -m pytest bilqis_mlx/source_adapters/tests/test_source_adapters_micro.py bilqis_mlx/source_adapters/tests/test_boolean_composite.py bilqis_mlx/source_adapters/tests/test_boolean_identification.py`

**Verification tier:** `T1_INTEGRATION`.

## Stop conditions

- factory retains executable Boolean source semantics
- footprint includes representation-only terminals

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- `NO_SEMANTIC_ROOT_TICKETS`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
