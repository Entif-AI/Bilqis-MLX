# Bilqis compositional curriculum: strict behavioral contract v1

**State:** DRAFT, awaiting independent reviewer and source-interface verification. No neural training or new grade authorization follows from this specification.
**Authority:** User's source-reuse / functional-composition directive and governing private issue [#336](https://github.com/socr8s/private-ip/issues/336).
**Sources:** Exact ten pinned GitHub implementations and four additional production candidates are indexed in [04_COMPOSITION_AND_UPSTREAM_REUSE_DECISION.md](04_COMPOSITION_AND_UPSTREAM_REUSE_DECISION.md). These requirements describe observable behavior independently of third-party implementation.

## 1. Scope and semantic type system

The service accepts an immutable semantic release, original curriculum IDs, source claims, typed operator bindings, and independent verification methods. It outputs verified construction witnesses, exam/lesson candidate plans, and explicit coverage debt. Actual model training and teacher-policy mutation are outside this service.

Key abstract value types:

~~~text
SemanticRef       = ID resolved through single code-native catalog
LessonRef         = preserved curricular lesson ID, distinct from SemanticRef
TokenIndex        = original model ABI index 0..221 (append-only beyond that)
Signature         = typed arguments, result, binder, and legal-world constraints
Expr[T]           = Reference | Apply | Bind | Transform (immutable syntax nodes)
LawRef            = registered law with applicability, preconditions, source claims
MethodRef         = executable strategy with typed applicability and proof method
Witness           = source-grounded expression, original+independent checks, lineage
WitnessResult     = VERIFIED | REJECTED(reason/evidence) | UNKNOWN(missing evidence)
DiagnosticResult  = observed finding, controls, teacher response, delayed outcome
~~~

Serialization MUST be deterministic for the same release and typed expression. Runtime callable object identity, sheet row position and editable display spelling MUST NOT enter witness identity.

## 2. Required behavior

| ID | Behavioral invariant | Falsifiable acceptance |
| --- | --- | --- |
| C01 | One code-resident catalog owns Bilqis semantic and lesson identities. Preserve all original 222 token indices and existing verified semantic refs. External sheets do not allocate domain IDs. | Historical mapping readback, collision rejection, sheet reorder without identity drift. |
| C02 | Resolve aliases once at boundaries into typed references. No production method branches on a grade/semantic display slug. | Rename labels; generated AST and oracle result remain identical. |
| C03 | Type-check operator arity, arguments, result, quantifier binding and source-world contracts before composition. Boolean result compatibility alone is insufficient. | Return distinct type/world/arity errors; no gold for an incompatible bridge. |
| C04 | Generic higher-order apply, curry, partial application, compose, lift, bind and source-admitted transform produce immutable inspectable expressions and may compile to existing executable backends. | Compose a new compatible synthetic predicate without changing a named-grade branch. |
| C05 | Preserve variable binding and capture avoidance, including lawful alpha-renaming in quantified expressions. | Equivalent scope/renaming outcomes; unsafe captures rejected. |
| C06 | Resolve interpreter and solver adapters by registered type traits and source-world support. No duplicated Boolean truth engines in the factory. | Swap compatible solver; AST and meaning digest unchanged, independent results agree. |
| C07 | Registered laws declare quantified preconditions, source references, transformation semantics and expected outcome relations. Prose labels do not confer law authority. | Universal false law yields counterexample/unknown, not an asserted gold. |
| C08 | Separate constructed, offered, selected, delivered, reassessed, retained and mastered evidence; these are not interchangeable. | Generation cannot create student-exposure or mastery receipts. |
| C09 | Discover potential composition and prerequisite relationships by typed unification plus source grammar/world constraints. Classify REQUIRED, PERMITTED, INAPPLICABLE, UNKNOWN with evidence. | Synthetic new primitive updates legal edges without bespoke generator edits. |
| C10 | Verify source expressions with pinned interpreter and independently implemented checking backend/oracle; verify typed gold, token ABI and record provenance. | Mutated gold/source/oracle/bytes fail closed. |
| C11 | Generate reproducibly varied lesson/exam programs from the same admitted semantic contracts; previously examined examples remain eligible for instruction. | Seed replay deterministic; different seeds give legal diversity; no permanent embargo. |
| C12 | Track complete coverage obligations separately from sampling budgets, including contrast, boundary, invalidity, constituent, property and lawful answer-mode cases. | Under-budget audit leaves specific visible coverage debt. |
| C13 | Preserve contradictions, false-law counterexamples, vacuous cases, unsupported operations and solver UNKNOWN as first-class evidence. | Zero evaluated cases never pass a universal check; timeouts are not proofs. |
| C14 | Support finite Boolean logic and first-order functions/relations/quantifiers only when source-attested adapters implement them; permit additional typed answer domains. | Exhaustive small-world independently scored fixtures. |
| C15 | Offer admissible teaching options; the inherited teacher selects through its learned policy. Never impose a per-grade instruction ratio from the compiler. | Synthetic teacher can choose any admissible option; selected is not counted delivered. |
| C16 | Implement the five user-defined failure signals from actual predictions, class baselines, delivered exposure and delayed outcomes with controls. | Each detector has positive/negative/no-data fixtures and teacher-facing findings. |
| C17 | Retain unresolved source-verified examination errors across sampled cohorts with fairness, resolution, starvation and bounded eviction receipts. | Fresh exam never silently erases unresolved prior failure. |
| C18 | Preserve full active-grade pass, two fresh weakest-three rounds, permissible temporary earlier-grade regression, ordered A-through-current replay and cumulative whole-checkpoint 100%. | Synthetic B/C/D grade-cycle and same-cohort tests. |
| C19 | Composition has no mutable access to actual FP32 student, native AdamW, champions or learned teacher state. Agents cannot initiate actual neural optimization. | Read-only API / frozen checksum / no optimizer writes. |
| C20 | Version all semantic meaning changes, generation recipes and source claims; invalidate affected dependent families without reinterpreting pinned historical checkpoints. | Alias-only, meaning-change and historic-readback mutation fixtures. |

## 3. Reusable higher-order method contracts

Methods are selected by registered source and type traits, NEVER by a list of current A/B slugs.

| Method | Preconditions | Generated evidence | Verifier |
| --- | --- | --- | --- |
| DIRECT_EVALUATION | Source-attested Expr[T], legal world | Typed direct question | Source interpreter plus independent oracle |
| BOOLEAN_LIFT | Admitted Boolean operator and Expr[Bool] arguments | Truth-controlled conjunction/disjunction/negation/etc. | Exhaustive finite model + source oracle |
| PARTIAL_APPLICATION | Typed function and bound valid arguments | Curried expression with remaining arguments | Direct vs curried evaluation equivalence |
| BIJECTIVE_RENAMING | Finite model and one-to-one onto relabeling without capture | Structurally different equivalent source worlds | Bijection precondition and independent gold |
| RELATION_REVERSAL | Registered relation traits and controlled facts | Directed/symmetric contrast witnesses | Predicate oracle, not universal flip assumption |
| MINIMAL_COUNTERFACTUAL | Typed mutable world with legal perturbation | Paired world with changed/preserved result | Source evaluator, world-difference checker |
| FINITE_QUANTIFIER | Finite model, supported binder and variable scope | Exists/forall/negated query families | Enumerated assignments / independent finite model |
| ALGEBRAIC_REWRITE | Source-attested algebraic law with preconditions | Equivalent or contrasting expression pairs | Solver counterexample search or exhaustive table |
| DECOMPOSE_RECONSTRUCT | Composed source-valid expression and independently mastered constituents | Operand probes plus composite reconstruction | Independent operand + whole-oracle checks |
| CONSTRAINT_PROPAGATION | Finite constraints and supported domain | Partial deduction, contradiction and explanation ledger | Constraint solver and independently checked model |
| INVALID_BOUNDARY | Candidate near type/grammar/world validity bounds | Explicit invalid case without fabricated gold | Parser/type/world rejection |
| DIFFICULTY_RAMP | Verified expression and prerequisite evidence | Introductory-to-composed teaching choices | AST complexity and later learning evidence |
| NEURAL_RULE_FIDELITY | Frozen model predictions with source-verified gold | Candidate learned-rule explanation and disagreements | Same-cohort independent observations, not source truth |
| GRAPH_PROPOSAL | Staged source/research concept relation | Proposed dependency, source-search obligations | Source admission required prior to any live use |
| SCOPED_CERTIFICATE | Claim, finite universe/budget and falsifier | Proof scope, counterexamples, vacuity status | Scope-aware checker, explicit UNKNOWN beyond bound |

## 4. Pure functional construction algebra

~~~python
# Interface sketch; names are resolved at the catalog boundary.
predicate = catalog.resolve(existing_predicate_ref)
operator = catalog.resolve(existing_operator_ref)

partially_bound = partial_apply(predicate, argument_positions={0: entity_a})
operand = partially_bound(entity_b)               # typed Expr[Boolean]
another = apply(predicate, entity_b, entity_c)    # typed Expr[Boolean]
expression = lift2(operator)(operand)(another)    # typed Expr[Boolean]

methods = method_registry.applicable(expression, release, source_world)
plan = coverage.compile(expression, methods)
result = verifier.run(plan, original_source_oracle, independent_backends)
~~~

Implementations MUST preserve the expression AST and source attachments across currying/lifting; do not serialize an opaque function closure. Typed world conversion requires a separately admitted source interpretation agreement.

## 5. Source-to-method trace

Research source IDs below are ledger pointers, NOT new semantic IDs. Exact source commits and files are recorded in specification 04.

| Research source | Used mechanism | Contract IDs |
| --- | --- | --- |
| S01 Logic Explained Networks | Neural-symbolic explanation and fidelity checking | C08,C16; NEURAL_RULE_FIDELITY |
| S02 REASON | Composable differentiable Boolean concept layers and rule extraction, separate research lane | C19; NEURAL_RULE_FIDELITY |
| S03 knights | Recursive logical expression semantics and finite model checking | C04,C10,C14; BOOLEAN_LIFT |
| S04 SymStep | Constraint propagation, contradiction explanation and incremental verified steps | C13,C14; CONSTRAINT_PROPAGATION |
| S05 DYNA-SKILL | Graph relation proposal and resumable discovery, not semantic admission | C09,C20; GRAPH_PROPOSAL |
| S06 AI Math Tutor | Formula/concept source curation to staged candidate catalog | C01,C11; source ingestion |
| S07 math-of-logic | Bounded truth/certificate scope, falsifier, vacuity and ledger | C07,C12,C13; SCOPED_CERTIFICATE |
| S08 Mathematical Logic Through Python propositional | Recursive evaluation, all-model truth tables and synthesis | C10,C14; BOOLEAN_LIFT |
| S09 Mathematical Logic Through Python predicates | Finite universe, functions, relations; linked evaluation methods are unfinished | C03,C14; FINITE_QUANTIFIER |
| S10 pylogic | Callable finite-model predicates registered by arity | C04,C06,C14; PARTIAL_APPLICATION |
| S11 SymPy | Symbolic logical connectives and rewriting | C06,C10,C13; ALGEBRAIC_REWRITE |
| S12 Z3 | Finite-model counterexample and satisfiability verification | C10,C13,C14; CONSTRAINT_PROPAGATION |
| S13 Hypothesis | Recursive property generation and shrinking | C11,C12,C20; mutation fixtures |
| S14 NetworkX | Dependency graph closure, cycle and invalidation | C09,C12,C20; dependency planner |

## 6. Acceptance suite

| Test | Expected literal outcome |
| --- | --- |
| A01 Legacy ID roundtrip | Every original token maps to its one canonical index; colliding binding fails; alias rename leaves ABI intact. |
| A02 Composition portability | Synthetic type-compatible operation composes under same methods without a new grade/semantic switch. |
| A03 World contract rejection | Cross-interpreter Boolean pair without source-approved translation has UNKNOWN_SOURCE_BRIDGE and no gold. |
| A04 False-law control | Directed-relation reverse does not assert a universal flip without controlled preconditions; counterexample or inapplicability produced. |
| A05 Independent oracle drift | Poisoned record/gold yields rejected witness; never eligible teaching. |
| A06 Changed type | Meaning revision invalidates only dependent generated plans; old release unchanged. |
| A07 Teacher freedom | Teacher-selected fraction may differ from prior fixed A/B allocation; selection not miscredited as delivered. |
| A08 Five diagnostic signals | Positive, negative and missing-data fixtures for each user's warning. |
| A09 Historical custody | FP32, AdamW, teacher, original token index and champion hashes unchanged in source-only proof run. |
| A10 Support unavailable | Missing external adapter/symbolic method returns UNKNOWN with exact method ID, not a guessed implementation. |

## 7. Implementation phase boundary

First implement the pure composition grammar and verifier **C01-C07 and A01-A04** on an existing fully source-verified finite-world Boolean slice. Do not refactor the trainer or admit another grade in that unit. Runtime integration follows tests of source provenance, method coverage, teacher options and the five diagnostics. The full feature is not complete until actual human-run evidence demonstrates retention and graduation.
