# SPEC-0070: Source owns fragile preservation semantics

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `provider-custody`.  
**Wave:** `23` (derived from dependencies).  
**Dependencies:** `SPEC-0064`, `SPEC-0069`

## Invariant

Generic fragile replay has no Boolean/U7C oracle or source-shape knowledge; source-owned callbacks provide structural/truth semantics.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

learning.fragile_replay imports and implements Grade-B-specific row recognition, operand truth, gold, and structural signatures.

## Predetermined design

Move source-specific recognition/pattern/gold/signature mechanics behind the school source/profile callback; keep cohort custody and selection generic.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/source_adapters/school.py`
- `bilqis_mlx/learning/fragile_replay.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/source_adapters/school.py`
- `bilqis_mlx/learning/fragile_replay.py`
- `bilqis_mlx/learning/tests/test_fragile_replay.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `_is_direct_u7c_row`
- `_preservation_pattern_counts`
- `_replay_operand_pattern`
- `_operand_kind`
- `structural_signature`

## Behavior that must remain unchanged

- all FRAGILE_* error strings and result shapes remain unchanged
- historical micro and direct-U7C rows select identically

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `bilqis_mlx/learning/tests/test_fragile_replay.py`

Commands:
- `python -m pytest bilqis_mlx/learning/tests/test_fragile_replay.py`

**Verification tier:** `T1_INTEGRATION`.

## Stop conditions

- learning layer still imports live_grade_b/grade_b_oracle after migration

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
