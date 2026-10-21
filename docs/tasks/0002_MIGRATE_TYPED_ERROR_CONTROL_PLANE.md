# TASK 0002 — Migrate Bilqis to the Typed Error Control Plane

Implement SPEC 0004 until raw operator-facing exception identities are eliminated.

## Authority

- `docs/specifications/0004_TYPED_ERROR_CONTROL_PLANE.md`
- current central catalog: `bilqis_mlx/errors/`
- operational vocabulary: `bilqis_mlx/operator_vocabulary.py`
- migration ratchet: `scripts/error_control_plane.py`

## Non-negotiable rules

1. Do not add a new string-literal exception identity.
2. Do not refresh `operator_contract_baseline.json` to make new opaque debt pass.
3. Add or reuse a typed `ErrorSpec`.
4. Preserve exact repair context at the detection boundary.
5. Give each operator-visible error an owner, recovery disposition, self-heal owner, and operator action.
6. Split compound validators into small pure invariant functions before changing tests.
7. Convert policy arithmetic and unexplained numeric limits into named policy objects or constants.
8. Do not refactor historically hashed provider files in place. Use compatibility wrappers or versioned successors.
9. Keep stop reasons and blockers in the operational vocabulary. Do not turn them into exceptions.
10. Prefer bounded owner-level repair, regenerate, defer, or reroute when safe. The CLI block is the last line.
11. Tests are regression proof only. Exercise the real governed trainer after changes to runtime recovery behavior.

## Migration sequence

### A. Resume and custody

Migrate errors in scheduler, runtime state, admission, checkpoint loading, persistence, release readback, and compatibility.

For each raw error:
- identify the exact violated invariant;
- preserve the observed and expected values;
- determine whether deterministic reconciliation exists;
- route through `ErrorBus`;
- update generated docs;
- add focused unit coverage.

### B. Source, factory, and JIT

Migrate source adapter, candidate frontier, factory compiler, release, coverage, answer/world binding, and JIT errors.

Model expected source-development conditions as blockers or proposals, not crashes.

### C. Trainer and learning

Migrate lesson construction, assessment, retention, championship, stagnation, telemetry, and recovery.

Audit every hard stop. If the owner can safely regenerate, defer, reroute, reconcile, or restore from an authoritative receipt, implement that path before leaving an operator block.

### D. Remaining library contracts

Migrate lower-risk programmer and validation errors. Remove the legacy substring classifier when no operator-visible raw failures depend on it.

## Verification per unit

Run:

```text
python3 scripts/error_control_plane.py --check
python3 -B scripts/check_factory_architecture.py
python3 -B scripts/check_semantic_boundaries.py
```

Run the focused tests for the owner being migrated.

For runtime behavior, use an authorized isolated run or read-only preflight as appropriate. Record the exact checkpoint, optimizer step, release identity, error/recovery outcome, and whether neural state changed.

## Done

SPEC 0004 completion criteria are all true, the raw production error debt is zero for operator-facing paths, and live trainer runs demonstrate recovery at the migrated boundaries.
