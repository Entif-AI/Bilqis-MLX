# Bilqis MLX: upstream-grounded compositional curriculum architecture

**Status:** RECOMMENDED DESIGN FOR HUMAN REVIEW, 2026-10-16. Not approved as an executable architecture, release or migration. No student/teacher/optimizer behavior has changed.
**Governing correction:** User's 2026-10-16 interruption: inspect the ten supplied GitHub implementations and exploit functional composition, currying, higher-order operations and existing test/evaluation engines before building a new semantic framework. This succeeds the earlier three homegrown AST/factory/module-tree sketches in this directory.
**Private authority perimeter:** Protected IPR-0220 and [socr8s/private-ip#336](https://github.com/socr8s/private-ip/issues/336). No private Bilqis implementation details may be projected into public repository comments or code without screening.

## 1. Revised design decision

The desired system is **a typed, inspectable composition of existing semantic functions and reusable verification methods**, guided by the original curriculum identifiers and an authoritative code-resident semantic catalog.

The catalog owns the identity-to-meaning-to-implementation *binding*. It does **not** need to own implementations of every Boolean operator, logical evaluator, finite-model solver, graph algorithm, test generator, or transformer. Where adequate licensed packages exist, import them behind small adapters. Do not construct a parallel first-order logic engine or general solver just because the curriculum is AST-driven.

**Original Sheet identity is not disposable.** Adopt the verified Token Atlas's original 222 numeric token identities, semantic symbol identities, LESSON identifiers, and existing capability references as historical bindings in the code-resident catalog. Do not invent alternate opaque replacements merely to achieve abstraction. New future identities are assigned only by an approved catalog transaction; sheet row coordinates and prose are provenance, not identifiers. Aliases and semantic revisions remain explicit and versioned.

**A useful distinction:** Executable functions can be *composed*; persisted compositions must remain *inspectable*. A raw closure assembled through functools.partial may evaluate correctly but cannot, by itself, prove what source semantics, token identity, world constraints, or transformation laws it used. Keep a thin typed expression/provenance spine; compile that spine into existing executable backends. The spine should hold references and applications, not reinvent the logical operators.

The governing equation is:

~~~text
Sheet-origin canonical IDs + typed semantic bindings + source-verified rules
    -> reusable symbolic expressions and higher-order test methods
    -> constrained generator recipes + independent solvers/oracles
    -> verified construction and property receipts
    -> teacher-selectable lessons / cumulative complete exams
    -> observed student outcomes and diagnosed future teaching needs.
~~~

## 2. Ten GitHub candidates: audited source-level dispositions

Entries below are from the actual linked source and GitHub license metadata, with default-branch commit identities captured on 2026-10-16. A GitHub repository without a declared license is **not automatically available for copying or importing into another codebase**. A named outcome is a proposed reuse decision, not a claim of tested compatibility.

| User-supplied source (pinned commit) | Verified implementation | Direct-reuse judgment | Caveat |
| --- | --- | --- | --- |
| [Logic Explained Networks](https://github.com/pietrobarbiero/logic_explained_networks/tree/5d36cebeead6958490cc27f797c331468eb9238b), Apache-2.0 | [lens/logic/explain.py](https://github.com/pietrobarbiero/logic_explained_networks/blob/5d36cebeead6958490cc27f797c331468eb9238b/lens/logic/explain.py) extracts local/global explanations; [eval.py](https://github.com/pietrobarbiero/logic_explained_networks/blob/5d36cebeead6958490cc27f797c331468eb9238b/lens/logic/eval.py) tests them. | Candidate **optional research/diagnostic adapter** for assessing whether a learned decision resembles a symbolic rule. | PyTorch model-oriented; rule explanation is not independent source gold and does not replace MLX's student. |
| [REASON](https://github.com/Mr-TalhaIlyas/REASON/blob/3c178c6cf0a80fbd97c9855b480a80f80f7677fa/model/crl/components.py), MIT | Concrete differentiable [ConjunctionLayer/DisjunctionLayer/UnionLayer](https://github.com/Mr-TalhaIlyas/REASON/blob/3c178c6cf0a80fbd97c9855b480a80f80f7677fa/model/crl/components.py#L302-L455), Binarizer, gradient grafting, and rule extraction. | **Research reference** for logically structured neural representations; evaluate in an isolated experiment only if ever authorized. | Copying its PyTorch layers into the intact FP32+AdamW MLX student is a neural architecture change, not a curriculum fix. |
| [knights](https://github.com/SavinRazvan/knights/blob/171ffe34ee2fed5d70268d7fb0aac6e8064f7885/logic.py), MIT | Composable Sentence/Symbol/Not/And/Or/Implication/Biconditional and [model_check](https://github.com/SavinRazvan/knights/blob/171ffe34ee2fed5d70268d7fb0aac6e8064f7885/logic.py#L228-L264). | **Small reference/optional adapter** for a bounded Boolean vertical slice. | No typed predicates, quantifiers, source-linked semantics or general generation infrastructure. Prefer established reusable Boolean backends for production. |
| [SymStep](https://github.com/Zangir/SymStep/tree/8b7091c67b07d578878063bc3b0109365dc7341b), MIT | [Constraint/Problem/Engine/Ledger](https://github.com/Zangir/SymStep/blob/8b7091c67b07d578878063bc3b0109365dc7341b/graphstep/engine/core.py), domain propagation, constraint primitives, IR and stepwise contradiction feedback. | **High-priority constrained-verification adapter candidate**. Reuse bounded IR/constraint-engine behavior after proving it against independent source cases. | The experiment runner uses prompts and a Claude CLI, which are not needed for authoritative lesson generation. Constraint proof is scoped to an encoded model, not automatically all New Ithkuil semantics. |
| [DYNA-SKILL](https://github.com/jongwonryu/dyna-skill/blob/e2c5561a7aa46ce3b290e25eea3debb950ffc942/scripts/generate_graph.py), no declared license | API-driven graph relation proposals, head/tail expansion, generated dynamic relation names, saved state. | **Research inspiration only** for candidate relation discovery and resumability. | Generated language-model relation proposals are not source-verified semantics. No verified permission to copy code. |
| [ai-math-tutor formula_book](https://github.com/namanshukla93/ai-math-tutor/blob/d5392076c66870925345a5e0ac3be9d0f0bfe6b2/formula_book.py), no declared license | Static MATH_FORMULAS and REASONING_CONCEPTS dictionaries. | **Human-content reference only**. | It does not compile, evaluate or independently check those formulas. No verified permission to copy content/code. |
| [math-of-logic](https://github.com/ApplePiesFromScratch/math-of-logic/tree/94526ce6ee110d1464c7157c1bf994dbbba46b25), MIT | [PROCESS.py](https://github.com/ApplePiesFromScratch/math-of-logic/blob/94526ce6ee110d1464c7157c1bf994dbbba46b25/pl/PROCESS.py) defines constrained values/operations, scoped certificate, falsifier, ledger, and migration logic. | **Adopt evidence-scope and falsifiability practices**, optionally source-specific certification adapters. | Its certify is scoped to a declared finite grid; does not prove arbitrary logical correctness or serve as a general calculus backend. |
| [Mathematical Logic Through Python: propositions](https://github.com/hjbolus/Mathematical-Logic-Through-Python/blob/cc7fe8275545bec0236c007670f154b1ecf388c3/propositions/semantics.py), no declared license | Recursive Boolean formula evaluation, all-model enumeration, truth-table analysis, tautology/satisfiability, formula synthesis. | **High-value reference** for exact finite propositional semantics and exhaustive checking. | Educational source has no repository license; use licensed alternatives or obtain permission rather than copying the implementation. |
| [Mathematical Logic Through Python: predicates](https://github.com/Datamance/Mathematical-Logic-Through-Python/blob/99b7ebf3c8a6d191a6d67fdd296e5135623b1531/predicates/semantics.py), no declared license | Model structure includes finite universe, constants, n-ary relations, function tables. | **Model/design reference only**. | evaluate_term, evaluate_formula and is_model_of are unfinished textbook exercise placeholders in the linked file, so it is **not a working oracle**. |
| [pylogic](https://github.com/kakwa/pylogic/blob/46b6cfecca7ccb74b8caae054464d8092b40c97b/src/pylogic/logic.py), no declared license | [Context.setPredicateFunction](https://github.com/kakwa/pylogic/blob/46b6cfecca7ccb74b8caae054464d8092b40c97b/src/pylogic/logic.py#L238-L260) registers callable predicates with arity, finite-domain checking and quantifiers. | **Excellent direct precedent for the desired functional registration API**. | Old PLY lexer/parser design and string-converted domain objects; no verified reuse license. Reimplement only the narrow API shape if no approved dependency exists. |

### Established licensed tools to evaluate before writing anything similar

These are additional, stronger candidates for the actual reusable production components:

| Tool | Specific role, not blanket adoption | License/source |
| --- | --- | --- |
| [SymPy Boolean algebra](https://github.com/sympy/sympy/blob/master/sympy/logic/boolalg.py) | Symbolic Not/And/Or/Xor/Implies/Equivalent; algebraic simplification, propositional equivalence and counterexamples. | SymPy's [BSD-style license](https://github.com/sympy/sympy/blob/master/LICENSE). |
| [Z3 solver](https://github.com/Z3Prover/z3) | Generate or disprove finite/domain-constrained candidate laws; find satisfying/counterexample interpretations. Constrain timeout and semantics exactly; record SAT/UNSAT/UNKNOWN. | [MIT](https://github.com/Z3Prover/z3/blob/master/LICENSE.txt). |
| [Hypothesis](https://github.com/HypothesisWorks/hypothesis) | Declarative property-based source/AST and compiler tests, including recursive structured generation and shrinking of failing examples. | [MPL-2.0](https://github.com/HypothesisWorks/hypothesis/blob/master/LICENSE.txt). |
| [NetworkX DAG algorithms](https://networkx.org/documentation/stable/reference/algorithms/dag.html) | Dependency closure, topological ordering, cycle rejection and affected-subgraph invalidation; no homegrown graph algorithms. | [BSD-3-Clause](https://github.com/networkx/networkx/blob/main/LICENSE.txt). |

Version/packaging/Apple Silicon compatibility of these four and any selected SymStep adapter remains **unverified locally**. Include a disposable dependency/license/performance spike before adding a production dependency.

## 3. Architecture: register the original identifiers, compose functions, preserve interpretable ASTs

### 3.1 Catalog binding contract

The only domain-level registry must map *existing* semantic and lesson identifiers to typed implementation and source contracts. First import reconciles the original Sheet IDs against pinned legacy token graph and current admitted course. Later changes are reviewed code-catalog transactions.

~~~python
# PSEUDOCODE: API direction, not implemented.
SemanticBinding(
    original_id=ExistingSemanticRef,       # e.g. original Token Atlas identity
    signature=FunctionType,
    source_claims=tuple[SourceRef, ...],
    oracle=CallableRef,                    # independently implemented
    implementation=BackendOperatorRef,     # SymPy/Z3/source adapter/etc.
    laws=tuple[RegisteredLawRef, ...],
    valid_worlds=WorldContractRef,
)

LessonBinding(
    original_lesson_id=ExistingLessonRef,  # preserve initial curriculum ID
    objectives=tuple[SemanticRef, ...],
    prerequisites=PrerequisiteExpr,
    generation_recipes=tuple[RecipeRef, ...],
    valid_answer_types=tuple[TypeRef, ...],
)
~~~

An external grammar/source remains the *truth evidence* for a New Ithkuil interpretation. The code AST remains the *machine-authority* for which interpretation Bilqis has versioned and admitted. Neither declares the source true merely by referring to it.

### 3.2 Higher-order constructor algebra

Operators combine typed expression objects, not arbitrary strings. Think of the expression layer as a minimal **provenance-carrying syntax wrapper** around imported backend expressions.

~~~python
# PSEUDOCODE: names are obtained once from the catalog, not duplicated in tests.
identity = catalog.resolve_legacy_symbol("micro.compare.EQ")
parent   = catalog.resolve_legacy_symbol("micro.relation.PARENT")
link     = catalog.resolve_legacy_symbol("micro.relation.LINK")
xor      = catalog.resolve_legacy_symbol("cogal.operator.XOR")

# Apply/curry a typed relation: source-world and variable binding are preserved.
parent_of_a = partial_apply(parent, slot=0, value=entity_a)
p = parent_of_a(entity_b)                    # Expr[Boolean]
q = apply(identity, entity_a, entity_a)     # Expr[Boolean]

# lift2 produces an inspectable AST application, never just an opaque closure.
combine_xor = lift2(xor)                    # Expr[Bool] -> Expr[Bool] -> Expr[Bool]
composed = combine_xor(p)(q)                # Expr[Boolean]

# A property generator is itself higher-order and source-configurable.
law_tests = properties.for_expression(composed)
plan = law_tests.under(source_worlds).with_methods(admitted_property_methods)
receipts = verification_backends.check(plan)  # bounded, source-attested
~~~

The module implementing lift2/currying need not know XOR, PARENT or grade B. The catalog resolves IDs and types once. The functions produce expression nodes (reference, apply, bind, transform) which can be deterministically serialized, hashed and lowered to SymPy/Z3/finite-world interpreters. The AST does *not* reimplement their solver algorithms. A source-binding mismatch must fail when lowering to the chosen backend, not silently coerce a world.

For source-oriented New Ithkuil morphology or typed non-Boolean semantics, register a different interpreter/backend. Boolean backends cannot approve grammar or pronunciation semantics.

### 3.3 Methods are higher-order functions with proof obligations

One compositional registry provides **test/lesson method factories** keyed by semantic traits and types, not named grades:

| Reusable method | Accepted typed input | Generates | Independent check |
| --- | --- | --- | --- |
| direct-evaluation | source-attested Expr[T] | simple source example and typed answer | source oracle and corroborating backend |
| Boolean composition | Expr[Bool] with lawful connectives | combinations with controlled truth patterns | truth-table enumeration + source oracles |
| semantic-equivalence | Expr[T], admitted law | transformed equivalent/contrastive pair | SAT/SMT counterexample or finite exhaustive check |
| bijective renaming | finite-world referent-bound Expr[T] | fresh consistent entity names | interpreter invariance plus explicit preconditions |
| relation reversal | directed/symmetric typed relation plus world witness | query role reversal | oracle outcome, **not** a universal flip assumption |
| set/function counterfactual | membership/mapping with source world restrictions | minimally changed source worlds | scoped counterexample and type validity |
| quantifier expansion | finite nonempty model with typed predicate | exists/forall instances and negations | independently evaluated finite-model truth |
| associative/commutative/De Morgan | admitted operator and proof-backed law | equivalent expression families | solver or exhaustive truth table, source constraints |
| decomposition/reconstruction | composed expression with admitted constituents | direct operand review + recomposition | separately scored constituents and whole |
| source syntax roundtrip | approved grammar/parser/serializer | legal structures and invalid-boundary cases | independent parse/encode agreement, where available |

Each method exposes applicability, law/source references, construction strategy, independent checker(s), coverage dimensions, proof depth, and failure modes. It returns versioned **VerifiedWitnesses** or explicit **CoverageDebt**. A method that cannot be proven for a new semantic family stays inapplicable/unresolved; no string-name dispatch or guessed gold.

**Important:** a technique's mathematical validity is different from whether the learner can absorb it at its current stage. Eligibility belongs here; lesson order and teacher decisions belong to the curriculum/learning layer.

### 3.4 Compact interface, few meaningful packages

Start with *five* internal boundaries, not the enormous new directory tree previously sketched:

~~~text
bilqis_mlx/
  semantics/        canonical ID bindings, typed expression references, source claims
  composition/      small pure higher-order combinators and property recipes
  verification/     adapters to existing licensed backends + source oracle agreements
  curriculum/       AST-derived lesson/exam plans, coverage obligations, spiral contract
  learning/         existing teacher/trainer/student integration, diagnostic receipts
~~~

Existing compatibility, saved-checkpoint, source and dashboard modules may remain in place until migration demonstrates a genuine ownership boundary. Do not move all 46 modules simply to make the repository look organized. Delete duplicate semantic dispatch **as its callers are migrated**; measure module/interface count and reader load after each vertical slice.

## 4. Source, proof and sampling: what the engines may claim

Construct a consistent finite world through the *existing pinned source adapters*. Compose the AST expression, then compare:

1. Source-attested semantic oracle of the actual encoded expression.
2. Independent model/solver interpretation of the same **explicitly constrained** world and typed formula.
3. Where useful, another independent implementation of the declared property.

The systems must not share one undocumented handwritten truth table and then call agreement independent. Model-conversion witnesses have explicit source identity, type and losslessness checks. A correct SymPy XOR truth table does not prove that a particular legacy micro/development world encoding is lawful or that new linguistic roots are source-attested.

When a solver reports UNKNOWN/timeout, an interpreter disagrees, or a law lacks a source claim, the result is **UNRESOLVED**, not a gold label. For a false law, preserve a counterexample. For scoped exhaustive proofs, preserve the enumerated finite universe and scope digest. Do not equate thousands of randomized samples to universal proof.

Hypothesis is primarily a **verification generator** and shrinker. Use one canonical typed generation-plan representation to also construct reproducible **instruction** samples with an explicitly recorded seed and version. The live trainer need not depend on Hypothesis's test runner, hidden random state, or database. Coverage obligations are compiled before sampling; unsampled required cells remain visible debt instead of disappearing under a sampling budget.

## 5. Keep pedagogy and checkpoint contracts intact

The goal is to replace **how semantic exercises are constructed**, not to redesign the student's identity or re-bias the teacher.

- The inherited learned teacher chooses from independently verified, source-valid lesson options; do not force an A/B mix, hard-code per-grade repair ratios, or override its selected policy.
- Source-verified failed examination items remain eligible for subsequent instruction; no permanent exam holdout. Record *delivered* exposure versus offered options and unresolved failures across cohorts.
- Existing Grade A and B admitted releases, 222 token positions, model FP32 weights and own AdamW, grade champions, teacher votes and immutable examination receipts retain their meanings.
- Six-to-nine-capability grade organization and Billy Madison spiral remain. New-grade acquisition may temporarily harm earlier grades; full same-checkpoint current grade 100% and cumulative prefix 100% remain the advancement standard.
- Build the five user-defined signals against real predictions, baselines, actual delivered teaching and delayed assessments. The factory makes valid options; measured learning rather than green construction tests determines effectiveness.
- No agent may run actual student optimization. Human-run, disk reserve, crash/event custody and checkpoint retention boundaries remain unchanged.

## 6. Minimal, testable implementation sequence

### Gate 0: external dependency and license proof

Pin upstream commits and inspect each relevant interface, license and dependency tree. Try **licensed** SymPy Boolean operations, Z3 finite constraints, Hypothesis recursive generation, and NetworkX DAG closure, plus a *disposable* SymStep engine adapter if it adds value beyond Z3. Record actual compatibility, runtime costs and which component is redundant. Fork/copy no unlicensed code.

**Deliverable:** decision table with VERIFIED / REJECTED / CONDITIONAL dependency outcomes and a reproducible executable mini-spike. An upstream package is not admitted merely because its README looks ideal.

### Gate 1: reconcile original Sheet IDs into one code catalog

Import the existing Token Atlas IDs 0..221, original semantic symbols, LESSON references and accepted A/B capability aliases **without minting alternative identities**. Check against pinned graph hashes and a frozen copy of current student metadata. Move Sheet count assertions into immutable historical compatibility fixtures; future general tests reason over catalog invariants.

**Deliverable:** catalog lookup map and round-trip compatibility tests. Sheet row move/rename changes external provenance only; a true meaning change causes explicit versioned review.

### Gate 2: compositional Grade A/B vertical slice

Choose already source-verified Boolean input predicates (EQ, PARENT, LINK) and compose them with selected Grade B operators using lift, curry and partial application. Emit inspectable AST, source-world witnesses, solver/finite truth cases and independently scored golds. Leave original B runtime path unchanged for comparison.

**Deliverable:** seed-reproducible generated lesson/test property families for these existing semantic refs with **zero Grade B-specific branches** in the composition or verification engine. Detect false metamorphic claims using deliberately poisoned witness fixtures.

### Gate 3: expand methods, not bespoke capability code

Register generic relation reversal, bijective renaming, counterfactual, quantifier, source syntax and prerequisite decomposition methods only where source proof supports them. Require law applicability, typed argument/result compatibility and source-world translation witnesses. Drive AST-derived obligation coverage and independent missing-edge/debt reports.

**Deliverable:** adding a synthetic capability, alias change, typed meaning revision and an unfamiliar grade changes catalog data and generated dependent artifacts but **does not require editing core lesson or test method source**.

### Gate 4: shadow construction and teacher-facing plans

Produce new-source generated teaching/exam plans and five-signal diagnostic receipts side-by-side with the current trainer on disposable/frozen data. Bind old release digest and source cohort for identical checkpoint comparisons. The teacher may inspect and choose valid plans only after its selection/policy compatibility has been proven; no assistant-imposed quotas.

**Deliverable:** a complete, same-cohort A+B shadow exam with preserved old-rubric compatibility, teacher option visibility, diagnostic negative controls and zero actual optimizer steps.

### Gate 5: adopt, then consolidate

Only after gates 0–4 prove behavior and receive architectural approval, route live **human-invoked** training through the verified factory. Migrate callers and remove duplicate Grade-A/B semantic dispatch. Preserve and verify state/AdamW/teacher/event recovery. Reorganize the directory *as a consequence* of established boundaries, not as phase-one cosmetic work.

**Deliverable:** reproducible release receipt, complete source-to-semantic-to-lesson-to-test trace, memory/disk proof, full incumbent/challenger scoring, and human-measured learning after an explicit run.

## 7. Decisive tests for whether this is genuinely generic

1. Register **one new type-compatible primitive** through the catalog, prove it source-valid, and show automatically discovered *legal* composition/test families without a per-capability source edit.
2. Register a new primitive with incompatible source-world representation. It must produce explicit UNVERIFIED_BRIDGE debt, not unjustified combinations or fake gold.
3. Rename/reorder a Sheet row or a display label. The same canonical semantic identity, ABI and old released scores must survive.
4. Change a semantic law's type/contract. Only actual dependent generated plans invalidate; pinned old releases remain immutable.
5. Substitute a false axiom (for example, universally asserting reversed directed queries flip truth). The independent checker must find a counterexample or fail a source precondition.
6. Generate original-vs-composed Boolean tests with a real variety of input truth patterns and non-isomorphic worlds; construction coverage is reported separately from measured student proficiency.
7. A previously failed assessment witness is available to the teacher for future instruction, and evidence records if it was actually used.
8. Five real learning-warning tests distinguish no data, chance performance, prediction collapse, transient gains, broken prerequisite exposure, and overly complex introductions.
9. Earlier-grade temporary regression is visible and tolerated during acquisition, but the same-checkpoint 100% cumulative gate cannot be bypassed.
10. The original 222 model token slots, full FP32+own AdamW, teacher state and grade-vote semantics remain byte-identifiable and recoverable.

## 8. Why this wins over the previous proposed architecture

| Decision | Rejected alternative | Rationale |
| --- | --- | --- |
| Compose existing typed operations | Bespoke source-oracled builder for every A/B predicate and Boolean operator | Reusable methods do not know semantic names, and third-party Boolean/constraint engines already exist. |
| Thin inspectable AST + executable combinators | Raw Python closures as the only semantics OR elaborate invented new general logic AST | Closure-only representations cannot preserve source/ABI dependencies; a full handwritten logic engine repeats upstream work. |
| Original sheet-derived IDs bound in code | New opaque IDs for everything and alias-mapping the old vocabulary | Existing semantic and lesson identities must not be casually replaced; only future additions require allocation. |
| Solver-backed, independent property methods | Writing asserted 'gold' or effect labels inside SemanticLaw strings | The law expresses a typed claim to check; trusted evaluators provide counterexamples and verified scope. |
| Teacher chooses eligible options | Engineer-selected grade ratios and static anti-forgetting gates | Preserves the student's curriculum ecology and the teacher's learned policy while maintaining measured coverage debt. |
| Small vertical proof before package split | Predefine a 40-file target repository tree and migrate immediately | Design boundaries follow proven interfaces, not speculative module sprawl. |
| License-pinned adapters | Copy any attractive public GitHub sample | Provenance, permission, and compatibility are part of reusability. |

**Recommendation:** Accept this *composition-first, upstream-reuse* direction as the architectural checkpoint for review. Do **not** ratify any particular third-party runtime dependency or semantic rule until its scoped executable proof exists. The next authorized action after review should be Gate 0 and Gate 1, not more named Grade B source patches or live student training.
