# Factory blocked-leaf grooming decisions

**Status:** issue #150 grooming record.
**Date:** 2026-10-24.
**Change posture:** CONFORMANCE + MAINTENANCE.
**Scope:** preserve decisions for blocked executor questions without moving
architecture design back into page-local execution.

GitHub leaf comments remain the executable contracts. This record preserves
the reasoning and recurring completion rule; a leaf executor reads only the
current issue, its gate/amendments, direct prerequisites, and declared files.

## Guard-leaf completion rule

Guard leaves install a structural guard and freeze pre-existing violations as
explicit migration debt. They do not require the whole repository to already
satisfy the guard when downstream leaves exist specifically to migrate that
debt.

Therefore:

- focused adversarial fixtures prove the guard itself;
- existing violations remain visible and are not baselined away;
- downstream migration leaves remove the frozen debt;
- terminal SPEC-0082 requires zero remaining closure debt.

This applies to SPEC-0011, SPEC-0013, and SPEC-0015. It does not convert their
desired-state invariants into waivers. It separates guard installation from
later repository convergence so the dependency graph is not circular.

## SPEC-0012: split grade cardinality contracts

Permit the v2 validator edit in SPEC-0012. It owns this contract split:

- v2 `CurriculumDefinition` accepts 1..12 capabilities per grade;
- legacy `Course` remains 1..9;
- `bilqis_mlx/factory/curriculum_definition.py` is added to the bounded write surface;
- SPEC-0016 owns the representative twelve-capability proof after the split.

## SPEC-0013: ban current legacy-course APIs

Guard installation completes before caller migration. The AST guard detects
current `legacy_course` parameters, reads, keyword forwarding, and attribute
fallback while preserving the historical compatibility decoder exemption.
Current-path uses remain explicit migration debt for the direct-v2
legacy-decoupling leaves beginning at SPEC-0024. Repository-wide architecture
acceptance remains red until those migrations finish.

## SPEC-0011: compatibility writer quarantine

Compatibility must not call these current mutation-owner entrypoints:

- `bilqis_mlx.runtime.admission._factory_admission`;
- `bilqis_mlx.runtime.admission._executable_factory_admission`;
- `bilqis_mlx.runtime.checkpoints._advance`;
- `bilqis_mlx.runtime.checkpoints._persist`;
- `bilqis_mlx.runtime.checkpoints._reconcile_delivery_outbox`;
- `bilqis_mlx.runtime.release_adoption._adopt_executable_profile`;
- `bilqis_mlx.runtime.release_adoption._adopt_catalog_profile`.

Pure decode, translation, verification, schedule/state reconstruction, identity
checking, pure scheduler transforms, outbox-record construction, and the
neural-inert debt-boundary measurement helper are not writer calls for this
guard. Later leaves may migrate them for other architecture reasons. Existing
compatibility writer ownership is frozen debt for SPEC-0040/0041/0042.

## SPEC-0015: semantic-root neutrality

Reuse the structural identity rules in `scripts/quality/check_factory_closure.py`.
Generic factory/runtime code rejects concrete provider imports, control-flow
dispatch on capability literals matching `^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9_~-]*$`,
and concrete release-identity dispatch/reference under the existing
`RELEASE`/`RELEASES` alias rule.

Concrete source meaning remains legal only at explicit provider/registration
owners such as `bilqis_mlx/source_adapters/**`, the typed
`SourceAdapterRegistry`, the candidate realization registry, and compatibility
or research surfaces governed by their own boundaries. Descriptor identity
fields such as `adapter_id`, `generator_id`, `oracle_id`, and `source_sense_id`
are data; their presence is not itself a violation. Generic runtime branching
on a concrete identity is.

## Durable issue amendments

Amendments remain append-only and page-local. A later same-issue
`FACTORY_SPEC_AMENDMENT_V1` with `reopen: true` supersedes an earlier
`BLOCKED_SPEC_GAP`. A `FACTORY_DEPENDENCY_BLOCKED` receipt is different: it is a
staleable observation and requires only a recheck of the named direct
prerequisites, not a new same-page amendment.

The previously published amendments for SPEC-0011/#157, SPEC-0012/#158,
SPEC-0013/#159, and SPEC-0015/#178 remain historical issue receipts. Their
numbers are citations, not current-page bookmarks. Frozen issue bodies and
specifications are not rewritten; the active page gate controls local
navigation and the current bookmark remains in the handoff/checkpoint.
