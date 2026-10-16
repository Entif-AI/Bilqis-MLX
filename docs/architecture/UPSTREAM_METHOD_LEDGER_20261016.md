# Upstream mechanism ledger: Bilqis generative curriculum

**Status:** RESEARCH / DESIGN INPUT v0.2, updated for the user's curriculum-scope correction on 2026-10-16. None is an adopted Bilqis dependency or neural architecture change by appearing here.
**Derived contract:** [CLEANROOM_COMPOSITION_CONTRACT_20261016.md](CLEANROOM_COMPOSITION_CONTRACT_20261016.md).
**Source request:** Protected issue #336, user comment 6210595466; scope correction in progress comment 6211375269. This ledger records behavior, potential use, scoped tests and implementation-specific failure cases, not a requirement to prove general logic or all of New Ithkuil.

**Educational objective:** In the first grades we prescribe a simplified finite-world interpretation of the target concept, generate many meaningful variations, and assess whether Bilqis has learned it. A coherent curriculum-local evaluator can score these exercises. Stronger solver proofs are tools for particular investigations or future claims, not a universal admission requirement.

## Supplied implementations

| ID | Source at inspected commit | Source-grounded behavior | Bilqis method role | Reuse disposition |
| --- | --- | --- | --- | --- |
| U01 | [Logic Explained Networks](https://github.com/pietrobarbiero/logic_explained_networks/tree/5d36cebeead6958490cc27f797c331468eb9238b), Apache-2.0 | Neural concept/explanation interfaces expose local and global logical explanation formulas. `lens.logic.eval.test_explanation` measures agreement with labeled predictions. | Optional explanation/fidelity diagnostics over learned behavior, never semantic gold. | Adapter candidate, research lane; requires MLX/tensor-API evaluation. |
| U02 | [REASON](https://github.com/Mr-TalhaIlyas/REASON/blob/3c178c6cf0a80fbd97c9855b480a80f80f7677fa/model/crl/components.py), MIT | PyTorch differentiable concept binarization, conjunction/disjunction/union layers and symbolic rule extraction. | Research reference for concept compositionality and neural explanations. | Isolated neural experiment only; no replacement of current MLX student/AdamW. |
| U03 | [knights](https://github.com/SavinRazvan/knights/blob/171ffe34ee2fed5d70268d7fb0aac6e8064f7885/logic.py), MIT in `LICENSE.txt` | Sentence constructors compose Boolean symbols/connectives; recursive evaluation and model checking traverse all truth assignments. | Boolean expression/finite-model evaluator pattern; bounded adapter possible. | Small licensed source or clean typed adapter; no finite predicates or general lesson-generation engine. |
| U04 | [SymStep](https://github.com/Zangir/SymStep/tree/8b7091c67b07d578878063bc3b0109365dc7341b), MIT | Experiment runner checks stepwise deductions against a mutable possibility state. Separate `graphstep/engine/core.py` implements finite-domain constraints, propagation, search, removal ledger and contradiction evidence. | Generate bounded teaching worlds, narrow candidate choices, and explain model-specific feedback. | Consider the constraint engine selectively; validate only the operations we actually use. Do not mistake consistency for entailment **if** asking it to prove a deduction. |
| U05 | [DYNA-SKILL](https://github.com/jongwonryu/dyna-skill/blob/e2c5561a7aa46ce3b290e25eea3debb950ffc942/scripts/generate_graph.py), standard root license not found | Generates head/relation/tail chains through model prompting and saves generation state; later processes link two triples. | Discovery of candidate semantic relations or pedagogical contexts, with explicit proposal provenance. | Rebuild independent behavior if needed; generated relations are unverified hypotheses. |
| U06 | [ai-math-tutor](https://github.com/namanshukla93/ai-math-tutor/blob/d5392076c66870925345a5e0ac3be9d0f0bfe6b2/formula_book.py), standard root license not found | `MATH_FORMULAS` and `REASONING_CONCEPTS` are declarative content tables; no formula solver/evaluator in linked module. | Candidate math-law source/index for reviewed typed semantics. | Research/content reference only; no runtime backend to import from this file. |
| U07 | [math-of-logic](https://github.com/ApplePiesFromScratch/math-of-logic/tree/94526ce6ee110d1464c7157c1bf994dbbba46b25), MIT | Constrains legal values and operations, evaluates bounded scopes and records costs/lineage. | Record which stipulated world and rules led to an exercise and its answer; support stronger checks as necessary. | Reuse scoped-record patterns; no general logic solver needed for early lessons. |
| U08 | [Mathematical Logic Through Python: propositions](https://github.com/hjbolus/Mathematical-Logic-Through-Python/blob/cc7fe8275545bec0236c007670f154b1ecf388c3/propositions/semantics.py), standard root license not found | Recursive formula evaluation, truth assignments, tautology/contradiction/satisfiability checks and formula synthesis. | Finite propositional-model verification, Boolean test construction and counterexample checks. | Behavioral reference; licensed modern solver preferable for production. |
| U09 | [Mathematical Logic Through Python: predicates](https://github.com/Datamance/Mathematical-Logic-Through-Python/blob/99b7ebf3c8a6d191a6d67fdd296e5135623b1531/predicates/semantics.py), standard root license not found | Universe, constants, n-ary relations and function interpretation model; linked `evaluate_term`, `evaluate_formula`, `is_model_of` are unfinished exercise points. | Typed finite-world interface and proof obligation template. | Design reference only; linked module is not a verified truth oracle. |
| U10 | [pylogic](https://github.com/kakwa/pylogic/blob/46b6cfecca7ccb74b8caae054464d8092b40c97b/src/pylogic/logic.py), standard root license not found | `Context.setPredicateFunction` registers a callable and arity for finite-domain interpretation; uses a lexer/parser and quantifiers. | Predicate-as-function registration and partial/curry composition precedent. | Requirements reference, not a modern Python drop-in; several linked routines contain implementation defects. |

"No standard root license found" is an observation limited to the inspected standard filenames, not a definitive legal status.

## Independent mechanism requirements and falsifiers

| Behavior ID | Input / precondition | Required output and invariant | Minimal falsifier |
| --- | --- | --- | --- |
| M01 Boolean algebra | Typed `Expr[Bool]`, compatible fully specified teaching world, bound variables | Recursive evaluation and Boolean construction produce the answer prescribed by that world. Tiny truth tables are useful fixtures. | One of the four binary-operator truth cases differs from our defined table. |
| M02 Finite predicates | Finite typed universe, arities, declared relation/function interpretations, valid assignment | Evaluate relationship questions in the *specific* stipulated world. Add quantifiers only when the lesson requires them. | A relation answer changes without a corresponding world/rule change. |
| M03 Predicate registration | Declared semantic ID, function signature, source meaning, backend adapter | Callable is bound to typed semantic reference without allocating or parsing an ad hoc string name. | Same display alias accidentally changes semantics or function identity. |
| M04 Constraint search | Finite model, chosen constraints and resource bounds | Help select varied consistent teaching-world instances; report whether the requested search succeeded. Use SAT/UNSAT/UNKNOWN distinctions only for operations making those claims. | Failed proposal corrupts the next generated world. |
| M05 Stepwise feedback | Student answer, prescribed world, expected answer under that world | Check the answer against the teaching definition. If a *deduction proof* is explicitly requested, distinguish mere consistency from entailment. | An answer contradicting our own world is praised as correct. |
| M06 Structural variation | Typed AST, chosen transformation, its stated conditions and teaching world | Generate fresh equivalent/contrastive items and check expected labels under the scoped evaluator. | Reversed directed queries are always labeled false regardless of actual stipulated facts. |
| M07 Knowledge-graph expansion | Existing concept triples, prompting method and source identity | Return possible relations and examples for review or as explicitly *hypothetical* worlds; label proposals clearly. | A generated conjecture silently overrides the current teaching definition. |
| M08 Formula registry | Prescribed mathematical relation, input domain and variable assumptions | Parse a declarative teaching formula into a typed expression and check examples in its chosen domain. | Answer evaluator uses formula outside stipulated input domain. |
| M09 Explainable neural output | Student predictions and concept references | Explanations describe model behavior and measured fidelity, not independent label truth. | Explanation agrees with wrong predictions and is called an oracle. |
| M10 Scope receipts | Operation `G`, allowed values `V`, finite teaching scope | Return observed result with the model/world, method and version recorded; optional stronger certificate when warranted. | Model-specific success presented as a universal theorem. |
| M11 Graph dependencies | Canonical typed semantic IDs, admitted edges, revisions | Compute affected transitive closure, reject cycles where prohibited and report missing or unsupported edges. | New grade/primitive does not invalidate dependent generated plans. |
| M12 Generated properties | Typed strategy and declared semantic obligations | Produce reproducible, diverse valid/invalid samples; shrink counterexamples for testing; runtime teaching seed remains explicit. | Random generator omits a required coverage family while reporting full coverage. |

## Source defects that matter

- **U04 SymStep experiment:** `ConstraintPropagator.apply_positive` treats an admissible value as an accepted deduction. A value can be consistent without following from the clues. The experiment also mutates possible domains before detecting some rejected proposals, without automatic rollback. Bilqis cannot use the experiment's `Correct deduction` status as an oracle.
- **U04 GraphStep core (only if adopting the affected operations):** `Constraint.filter` is supplied by subclasses. `Table.status` can incorrectly assert entailment when duplicate allowed tuples inflate its count; `solve(max_solutions=1)` cannot prove solution uniqueness. Shared branch-ledger state and `unsat_core` claims also need focused checks before use for formal proofs. These defects **do not block using our own deterministic finite-world evaluator for basic lessons**.
- **U08 propositions:** `all_models` iterates a set of Booleans, which need not preserve a specified truth-table order. `combine_formulae` indexes a declared Iterable as if it were a Sequence. Behavioral requirements must specify deterministic enumeration and valid input collections.
- **U09 predicates:** The cited semantic evaluators are incomplete. Use the universe/interpretation model as a spec precedent, not executable gold.
- **U10 pylogic:** Uses old Python syntax and APIs in places; `_isSatisfiable` compares a returned list of truth rows with integer 1. Use only the callable-predicate registration concept after a separately verified rebuild.
- **U01 LEN:** Testing an explanation against feature labels measures fidelity to data or model, not whether a proposed rule is logically/source correct.
- **U05 DYNA-SKILL:** LLM-generated graph edges may be plausible while wrong. Stage external factual/NI claims as proposals, but hypothetical worlds may be used as clearly declared pedagogical examples.
- **U02 REASON:** Differentiable operators operate inside another neural system; no modification of existing Bilqis FP32/AdamW is implied.

## Supplemental libraries worth qualifying

| Source | Distinct role | Conditions before use |
| --- | --- | --- |
| [SymPy logic](https://github.com/sympy/sympy/blob/master/sympy/logic/boolalg.py) | Boolean operators, simplification, and optional formula comparisons | Verify behavior for the exact finite-world Boolean lessons selected, preserving answer type and AST meaning. |
| [Z3](https://github.com/Z3Prover/z3) | Finite/domain constraints, satisfiability, counterexample construction | Check source-world encoding, solver timeouts and SAT/UNSAT/UNKNOWN status handling. |
| [Hypothesis](https://github.com/HypothesisWorks/hypothesis) | Declarative generated property tests with shrunk falsifiers | Use as verification/testing infrastructure; don't accidentally make its test-runner state the live teacher's sampling authority. |
| [NetworkX](https://github.com/networkx/networkx) | Typed dependency DAG closure, reachability, topological operations | Use stable AST node IDs, no domain law inference from mere graph adjacency. |

These are candidates, not yet locally installed or compatibility-tested. Do not write a replacement solver or graph algorithm before a small reproducible dependency spike.

## Implementation separation and source trace

The source analyst owns U01-U10 and M01-M12. The independent builder must receive method requirements, example inputs, preconditions, expected outputs and failure cases, not the source implementations. Each candidate method receives a receipt:

~~~text
method_id | method_revision | upstream_reference/commit
behavior_requirement_ids | source_claim_ids | implementation_adapter
conformance_fixtures | independent_verifier | proof_scope
decision {IMPORT, CLEANROOM_REBUILD, REFERENCE_ONLY, REJECT}
status {PROPOSED, PROVEN, ADMITTED, SUPERSEDED}
~~~

A new early-grade method is usable when an actual application through the canonical AST consistently executes its **prescribed bounded teaching behavior**, its example answers pass representative positive/negative/boundary tests, and it produces useful varied instructions. Stronger formal claims receive corresponding extra verification. Implementation tests alone do not establish that Bilqis learned.

## What the next agent must do

Read protected issue #336 and the parent compositional contract first. Preserve the current worktree's uncommitted trainer fixes. Start with an executable, disposable example of **our** finite-world Grade A predicates composed with an existing Grade B connective through higher-order functions. Show fresh lawful examples with correct prescribed answers and an added compatible predicate without rewriting the engine. Test supplemental constraint engines only where they supply actual needed functionality. Observe the teacher's selections, then validate real learning only in a separately human-invoked run. Preserve all student/optimizer/teacher state.

## Minimal executable acceptance specimens

**F01: Learn the stated world.** In the lesson's finite directed-parent interpretation, world `{(a,b)}` yields `parent(a,b)=TRUE`, `parent(b,a)=FALSE`. An empty world yields `FALSE` for both. A separately declared symmetric link interpretation may make the reversed link `TRUE`. No universal theorem is being claimed.

**F02: Compose consistently.** For each reachable truth combination of two prescribed predicates, a curried Boolean operation and its direct-application counterpart yield the same answer and trace their original semantic IDs. A display alias change cannot alter the resulting exercise.

**F03: Preserve teaching worlds.** Two predicates from incompatible entity/world representations cannot be mixed until an explicit conversion has practical round-trip tests. Unavailable combinations appear as scoped debt while other lessons continue.

**F04: Generate useful diversity.** Fresh seeds yield different referents, true/false contrasts and lawful composition structures. The system reports how many distinct structures were actually shown, not merely how many string permutations it printed.

**F05: Grow without branches.** In a disposable catalog, add one new compatible predicate and an unfamiliar grade, keeping historical model IDs fixed. Existing methods discover the new permitted exercises without adding named-capability cases to the core compiler.

**F06: Teach before escalating.** A direct primitive exercise is available before a nested composite that requires it. A failed examination can inform a later teaching sample, and delivered exposure is recorded separately from offered options.

**F07: Keep learning claims empirical.** Generator tests establish only that questions/answers comply with the teaching definition. Real student mastery is measured by scored complete, fresh, same-checkpoint cohorts and later retention.

**F08: Validate an optional solver only for its actual role.** If GraphStep will grade inference, entailment or uniqueness, test its duplicate-table and multiple-solution edge cases. If Bilqis only needs an explicit finite-world evaluator for a direct beginner question, no general-purpose solver proof is required.
