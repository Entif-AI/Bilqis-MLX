# Typed integer curriculum and selective generated-test releases

**2026-10-15.** This is a source-bound curriculum-generation mechanism,
not another hand-authored numerical worksheet or modification to the frozen
Grade A 144/72 source inventory. It preserves the legacy PyTorch interpreter,
student and optimizer. The new research generator has not been admitted into
the currently active Grade A human training schedule.

## Change one variable

Copy `.env.example` to the ignored local `.env` and edit exactly one value:

```dotenv
BILQIS_INTEGER_MAX=3
```

`3` teaches and proposes tests over `0..3`. Changing the value to `9`
expands freshly sampled integer expressions and their permitted numeric
answers to `0..9`. Valid current values are `1..100`, bounded by the
source-attested `school.number.0` through `school.number.100` vocabulary.
An explicitly exported `BILQIS_INTEGER_MAX` overrides `.env` for one process.

The integer maximum is **not** a limit on the model's 222-token vocabulary,
and never rewrites a token ID or a learned embedding. It is an *instruction
and generation policy*, so it does not implicitly enlarge the tested space
of a sealed historical grade or activate new optimizer work.

## Tests regenerate on demand, never automatically

```bash
# Inspect exactly what is out of date without rewriting anything
npm run curriculum:tests -- --plan-tests=type:integer

# Rebuild every suite whose types depend on integer bounds
npm run curriculum:tests -- --regenerate-tests=type:integer

# Verify saved integrity, oracle truths, partitions, and current integer cap
npm run curriculum:tests -- --check-tests=type:integer
```

Optional `--seed=1234 --count=40` changes the source sample and number of
distinct expression families only when explicitly supplied to regeneration.
Each new teaching pass can sample varied source-attested exercises using a
new seed without changing persisted tests. A repeated regeneration with the
same seed, cap, and specifications is content-identical and idempotent.

Selectors operate on **type dependencies**, not filenames or an enumeration
of arithmetic test inputs. `type:integer` currently captures the following
generated families:

| Type-derived suite | Semantic contract |
|---|---|
| `integer.direct` | Number-producing arithmetic AST, direct typed numeral and original native `school.number.N` target |
| `integer.truth` | Equality from two Number operands to Boolean TRUE/FALSE |
| `integer.equivalence` | Symmetry of number equality, verified by both exact arithmetic oracles |
| `integer.inverse_negation` | Negation and double negation of number-derived Boolean statements, verified by the source Boolean NOT table |

`boolean.constants` is independent of integer bounds and stays **byte-for-byte
unchanged** when `type:integer` is selected. `type:boolean`, `all`, or
`family:<family-name>` are also valid selectors. Newly registered typed
families that depend on Number automatically participate in `type:integer`
regeneration without any change to the CLI.

## Provenance, partitions, durability

The original pinned 222-token catalog supplies type signatures for operators
such as `Number*Number->Number`, `Number*Number->Boolean`, and
`Boolean->Boolean`. The predecessor arithmetic source evaluates generated
ASTs and cross-checks an independent interpreter before a sample is admitted.
The integer cap bounds *every input operand, intermediate arithmetic result,
and direct answer*, not merely the output classifier. The generator composes
bounded arithmetic subexpressions rather than depending on a stored finite
list of questions. Positive equality claims and contrasting false claims
share one source identity, with distinct answer types and golds.

Source identity determines a stable train/development/proposed-sealed
partition by hash, independent of random seed and the integer cap. Therefore
rerunning a teaching pass does not silently turn a development or sealed
source into a teaching example. Exact teaching replay and independent
evaluation remain distinct; `sealed_proposed` results are not an admitted
grade examination and may not become a teacher reward.

Generated tests are stored under ignored `artifacts/semantic-tests/` in
content-addressed, immutable release directories. On-demand regeneration
builds a **new complete release** and publishes one `current.json` pointer
atomically. Every suite has a SHA-256 digest, source graph and interpreter
identity, a recorded seed, and a dependency state that includes integer_max
only if its type graph depends on Number. Older generated test releases are
retained for provenance; no large neural checkpoint is copied. Regenerating
only integer-dependent suites carries unrelated suites forward unchanged.

If the environment is changed without regeneration, the `--check-tests`
command and the local regression suite report `SEMANTIC_TEST_STALE` instead
of evaluating outdated bounds. Tests never silently rewrite themselves.
Corrupted suite bytes or source/answer inconsistencies fail closed.

## Important implementation boundaries

The generated numeric and equality prompts can be expressed through the
existing arithmetic AST and token codec. Negation/equivalence tests assert
typed logical laws from the original source graph; the independent Boolean
negation construction is **not yet admitted as a neural input codec**. No
neural model should be scored as having learned NOT from an oracle-only
metamorphic test.

The source-bound typed MLX adapter accepts a `numeric_active` target set
from the same integer cap while retaining the complete native-vocabulary
semantic-token objective and five-state evidence head. This is compatible
with the current FP32 embedding shape, but the live Grade A trainer is still
the existing binary-only recipe. A passing generator/assessment contract is
not proof that an actual student learned these primitives.

## Observe learning rather than only testing the generator

Run `npm run curriculum:learning-smoke` to initialize fresh **disposable**
MLX model weights and AdamW moments in memory, generate capped lessons from
the same typed source, then report source-training and independent development
performance before and after 100 optimizer steps. This command never opens
the real Bilqis student for training or changes its teacher/checkpoints.
The deterministic default at `BILQIS_INTEGER_MAX=3` was verified to improve
source performance from numeric `0/4` to `4/4`, full-vocabulary native token
`0/4` to `4/4`, and evidence `3/8` to `8/8`. Development improved from `0/1`
to `1/1` for both numeric and native-token output and from `0/2` to `1/2`
for evidence. This establishes a functioning neural acquisition path on a
small toy fixture, **not** statistically sound generalization, nor progress
by the actual human-owned student. Every seed and bound still needs adequate
coverage and independent qualification evidence before production claims.
