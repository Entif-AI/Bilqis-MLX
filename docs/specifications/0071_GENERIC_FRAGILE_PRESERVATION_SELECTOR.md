# SPEC-0071: Single generic fragile preservation selector

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `provider-custody`.  
**Wave:** `24` (derived from dependencies).  
**Dependencies:** `SPEC-0070`

## Invariant

One generic implementation owns the exact three-fresh-draw, structural-match, truth-fallback, exam-exclusion, max-four preservation algorithm.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

Candidate evidence and prefetch duplicate portions of preservation selection and source-specific fallbacks.

## Predetermined design

Consolidate selection in learning.fragile_replay and parameterize it by retention/source policy callbacks.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/learning/fragile_replay.py`
- `bilqis_mlx/runtime/candidate_evidence.py`
- `bilqis_mlx/runtime/source_prefetch.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/learning/fragile_replay.py`
- `bilqis_mlx/runtime/candidate_evidence.py`
- `bilqis_mlx/runtime/source_prefetch.py`
- `bilqis_mlx/learning/tests/test_fragile_replay.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `select_preservation_rows`
- `select_structural_preservation_rows`
- `_fresh_fragile_preservation_rows`
- `_fragile_rows`

## Behavior that must remain unchanged

- seed order, rotation math, draw sizes, ordering, and FRAGILE_PRESERVATION_EXAM_ROW_LEAK remain exact

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

- serial and prefetched fixed-seed row order differs

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
