# PyTorch to MLX pedagogical parity: source-bound reconstruction

**Private research, 2026-10-15. Not a Grade A replacement or training release.**

This is a correction of an engineering regression, not an independent new
teaching theory. The MLX successor must inherit the predecessor's demonstrated
curriculum and assessment procedures, not merely its FP32 weights, AdamW and
teacher statistics. Refer to the actual source, not remembered descriptions.

## What source inspection established

| Requirement | Original School50 source | Existing admitted MLX Grade A | Corrected implementation |
|---|---|---|---|
| Direct typed output | `numeric_answer_contract.readout`, tied `school.number.0..100` embeddings; v10 directly teaches 0..3 | All 144 train and 72 exam rows have `TRUE`/`FALSE`; `grade_a_trainer._train_step` uses only logits `[:, :2]` | `pedagogical_parity` supplies `numeric_0_3`, the same 4-way tied-token head, **and a separate full-vocabulary native-token training target** for each source-oracled direct number |
| Lower-fidelity answer | Original five-state `MicroStudent.answer_ids` evidence output | Grade A constrains evidence to two states | Original 5-class head retained; TRUE/FALSE examples and inherited UNKNOWN/AMBIGUOUS rehearsal remain typed, never coerced into binary |
| Negative contrast | `small_domain_lessons.triplet` contains oracle-correct false counterexamples | Each binary predicate has negative rows but no direct-value companion | Each arithmetic source compiles direct result, true equality, and false equality with a different result |
| First acquisition criterion | v10 replays the **exact taught question IDs**, not a distinct unseen source | Fixed 72-item exam is disjoint from 144 teaching examples | Acquisition replay must be a literal subset of teaching rows; reserved development and sealed sources never gate first acquisition |
| Instructional variation | v10 `compile_batch` uses standard, structural-equivalence, minimal-counterfactual methods, six numeric + 36 relation + six old rehearse rows | Current adaptive teacher is inherited but only some policy dimensions affect Grade A lesson selection | `predecessor_teaching_batch` executes the **actual pinned v10 compiler**, converting all 48 rows to validated MLX answer castes |
| Numeric honesty | Four-way restricted result distinct from original unrestricted 101-way diagnostic | No direct numeric measure | `evaluate_rows` labels these independent readout scopes, never calling a 4-way result unrestricted mastery |

The previous student was about 91.5% correct on the older 1,150-item historical
rubric, but that statistic must not be presented as Grade A proficiency, or as
proof that importing teacher statistics alone transfers teaching competence.
The repeated roughly half-correct new Grade A exam results alongside near-perfect
training-row accuracy point to an acquisition/transfer defect worth prioritizing.
The source constructors for the current frozen train and exam do share their
six *binary* predicate definitions; therefore literal use of different
predicates has **not** been established as the cause.

## Versioned lesson contract

`bilqis.mlx.predecessor-pedagogy/v2` rebuilds the exact older 20 arithmetic
expression sources: 12 in `train`, four in `development`, and four reserved
`sealed`. The four original replay sources, ADD(0,0), ADD(1,0), ADD(1,1),
ADD(0,3), appear unchanged among the taught inputs. ADD(1,2) is an additional
taught expression. For each source, the **same arithmetic AST** generates:

1. A direct numeric answer, such as `ADD(1,2) -> 3` (4-way restricted numeral
   exercise), **also teaching a native output token** `school.number.3` against
   the *entire current 222-token semantic vocabulary*. Both targets share
   the same oracle-attested question, stable source ID and embedding row.
2. A valid proposition, `EQ(ADD(1,2),3) -> TRUE` (original five-state evidence
   caste).
3. A minimally changed, false proposition, `EQ(ADD(1,2),0) -> FALSE`
   (same evaluator and input contract; wrong answer selected by predecessor's
   deterministic `+1 mod 4` rule).

These are different *question/answer types* under one semantic source ID.
The oracle's exact output and both asserted truth values must agree with the
predecessor's independent arithmetic implementation. The original mathematical
syntax is tokenized using the model's 222-token catalog, not an invented
symbolizer or an unadmitted New Ithkuil wordform.

The teaching staircase is `NUMERAL_IDENTITY`, `DIRECT_ARITHMETIC`, then
`TRUTH_CONTRAST`. A source-bound **exposed acquisition receipt** from the
prior stage is necessary to consider the next stage ready. The numeral-identity
stage is merely an atomic *readout calibration* of 0..3, not proof that finite
set cardinality, successor or counting beyond three has been learned. Those
separate source-grounded prerequisites remain to be qualified. The current
compiler reports eligibility but does not issue such receipts itself.

One 48-item predecessor teaching fixture preserves six numeric, 36 current
relationship, and six historical rehearsal observations. The latter may have
`UNKNOWN` or `AMBIGUOUS` labels, exposing why a two-class replacement was not
pedagogically equivalent. **Four-way recognition is no longer the learning
ceiling:** six source-oracled direct answers also supervise selection of their
real number-token identities over all 222 current model tokens. The separate
101-number head remains an explicitly labeled diagnostic, not a claim of
acquired arithmetic competence across 0..100. Only 0..3 are taught in these
research fixtures; expanding the *target syllabus* needs verified prerequisites
and new source examples, but the *output ABI* is not restricted to 0..3.

The full-vocabulary head is a tied **single semantic-token readout**, not a
claim that the current model now generates arbitrary multi-token New Ithkuil
compositions. Additional direct target types and multi-token response
constructions need their own source-attested curriculum/oracle definitions.
The training adapter accepts additional explicitly typed direct outputs from
the catalog, including nonnumeric token identities, once a separate compiler
has established their source/oracle correctness. A synthetic test verifies
this interface, **not** the semantic correctness or admission of any new
entity-level lesson. It also accepts future independently attested numbers
0..100 without repurposing the restricted 0..3 answer head.
When append-only vocabulary growth admits new tokens, the full output head
must expand to the same size as the embedding table. A stale head fails
closed instead of silently ignoring newly admitted meanings.

The predecessor's actual `spiral_staged_runner._choose_instruction` UCB
strategy selector is also available through `predecessor_instruction_choice`.
It runs against a copy of the supplied teacher statistics and the SHA-pinned
old source. This establishes method-choice parity and non-mutation in a
fixture; it **does not** claim that the current MLX teacher now operates the
old lesson-method reward loop. That integration needs a separately evaluated
recipe because the existing new Grade A teacher currently observes a
different, training-source-only reward.

## Source and trust boundaries

The bridge verifies SHA-256 of the predecessor's original source files,
including arithmetic, numeric readout, batching, School50 engine and teaching
strategy implementation. It verifies the original FP32 checkpoint's SHA
`646d8590cf8fddb7b3c412ecead4ac185a0578f93baadf24e05f92dd15068a78`
and reads its embedded full 222-token graph with canonical digest
`57ab0a141a9bfc25c6da8d0568f14e0a8beaab2c0c3fd33931e51e2624a0b16f`.
Regenerating graph nodes from the current base catalog produces the same
token order but a *different full contract hash*; identical IDs do not prove
semantic or optimizer provenance parity. No model or source bytes are written.

The new `typed_answer_training.py` uses only the existing tied embedding
matrix and original MLX forward path. Source-bound direct numeral rows
carry `native_output: {identity: school.number.N, token_id: <catalog-index>}`
and generate **both** a restricted four-way numeric loss and a full-catalog
semantic-token loss. Evidence assertions retain a separate five-state loss.
The three cross-entropies are averaged **per caste**, preventing numerous
TRUE/FALSE examples from drowning out direct construction. Full-vocabulary
output supervision exerts gradients on competing non-number embeddings, too;
retention and distillation safeguards therefore require actual qualification
before a real-student curriculum release. Tests verify these losses, both
numerical heads against PyTorch, complete historic 48-row fixtures, source
binding failure cases, and safe handling of vocabulary expansion using only
disposable model arrays. No agent step affects the real student.
The loss gathers the correct logit by token ID rather than allocating a dense
vocabulary-by-vocabulary one-hot matrix; this avoids quadratic one-hot memory
growth as the admitted semantic catalog expands.

## Acquisition, selection, and qualification are separate

**Exposed acquisition:** Replayed examples are identical to teacher inputs;
the first evidence is that a model learned what we taught. Exact overlap is
intentional, visibly labeled, and not independent generalization.

**Developmental candidate selection:** Use source-owned, separately
identified developmental probes *after* exposed acquisition. A development
score can nominate a per-capability best but cannot establish sealed grade
qualification. We must decide admission rubrics and which best scores are
allowed to guide the teacher before wiring this into the live trainer.

**Sealed qualification/transfer:** Reserve genuinely independent identities,
already taught operations, and admissible answer castes; evaluate a whole
student on the whole approved grade rubric at one checkpoint. This result
must not become the recurrent candidate-selection reward. The current legacy
Grade A trainer **does** repeatedly use its frozen 72-item rubric to select
capability-best checkpoints; that leakage remains in the existing accepted
experimental path, not in this new isolated research proposal.

No existing teaching manifest, teacher state, model, optimizer, checkpoint or
Grade A frozen 72-item exam was changed. This is deliberately not marked
`training_authorized` or `qualification_authorized`. It is **not** safe to
label the prototype as a successful repaired Grade A neural curriculum.

## Verification and next release gates

Run `npm run curriculum:parity` for a source-verified, read-only summary that
does not print reserved sealed answers. The regression tests establish
source partition identity, exact taught replay, multiple answer castes,
false-counterexample correctness, prerequisite gating, full original graph
binding, five-state historical rehearsal, PyTorch-to-MLX readout agreement,
and disposable optimizer compatibility. A later explicit release must still:

- Resolve finite-set counting and other prerequisite evidence rather than
  treating a numeral-token readout as semantic mastery.
- Design and independently verify typed direct construction for other Grade A
  primitives such as entity, mapping and set answers where the source ABI
  permits it. Do not force a numeric answer caste onto non-numeric relations.
- Integrate an admitted mixed-caste teaching and developmental-assessment
  plan into a versioned *new* training recipe with safety/provenance tests;
  preserve the existing current student's complete FP32 and AdamW state.
- Separate developmental best-score retention from unconsulted sealed
  qualification and independent transfer measurement. Freeze and authorize
  a new rubric rather than editing the already accepted 72-item manifest.
- Compare the complete old teacher's policy credit, example sampling,
  old-grade rehearsal, preview and distillation functions before claiming
  equivalence of the new long-form training method.

**Operator authority:** only the human may launch or resume the real neural
trainer. No training or exam release is implied by passing this source-level
conformance suite.
