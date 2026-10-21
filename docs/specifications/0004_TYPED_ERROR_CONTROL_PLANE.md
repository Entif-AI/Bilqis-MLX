# SPEC 0004 — Typed Error Control Plane and Operator Recovery

Status: ACTIVE MIGRATION
Owner: Bilqis runtime/factory architecture
Applies to: all operator-visible failures, controlled stops, blockers, recovery actions, and policy-bearing validation in Bilqis MLX.

## Problem

Bilqis has a large legacy backlog of string-literal exceptions. The production scan maintained by `scripts/error_control_plane.py` freezes the current raw-raise footprint as migration debt.

Raw strings currently mix machine identity, human explanation, ownership, recovery policy, control-flow signaling, compatibility drift, and test assertions. Compound validators also collapse independent invariants into one failure identity. Later layers then inspect string fragments such as `DRIFT`, `MISSING`, or `INVALID` to guess a recovery posture.

This discards the exact facts needed for repair before the operator layer receives the failure.

The same problem appears in policy validation when numeric policy is embedded as arithmetic such as `each < 4`, `each % 2`, or `max_rounds <= 32`.

## End state

Bilqis has one typed error control plane.

New domain code raises an `ErrorSpec` through `ErrorBus`:

```python
ErrorBus.raise_(
    SCHOOL.STATE.COURSE_DIGEST_MISMATCH,
    saved_course_digest=state.course_digest,
    runtime_course_digest=program.digest(),
)
```

The dotted path is stable machine identity. Human text is a rendering. Each error spec owns:

- dotted code;
- domain owner;
- localization-ready message key;
- message template;
- recovery key and disposition;
- operator steps;
- state-preservation rule;
- self-heal owner;
- legacy aliases during migration.

The CLI renders the structured report. Tests assert the typed error object and repair context, not a string fragment.

Controlled stop reasons and JIT blockers use a separate typed operational vocabulary. They are not exceptions. The same generated field manual contains both categories.

## Public interfaces

```python
ErrorBus.raise_(spec: ErrorSpec, **context) -> NoReturn
ErrorBus.report(error: BaseException | str) -> ErrorReport
```

Legacy exceptions pass through one compatibility classifier only. No second recovery policy table may diverge from the bus.

Operator lookup:

```text
python3 -m bilqis_mlx.cli explain CODE
```

The command accepts typed errors, legacy identities, stop reasons, blockers, and event aliases. A legacy identity that historically collapsed multiple invariants must display every possible typed replacement.

## Generated field manual

`scripts/error_control_plane.py --write-docs` generates:

- `docs/operations/ERROR_FIELD_MANUAL.md`;
- `docs/operations/error_catalog.json`.

The manual is derived from the same catalogs used by runtime code. Hand-edited glossary entries are not authoritative.

## Raw-string debt ratchet

`docs/evidence/development/operator_contract_baseline.json` freezes the pre-migration opaque error and numeric-guard debt from commit `708c117`.

```text
python3 scripts/error_control_plane.py --check
```

The check fails when a new raw string exception identity or opaque numeric guard appears beyond that baseline, or generated docs are stale. Existing debt may remain temporarily or decrease. Moving an existing debt token into a smaller function is allowed; duplicating it or creating a new opaque contract is not. The baseline must not be refreshed merely to admit new debt.

The check runs in normal quality and release workflows.

## Error namespaces

Namespaces describe ownership and invariant shape, not English phrasing.

Examples:

- `SCHOOL.STATE.COURSE_DIGEST_MISMATCH`
- `SCHOOL.STATE.GRADE_INDEX_OUT_OF_RANGE`
- `FACTORY.RELEASE.MANIFEST_CONTENT_DRIFT`
- `SEMANTIC_COVERAGE.AUDIT.INVALID_BUDGET`
- `SOURCE.SAMPLING.BALANCED_BINARY_COUNT_INVALID`

Do not create a code from an English sentence. Model the domain first, then name the violated invariant.

## Recovery semantics

Every new operator-visible error must answer:

1. What invariant failed?
2. Which domain owns repair?
3. Which exact facts prove the failure?
4. Can the owner repair it safely without operator action?
5. If not, what is the smallest safe operator action?

Owner-level recovery runs before the final CLI block when a safe deterministic repair exists. The CLI is the last line, not the primary recovery engine.

Identity and custody conflicts remain fail-closed. Self-healing must never mean deleting hashes, editing a checkpoint, weakening an oracle, or coercing a mismatched value through validation.

## Compatibility doctrine

A sealed artifact is verified by the schema contract that minted it.

A later Python dataclass field, default, serializer, or manifest shape must not retroactively change the digest of an older wire artifact.

Historical decoders therefore:

1. verify the raw persisted payload against its sealed digest;
2. decode the historical schema;
3. project safe absent fields into the current typed model;
4. verify semantic/source structure independently of today's serializer identity;
5. perform an explicit successor migration.

Current serializers may verify current artifacts. They may not judge historical wire identity.

## Policy and magic-number doctrine

Policy-bearing arithmetic must be named.

Bad:

```python
if not 1 <= max_rounds <= 32 or each < 4 or each % 2:
    ...
```

Target:

```python
violations = SOURCE_COMPOSITION_AUDIT_BUDGET.violations(max_rounds, each)
if violations:
    ErrorBus.raise_(SEMANTIC_COVERAGE.AUDIT.INVALID_BUDGET, ...)
```

Values such as 32 must declare what they are. If 32 is a resource/search ceiling rather than a semantic invariant, code and documentation must say so.

Pure policy functions return or describe violations. Boundary functions decide whether to raise.

## Historical generator constraint

Some provider modules are hashed into admitted release identity. Refactoring those files can change a sealed generator hash even when semantics are unchanged.

Migration must distinguish ordinary code from historically hashed provider code. Hashed provider cleanup requires a versioned successor or compatibility wrapper. Do not create ABI drift to remove stylistic debt.

## Migration order

### Wave 1 — control plane and enforcement

Complete when typed errors, CLI rendering, `explain`, generated docs, the raw-debt ratchet, and CI enforcement exist.

### Wave 2 — resume and custody boundaries

Migrate scheduler state, checkpoint, admission, release, and persistence failures first. Split compound validators into pure invariant checks and add owner-level reconciliation where safe.

### Wave 3 — source, factory, and JIT boundaries

Migrate source adapters, candidate frontier, factory compilation, executable release, JIT proposal, and coverage failures. Blockers and stops belong in the operational vocabulary.

### Wave 4 — trainer, learning, and diagnostics

Migrate lesson construction, retention, championship, stagnation, assessment, and diagnostics. Expected generated-work failures must prefer regenerate, defer, or reroute over operator termination.

### Wave 5 — remaining library failures

Migrate lower-risk validation and programmer-contract failures. Delete the legacy substring classifier when no operator-facing raw errors remain.

## Testing doctrine

Tests protect units and contracts. They do not prove that the trainer works.

For error handling, tests should call pure invariant/policy units, assert typed specs and repair context, test compatibility decoders with historical wire shapes, and enforce the raw-debt ratchet.

Operational qualification still requires the governed trainer.

## Current first migration slice

This specification begins with a working vertical slice:

- `INVALID_OR_DRIFTED_SCHOOL_STATE` split into five typed school-state invariants;
- CLI error rendering routed through `ErrorBus`;
- old recovery table reduced to a compatibility facade;
- sealed factory-release v1 decoder added;
- v1 resume scheduler reconstructed from the run's immutable admitted factory artifact;
- semantic-coverage audit budget moved behind a named policy object;
- `AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED`, `STAGED_SUCCESSOR_BINDING_REQUIRED`, and `AUTONOMY_SAFE_HOLD` registered as operational vocabulary;
- generated field manual and raw-debt ratchet added.

The Prometheus read-only resume preflight reconstructs its saved Grade-B `RECOVERY_2` school from the sealed factory artifact with no blockers. No model or optimizer state is changed by that proof.

## Completion criteria

The migration is complete only when:

- production contains no raw operator-facing exception identities;
- every operator-facing error has typed ownership and recovery;
- no substring heuristic determines primary recovery policy;
- all operator-visible stop reasons and blockers are cataloged;
- generated documentation is current by construction;
- CI rejects new uncataloged error literals;
- historically sealed artifacts use schema-owned compatibility paths;
- repairable failures attempt bounded owner-level recovery before blocking;
- policy constants are named and tested as domain units;
- governed trainer runs demonstrate recovery behavior at affected boundaries.
