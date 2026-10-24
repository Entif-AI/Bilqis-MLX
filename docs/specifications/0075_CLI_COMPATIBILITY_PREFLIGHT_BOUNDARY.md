# SPEC-0075: CLI legacy preflight translation boundary

**Status:** Desired-state execution leaf for issue #150.  
**Parent:** `Entif-AI/Bilqis-MLX#150`.  
**Track:** `provider-custody`.  
**Wave:** `22` (derived from dependencies).  
**Dependencies:** `SPEC-0045`, `SPEC-0051`

## Invariant

CLI orchestration/status is grade-neutral while historical Boolean/numeric/Grade-A interpretation is confined to compatibility with identical flags/help/JSON wire.

This is a reusable factory-mechanics leaf. It is not authority to create one implementation path, specification, or issue per semantic root.

## Current defect / root cause

cli.py still imports and interprets concrete historical profile/numeric staircase details despite an existing compatibility translator.

## Predetermined design

Use compatibility.cli_preflight descriptors for historical interpretation; leave current CLI orchestration and generic factory summary in cli.py.

Do not redesign this leaf during execution. If the observed code contradicts a required assumption, use the `BLOCKED_SPEC_GAP` protocol from SPEC-0005 and continue unrelated ready work.

## Authority clauses

- SPEC-0001 remains the broad desired-state authority: no factory release, no grade.
- ADR-095 controls decomposition: future semantic roots are declarative inputs, not automatic leaf identities.
- Compatibility may decode/translate historical artifacts but does not become a second current production architecture.
- No agent-run neural optimizer update is authorized by this leaf.

## Read allowlist

- `bilqis_mlx/cli.py`
- `bilqis_mlx/compatibility/cli_preflight.py`

Do not broaden this list during ordinary execution. Exact-symbol reference checks explicitly listed by the proof are permitted only for the named symbol family.

## Write allowlist

- `bilqis_mlx/cli.py`
- `bilqis_mlx/compatibility/cli_preflight.py`
- `tests/integration/test_operator.py`
- `tests/integration/test_numeric_staircase.py`

No other tracked path may be modified by this leaf.

## Named symbols / contracts

- `_boolean_revision_preflight`
- `preflight`
- `_inspect`
- `parse_args`
- `legacy_profile_label`
- `legacy_numeric_scope`
- `legacy_status_fields`
- `legacy_new_run_status_fields`

## Behavior that must remain unchanged

- all current CLI flags, aliases, help text, JSON keys and values remain byte-for-byte compatible

## Reuse / non-invention

- Reuse the existing typed factory/runtime/source mechanisms named in this spec.
- Do not add a new release family, plugin framework, semantic registry, compatibility architecture, or persisted sidecar unless this leaf explicitly requires one.
- Prefer stdlib and existing repository helpers over new dependencies.

## Prior-art disposition

Use repository mechanisms first. Import-layer/independence concepts may be borrowed as contract vocabulary; do not add Import Linter. Deterministic acceptance remains zero-install; Hypothesis is not required for this leaf.

## Focused proof

Owned tests:
- `tests/integration/test_operator.py`
- `tests/integration/test_numeric_staircase.py`

Commands:
- `python -m pytest tests/integration/test_operator.py tests/integration/test_numeric_staircase.py`

**Verification tier:** `T1_INTEGRATION`.

## Stop conditions

- CLI wire or alias changes

If a stop condition fires, do not expand architecture scope. Emit `BLOCKED_SPEC_GAP` with the exact failed assumption, observed fact, minimal additional authority/surface required, and proof already attempted.

## Forbidden exploration

- `NO_BROAD_REPO_SEARCH`
- Do not perform broad Git history archaeology, broad GitHub search, or unrestricted web research.
- Do not invent semantic-root work merely because a fixture contains a named capability.

## Completion receipt

A successful issue comment must use `FACTORY_LEAF_DONE` and bind this spec hash, the mapped issue-body hash, the run bootstrap hash, the remotely visible commit SHA, and the focused proof results.
