# SPEC-0072: Candidate evidence consumes retention policy

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `provider-custody`.  
**Wave:** `25` (derived from dependencies).  
**Dependencies:** `SPEC-0069`, `SPEC-0071`

## Invariant

Candidate evidence retains exact acceptance arithmetic and reason payloads while fragile capabilities and source semantics arrive only through retention/source policy.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

runtime.candidate_evidence contains executable B-specific preservation assumptions.

## Predetermined design

Consume the frozen retention policy and generic selector; do not change candidate-retention gates.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/runtime/candidate_evidence.py`
- `bilqis_mlx/profiles/retention.py`
- `bilqis_mlx/learning/fragile_replay.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/runtime/candidate_evidence.py`
- `bilqis_mlx/learning/tests/test_learning_experiment.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `_fragile_replay_evidence`
- `_candidate_fixed_evidence`
- `_fresh_fragile_preservation_rows`

## Behavior that must remain unchanged

- FRAGILE_COMPOSITION_REPLAY_REGRESSION and all existing acceptance reason/status payloads remain exact

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `bilqis_mlx/learning/tests/test_learning_experiment.py`

Commands:
- `python -m pytest bilqis_mlx/learning/tests/test_learning_experiment.py`

**Verification tier:** `T1_INTEGRATION`.

## Stop conditions

- accept/reject arithmetic changes

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
