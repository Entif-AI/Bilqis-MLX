# Source-verified cross-grade composition coverage

## Run the audit

From the private Bilqis MLX repository:

```sh
npm run curriculum:coverage
npm run curriculum:coverage -- --max-rounds 1 --details
```

This command reads the approved A+B Course, the pinned Token Atlas snapshot,
and the historical source interpreters. It performs no model or optimizer work.

## What the compiler checks

`semantic_coverage.discover_composition_obligations()` matches typed operator
inputs to outputs of earlier-grade capabilities. It includes relationships
missing from the hand-authored prerequisite lists. Each operand position has
its own obligation, source-token identity, meaning-contract digest, and
admission state. The source path identifies possible interpreter boundaries.
Type compatibility alone leaves coverage debt open.

`audit_pinned_micro_generator()` builds repeatable source-verified records from
the current Grade B generator. The pinned historical interpreter, its separate
evaluator, and independently implemented Grade A/B record oracles must agree.
For each supported edge, the audit measures the reachable combinations of
operand truth and final operator truth. It retains unsampled combinations as
explicit debt instead of inventing positive or negative cases.

For the current A+B source contract, six A predicates return Boolean values,
and the six B operators accept Boolean operands. This yields 66 candidate
operand-slot obligations. Existing B prerequisites declare three A families:
`A.IDENTITY`, `A.PARENT`, and `A.LINK`. The compiler also discovers
`A.MEMBER`, `A.EDGE`, and `A.MAPS` as type-compatible candidates.

The first three predicates use the source `micro` AST; the remaining three use
the separate `development` AST. The present Grade B constructor embeds only
`micro` expressions. Cross-interpreter candidates remain
`CROSS_SOURCE_AST_BRIDGE_UNVERIFIED`. An admitted bridge needs its own grammar,
source-construction and independent-oracle proof before any lesson or exam may
use those expressions. The ledger does not presume every type-compatible
relationship must be admitted.

## Verification boundaries

These receipts establish source construction coverage for the existing typed
Boolean adapter. They do not record student instructional exposure, model
predictions, teacher decisions, neural learning, or delayed retention.
`training_authorized` and `student_exposure_measured` remain false.

Next work must resolve the cross-interpreter relationship contract, track
actual teaching and examination coverage against the same obligations, and
implement the five continuous learning-failure diagnostics. Integrate
instructional choices through the learned teacher rather than fixed mix
percentages. Keep the original student, native AdamW, teacher history, and
whole-checkpoint spiral graduation rules unchanged.
