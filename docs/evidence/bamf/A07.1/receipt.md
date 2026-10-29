# A07.1 source-qualified PURE operators | implementation receipt

- Issue: #413; parent: A07 #353; Lane A
- Branch: `codex/bamf02-a-semantics`; reviewed trunk:
  `codex/bamf-unified-base-20261028`
- Consumed unified SHA:
  `44f78431709ec3b8fc23f47b45d9b18f167c7354`
  (already an ancestor at leaf start; no synthetic merge)
- Consumed A03 implementation: `4c422aa`, A03 EGM: `5e84ffb`
- Candidate head: pending commit/push verification
- Independent review: `EGM_PENDING` until immutable-head Goldfish readback

## Source and API

`bilqis_mlx/semantics/cognitive_operators.py` adds immutable
`CognitiveOperatorSpec`, `OperatorRegistry`, `OperatorBinding`,
`TypedValue`, `SourceOperand`, `Duration`, `UnitConversion`,
`default_registry(release)` and
`execute_pure(operator_id, typed_inputs, binding) -> TypedValue`.

The registry declares 25 PURE operators with explicit
`core.Signature` input/output types, applicability identifiers,
version `v1`, and SHA-256 implementation digests bound to the
module bytes and operator identity. No semantic tokens are allocated.
Registry resolution rejects forged applicability, signatures,
versions and implementation digests.

Source input version: `bilqis.cognitive-source-operand/v1`.
Typed value version: `bilqis.cognitive-typed-value/v1`.
Operator spec: `bilqis.cognitive-operator-spec/v1`.
Registry: `bilqis.cognitive-operator-registry/v1`.
Binding: `bilqis.cognitive-operator-binding/v1`.
Consumed A03 frame instance: `bilqis.semantic-frame-instance/v2`.
Consumed A13 source grant: `bilqis.context-source-grant/v1`.

## Acceptance coverage

1. Role lookup preserves exact role/occurrence and VALUE/NONE/UNKNOWN;
   identity and type inspection consume A03 ConceptRef semantic IDs,
   ABI and authoritative type IDs. Entity-set membership and Boolean
   NOT/AND/OR/XOR/IMPLIES/IFF use exact typed inputs.
2. ADD/SUB/MUL/DIV/MOD/EQ/LT/LE/SUCC/COUNT use an admitted, closed
   `FiniteDomain` with the existing decimal integer text codec.
   Overflow, underflow, division by zero and non-exact division are
   unsupported, never coerced. Literal 2+3=5 and zero versus NONE
   have direct tests.
3. Exact rational duration conversion requires a separately
   source-granted direct `UnitConversion` edge. The 1/4 hour to
   15 minute witness uses no float. Structural PARENT_OF/BEFORE
   use admitted source frame occurrences and spans; IS_OCCURRED
   distinguishes PLANNED from OCCURRED.
4. `execute_pure` recomputes A13 frame-context eligibility and
   validates exact source-grant evidence for each task-visible or
   admitted-knowledge operand. It refuses revoked, stale, foreign,
   invisible and ungranted inputs before computing.
5. Source operands are not evaluation answers; the implementation
   imports no assessment, verification/gold, MLX, optimizer or
   trainer modules. It neither mutates the live student nor grants
   source-release admission.

## Prime execution proof

`PATH=/Users/emilie/Code/bamf-planning-20261027/.venv/bin:$PATH python -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_cognitive_operators.py`:
**14 passed, 0 failed, 0 skipped**.

`git diff --check`: passed. The repository's module-size and
error-control-plane checks retain inherited unrelated shared-runtime
findings; no A07.1-specific new finding was observed.

The A07.2 evaluator/source separation and A07.3 compositional DAG,
memoization and bounded execution receipts remain separate leaves.
No parent acceptance, integration merge or live training is claimed.
