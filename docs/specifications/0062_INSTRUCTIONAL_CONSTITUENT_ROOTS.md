# SPEC-0062: Instructional constituent root closure

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `provider-custody`.  
**Wave:** `4` (derived from dependencies).  
**Dependencies:** `SPEC-0016`

## Invariant

A capability may expose only its own taught roots, prior-grade roots, and roots from strictly earlier teaching stages of the same grade.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

Prerequisite labels alone do not prevent a provider row from leaking later-stage, peer-stage, future-grade, or unknown semantics into instruction.

## Predetermined design

Derive allowed roots purely from CurriculumDefinition ordering; same-stage peers/later stages/later grades are excluded and an unstaged grade grants no same-grade predecessor ordering.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/factory/curriculum_definition.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/factory/curriculum_definition.py`
- `bilqis_mlx/factory/tests/test_curriculum_definition.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `instructional_constituent_roots`
- `CurriculumDefinition`
- `GradeSpec`
- `CapabilitySpec`

## Behavior that must remain unchanged

- do not create a persisted closure sidecar, learner receipt, EvidenceKind, or duplicate root registry

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `bilqis_mlx/factory/tests/test_curriculum_definition.py`

Commands:
- `python -m pytest bilqis_mlx/factory/tests/test_curriculum_definition.py`

**Verification tier:** `T0_LEAF`.

## Stop conditions

- closure depends on grade letters or inferred source order

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- `NO_SEMANTIC_ROOT_TICKETS`
- `NO_DUPLICATE_REGISTRY`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
