# SPEC-0074: Isolate historical presentation compatibility

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `provider-custody`.  
**Wave:** `19` (derived from dependencies).  
**Dependencies:** `SPEC-0045`

## Invariant

Current telemetry renders generic event fields first; all historical event aliases, grade-prefix heuristics, and legacy labels live under compatibility with unchanged rendered text.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

presentation.school_telemetry still recognizes historical grade-specific event classes and capability-prefix fallbacks directly.

## Predetermined design

Move historical classification/alias heuristics into compatibility.telemetry_events and call them only as fallback after current generic fields.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/presentation/school_telemetry.py`
- `bilqis_mlx/compatibility/telemetry_events.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/presentation/school_telemetry.py`
- `bilqis_mlx/compatibility/telemetry_events.py`
- `bilqis_mlx/presentation/tests/test_letter_school_telemetry.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `_grade_from_capability`
- `SchoolTelemetry`
- `historical_event_grade`
- `historical_live_exam`

## Behavior that must remain unchanged

- all dashboard rows/strings remain identical, including OR/XOR LOSS and historical live-exam labels

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `bilqis_mlx/presentation/tests/test_letter_school_telemetry.py`

Commands:
- `python -m pytest bilqis_mlx/presentation/tests/test_letter_school_telemetry.py`

**Verification tier:** `T1_INTEGRATION`.

## Stop conditions

- rendered operator text changes

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
