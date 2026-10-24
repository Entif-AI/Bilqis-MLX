# Factory blocked-leaf grooming decisions

**Status:** controlling issue #150 grooming record.  
**Date:** 2026-10-24.  
**Change posture:** CONFORMANCE + MAINTENANCE.  
**Scope:** resolve the four executor questions buffered after SPEC-0009 without
moving architecture design back into Codex.

The GitHub leaf comments are the executable contracts. This document preserves
the reasoning and common completion rule in repository history.

## Guard-leaf completion rule

Guard leaves install a structural guard and freeze pre-existing violations as
explicit migration debt. They do **not** require the whole repository to
already satisfy the guard when downstream leaves exist specifically to migrate
that debt.

Therefore:

- focused adversarial fixtures prove the guard itself;
- existing violations remain visible and must not be baselined away;
- downstream migration leaves remove the frozen debt;
- terminal SPEC-0082 requires zero remaining closure debt.

This rule applies to SPEC-0011, SPEC-0013 and SPEC-0015. It does not convert
their desired-state invariants into waivers. It separates guard installation
from later repository convergence so the dependency graph is not circular.

## SPEC-0012: split grade cardinality contracts

**Decision:** permit the v2 validator edit in SPEC-0012.

SPEC-0012 owns the actual contract split:

- v2 `CurriculumDefinition` accepts 1..12 capabilities per grade;
- legacy `Course` remains 1..9;
- `bilqis_mlx/factory/curriculum_definition.py` is added to the leaf's bounded
  write surface;
- SPEC-0016 owns the representative twelve-capability proof after the limit is
  split, not a second widening of the same validator.

## SPEC-0013: ban current legacy-course APIs

**Decision:** guard installation completes before caller migration.

The existing AST guard may complete once focused tests prove it detects current
`legacy_course` parameters, reads, keyword forwarding and attribute fallback
while preserving the historical compatibility decoder exemption. The currently
detected current-path uses remain explicit migration debt for the direct-v2
legacy-decoupling leaves beginning at SPEC-0024.

Repository-wide architecture acceptance remains red until those migrations
finish.

## SPEC-0011: compatibility writer quarantine

**Decision:** freeze the exact current writer denylist.

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
guard. Later leaves may migrate them for other architecture reasons.

Existing compatibility writer ownership is frozen debt for SPEC-0040/0041/0042.

## SPEC-0015: semantic-root neutrality

**Decision:** reuse the already established structural identity rules from
`scripts/check_factory_closure.py`; do not invent a second identity syntax.

Generic factory/runtime consumer code must reject:

- concrete provider imports matched by the existing `CONCRETE_PROVIDER` rule;
- control-flow dispatch on capability literals matching
  `^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9_~-]*$`;
- concrete release-identity dispatch/reference under the existing
  `RELEASE`/`RELEASES` alias rule.

Concrete source meaning remains legal only at explicit provider/registration
owners:

- `bilqis_mlx/source_adapters/**`;
- `bilqis_mlx/factory/adapters.py::SourceAdapterRegistry`;
- `bilqis_mlx/factory/candidate_realizations.py::REALIZATIONS`;
- compatibility and research surfaces governed by their own boundaries.

Descriptor identity fields such as `adapter_id`, `generator_id`,
`oracle_id`, and `source_sense_id` are data. Their presence is not itself a
violation; generic runtime branching on a concrete identity is.

## Durable issue amendments

The executable amendments are:

- SPEC-0011 / #157: `FACTORY_SPEC_AMENDMENT_V1`;
- SPEC-0012 / #158: `FACTORY_SPEC_AMENDMENT_V1`;
- SPEC-0013 / #159: `FACTORY_SPEC_AMENDMENT_V1`;
- SPEC-0015 / #178: `FACTORY_SPEC_AMENDMENT_V1`.

Each amendment sets `reopen: true` and supersedes the earlier local
`BLOCKED_SPEC_GAP`. The page-gate protocol recognizes only a later amendment
on the same issue; no global state reconstruction is required.
