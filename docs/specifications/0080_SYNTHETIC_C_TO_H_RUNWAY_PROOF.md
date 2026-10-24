# SPEC-0080: Synthetic C-to-H runway proof

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `proof-closeout`.  
**Wave:** `28` (derived from dependencies).  
**Dependencies:** `SPEC-0038`, `SPEC-0050`, `SPEC-0073`, `SPEC-0076`, `SPEC-0077`, `SPEC-0078`, `SPEC-0079`

## Invariant

Six arbitrary successive synthetic grades advance through one fixed semantic ABI using only declarative releases/profiles/providers/policies, with no grade-specific runtime implementation and zero neural updates.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

Individual proofs do not demonstrate repeated reuse of the same factory across multiple future grades.

## Predetermined design

Build one deterministic direct-v2 chain with unfamiliar synthetic grades sized C=8, D=9, E=10, F=11, G=12, H=8. Keep the semantic graph/token ABI fixed so every transition is `UNCHANGED`; append-only geometry is proved separately by SPEC-0078. Precompile the entire C→H `ExecutableFactoryRelease` lineage before `start_new()`. At each hop persist admission, cold-decode the receipt/release/state, and prove exact predecessor/release/checkpoint identity. Carry one explicit weak capability per grade without neural updates, keep cumulative assessment scope over every active grade, then clear all debt at H and reach `WHOLE_SCHOOL_MASTERED` at the same checkpoint/optimizer step. Reuse the existing Grade-Z championship/telemetry pattern only as a bounded final smoke; do not invent new championship semantics.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `tests/system/test_factory_grade_z.py`
- `bilqis_mlx/factory/executable_release.py`
- `bilqis_mlx/runtime/release_adoption.py`
- `bilqis_mlx/runtime/admission.py`
- `bilqis_mlx/runtime/state.py`
- `bilqis_mlx/curriculum/scheduler.py`
- `bilqis_mlx/presentation/school_telemetry.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `tests/system/test_factory_multi_successor.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `compile_executable_factory_release`
- `ExecutableFactoryRelease.verify_successor_of`
- `_profile_transition`
- `_require_executable_factory_admission`
- `_state_from_json`
- `WHOLE_SCHOOL_MASTERED`

## Behavior that must remain unchanged

- no model parameters, AdamW moments, optimizer step, or checkpoint SHA change anywhere in the runway
- all successor releases are prepared before live learner state exists
- assessment scope is cumulative through the active synthetic grade and debt clears only after complete evidence

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `tests/system/test_factory_multi_successor.py`

Commands:
- `python -m pytest tests/system/test_factory_multi_successor.py`

**Verification tier:** `T2_SYSTEM`.

## Stop conditions

- any hop requires semantic-root-specific or grade-letter-specific runtime code
- any C→H transition requires append-only ABI growth instead of the fixed-ABI proof design
- precompiling a successor depends on learner mastery/state

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- `NO_SEMANTIC_ROOT_TICKETS`
- `NO_UNDECLARED_FILES`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
