# A07.2 independent-gold isolation and applicability | implementation receipt

- Issue: #414; parent A07 #353; Lane A
- Consumed unified trunk:
  `44f78431709ec3b8fc23f47b45d9b18f167c7354`
  (already ancestor; no no-op merge)
- Consumed A07.1 reviewed implementation `ab5ed83`,
  EGM receipt `f950944`
- Branch: `codex/bamf02-a-semantics`; candidate head pending push
- Independent review: `EGM_PENDING`

## Owned behavior

1. **Gold is evaluator-owned.** The source-qualified PURE operator
   runtime imports no independent oracle, gold/assessment source
   adapter, generated assessment, Factory evaluator, or trainer.
   A new transitive production-import-closure test parses all
   reachable repository modules, not just the direct import lines,
   and rejects those forbidden dependencies. It also rejects
   gold/answer-key fields in runtime `OperatorBinding` and
   `TypedValue` records.
2. **Verified source algorithms are reused only when isomorphic.**
   The native ADD/SUB/MUL/DIV/EQ/LT/LE/SUCC operators bind the
   existing released `semantics.numeric.OPERATIONS` contract and
   call its pure `evaluate_pure` implementation. The legacy
   `evaluate` name still supports evaluator-owned memoization;
   the solver cannot reach that cache, including through recursive
   numeric expressions. Source COUNT is NumberSet->Number, not
   the cognitive EntitySet->Number COUNT; MOD is not in the native
   registered operation set. Both require separately granted
   formal-law authority and are not falsely attributed to the
   native numeric source implementation.
3. **Applicability is not gold.** Only
   `NUMERIC_LITERAL_OUTSIDE_SOURCE_ABI` and
   `NUMERIC_EXACT_DIVISION_UNDEFINED` become UNSUPPORTED.
   A source contract drift or unexpected source exception is a
   registered hard boundary failure, never silently converted
   to a valid null or guessed answer. UNKNOWN propagates;
   NONE is explicit and distinct from zero; PLANNED is a
   valid false value for IS_OCCURRED, not an occurred event.

The original frame-schema source-node hash formerly imported
`generated_assessment.digest`, exposing an evaluator module
through the solver's transitive frame dependency. It now uses
an exact local wire-compatible hash, with a Unicode test
proving the original JSON/UTF-8 digest semantics. This is a
dependency isolation repair, not a frame-identity migration.

Input/output versions remain
`bilqis.cognitive-typed-value/v1`,
`bilqis.cognitive-operator-spec/v1`,
`bilqis.cognitive-operator-binding/v1`,
`bilqis.semantic-frame-instance/v2`, and the native numeric
source contract recorded by `semantics.numeric.OPERATIONS`.

## Prime verification

`PATH=/Users/emilie/Code/bamf-planning-20261027/.venv/bin:$PATH python -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_cognitive_operators.py bilqis_mlx/semantics/tests/test_numeric_semantics.py bilqis_mlx/semantics/tests/test_source_memo.py bilqis_mlx/semantics/tests/test_frame_schema.py`:
**46 passed, 0 failed, 1 optional real-Atlas skip**.

The new tests cover transitive import closure, table-driven
numeric source equivalence, non-exact division, source ABI
limits, source-contract exception propagation, cache bypass,
exact source-node digest and explicit event/null/unknown states.
The existing evaluator-owned source memo tests remain green.

A07.3 owns bounded execution receipts, complete memo keys and
compositional typed DAG nodes. A07 parent and PR #546
integration remain open; no live training or merge occurred.
