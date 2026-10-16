# Bilqis compositional curriculum: method and identity contract

**Status:** DRAFT v0.2, 2026-10-16. Protected architecture specification; not an admitted semantic release or training authorization. Requires review by the user and implementing agent.
**Authority:** IPR-0220 and the user's corrections in protected issue #336, comment 6210595466, and the subsequent 2026-10-16 educational-scope clarification recorded in issue comment 6211375269.
**Baseline:** `Entif-AI/bilqis-mlx` commit `c5be82986d9e4ecc0fb207c07d60db567bf2cd62`.
**Change posture:** Documentation and design only, isolated from the shared worktree and real student.

## Intended system

Bilqis's versioned, code-authoritative semantic AST determines which concepts she is being taught, their types, identities, **our prescribed interpretation of each concept**, prerequisites and applicable teaching operations. These interpretations are informed by New Ithkuil sources but can be deliberately simplified for a beginner. Typed reusable methods supply algebra, finite-world evaluation, controlled variation, test generation and, where useful, solver-based checking. A compiler discovers valid compositions **within our declared instructional worlds**, constructs varied lessons and examinations, and exposes coverage gaps. The learned teacher chooses among valid teaching options. Methods may be imported from qualified packages or rebuilt independently from behavioral specifications.

A successful generic system responds to an admitted new or revised semantic contract by deriving its relevant downstream lessons and tests **without editing grade-specific conditionals**. Passing tests written against old hardcoded cases does not establish this outcome.

**The purpose is developmental acquisition, not universal proof.** An early student needs to reliably learn identity, relation, truth, simple composition and retention as *we define and teach them*, then build richer language semantics on that foundation. We control the questions, permitted permutations, answer functions and introductory complexity. A lesson's operational correctness means it complies with its recorded teaching contract and returns the expected answer under that contract. It does not mean we have proved the contract universally valid or established complete New Ithkuil conformance.

Three separate statuses must remain visible: **DEFINED_FOR_TEACHING** (we have prescribed usable bounded semantics), **LEARNING_OBSERVED** (real student performance on varied generated examples), and **EXTERNAL_CONFORMANCE_REVIEWED** (a stronger, later claim when independently warranted). The first is sufficient for early lessons when the contract is coherent and checked against representative fixtures. The latter two cannot be inferred from source code or green synthetic tests.

## Normative requirements

**BLC-001 Identity authority.** The canonical AST catalog alone allocates and resolves Bilqis `SemanticId`, `TokenId`, `LessonId`, `CapabilityId`, `LawId`, `MethodId` and `GradeId`. Source providers retain their external identifiers as provenance. Generators, tests, Sheets and adapters cannot invent domain identifiers or infer their meaning from display strings.

**BLC-002 Historical continuity.** Adopt the original Token Atlas indices 0..221, original semantic symbols and approved lesson/capability references. Do not replace or renumber them. New token ABI slots are append-only and separately admitted. Historical student checkpoints resolve their pinned semantic release even after later catalog edits.

**BLC-003 Typed meaning.** Each semantic definition records a structured type, *prescribed bounded teaching interpretation*, source references when known, allowed world/permutation rules, prerequisites, examples and revision digest. Parse imported type strings once at ingestion. Compatible result types do not by themselves permit mixing incompatible instructional worlds.

**BLC-004 Pedagogical interpretation and external source.** Official New Ithkuil material informs our preferred meanings and later conformity targets. We may explicitly teach a simpler scoped formal representation while richer morphology or semantic details remain pending. Its exercises are valid **relative to that chosen model**. Do not falsely label these provisional constructions as certified New Ithkuil, but do not block learning because a universal proof is unavailable. A label or `source_axiom` string cannot substitute for the actual prescribed definition.

**BLC-005 Versioned change.** Changes to display labels and Sheet row ordering do not change semantic meaning. Reviewed meaning changes create new revisions, selectively invalidate dependent compiled plans, and retain old release and model compatibility.

**BLC-006 Typed expression algebra.** A minimal persistent IR supports `Ref[T]`, `Apply[T]`, `Bind[T]`, `Transform[T]` and typed constants. Higher-order methods `apply`, `partial`, `curry`, `lift`, `compose`, `substitute` and `transform` return inspectable expressions and provenance. Runtime closures may be compiled but do not replace this expression record.

**BLC-007 Method contracts.** Each reusable method declares its type scheme, applicable semantic traits, operational preconditions, output type, implementation adapter and **bounded test contract**. Method applicability is computed from the AST. No production method dispatches on `A.IDENTITY`, `B.XOR`, a grade-prefix substring, or a fixed manually chosen capability list.

**BLC-008 Transformation contracts.** Each teaching transformation declares scoped applicability, preconditions and the answer effect **we expect inside the teaching model**. Consistent entity renaming, directed-relation reversal and counterfactual variation are selected only where our model defines them. Check examples and known counterexamples against the prescribed answer function. No claim of universal formal validity is necessary.

**BLC-009 Instructional worlds.** Every adapter declares accepted domains, local representations, encoders and output answer types. Cross-world composition requires **an explicit, tested translation under our chosen semantics**, not a formal theorem of universal equivalence. A missing translation becomes scoped `WORLD_BRIDGE_UNDEFINED` debt. Other lawful lessons continue.

**BLC-010 Teaching obligations before sampling.** The compiler derives the curriculum's declared prerequisite edges, operator positions, answer types, meaningful contrast/boundary families and age-appropriate introductory complexity. Do not explode the combinatorial universe merely because a type allows it. Budgets limit how many teaching examples are sampled; untried *declared* learning goals remain visible without forbidding routine progress.

**BLC-011 Shared generation.** Lessons and examinations draw from the same prescribed semantic constructors with reproducible seeds and varied teaching-world examples. Every revisit and optimizer-step sample should provide fresh lawful experience where available. No permanent sealed holdout or exam-question embargo. An assessed mistake can become a lesson. Exams disable optimizer updates during scoring; answers are withheld from student inference, not future instruction.

**BLC-012 Curriculum-relative answer checking.** A deterministic answer evaluator must be consistent with the teaching contract, the generated world and typed output. Test representative true/false, boundary and invalid cases, including deliberately wrong answers, before trusting a generator. Where multiple implementations or solvers are useful, compare them **within the prescribed world**, and preserve disagreements. External independent proofs and exhaustive model checking are optional escalation tools, not routine prerequisites to teach basic concepts. A generated item whose expected answer contradicts its own evaluator is excluded until repaired.

**BLC-013 Traceable instructional example.** A generated item carries release digest, typed expression, involved semantic/method IDs, teaching-world contract, generator and evaluator versions, seed, answer type, expected answer, verification status and content hash. Formal proof references are included when applicable but are not mandatory. A sample that cannot be scored consistently **under the chosen model** is repaired or skipped; unrelated lessons continue.

**BLC-014 Teacher authority.** The factory supplies legal choices, diagnostic evidence, prerequisite obligations, mistakes and actual exposure. The inherited learned teacher chooses their mix and order. No hardcoded 25% rehearsal quota or hand-authored ratio can silently replace that policy.

**BLC-015 Durable error memory.** Successive fresh exam cohorts never erase still-unresolved previous mistakes. Store each witness, semantic family, observed error, actual remedial exposure, retry and fairness evidence. A candidate offered to the teacher is not automatically a taught lesson.

**BLC-016 Graduation and custody.** Preserve the original full FP32 student with matching native AdamW, teacher state, 222 historic token indices, champion voting and checkpoint/event custody. The human alone runs real student training. Allow temporary old-grade regression during new-grade acquisition; perform full active-grade pass and two freshly ranked weakest-three rounds, then A-to-current cumulative revalidation. Advancement requires 100% on the complete rubric at one intact checkpoint.

**BLC-017 Comparable metrics.** Score incumbent and challenger on the exact same sampled cohort. Samples drawn at different steps are longitudinal observations, not paired score improvements. Show all five user-specified warning signals with actual predictions and training exposure: answer collapse, chance/lag, nondurable gain, disconnected semantics and needless introductory complexity.

**BLC-018 Failure precision.** Unsupported or inconsistent constructions block only the affected teaching sample or method. A missing universal proof, external license or complete NI morphology interpretation does **not** automatically block bounded, independently implementable educational methods. Report exact observed failures and unmet curricular coverage; do not convert every research uncertainty into an operational stop.

## Expression and method interface

The following is a behavior contract, not copied upstream code or approved implementation syntax.

~~~text
SemanticDefinition {
  identity: SemanticId, revision: Digest,
  type: TypeScheme, meaning: InterpretationRef,
  domain: ConstraintExpr, traits: Set[TraitRef],
  source_claims: Set[SourceClaimId], teaching_scope: TeachingContractRef,
  admission: AdmissionState
}

Expr[T] = Ref[T] | Constant[T] | Variable[T] | Apply[T]
        | Bind[T] | Transform[T] | WorldInstance[T]
        | Quantify[T]  # only when a curriculum declares quantification

LawDefinition {
  id: LawId, applicability: TypedPredicate,
  precondition: TypedPredicate, transform: MethodId,
  relation: OutcomeRelation, scope: TeachingContractRef,
  checks: BoundedCheckContract
}

MethodContract {
  id: MethodId, input: TypeScheme,
  traits: TraitPredicate, precondition: TypedPredicate,
  output: ArtifactType, backend: AdapterRef,
  evaluator: CurriculumAnswerContract
}
~~~

The compiler follows one deterministic direction:

~~~text
SemanticRelease
  -> type/teaching-contract/prerequisite validation
  -> applicable MethodContracts by unification
  -> lawful expression and dependency closure
  -> construction programs + explicit coverage debt
  -> seeded curriculum-constrained example sampling
  -> answer checks against prescribed scoped interpretations
  -> teacher-selectable lessons / complete generated exams
  -> durable outcomes, diagnostics and revised teaching options
~~~

Methods are composable at the typed-expression level. For example, bind arguments to a prescribed finite-world relation, lift a Boolean connective over two compatible expressions, generate varied worlds satisfying our explicit lesson rules, and evaluate their expected answers. A second solver can help diagnose a discrepancy when needed. The engine does not need to know the original human-facing names of those expressions.

For later language-semantic expansion, variable binding and quantifier nodes must preserve declared scope and avoid accidental variable capture. Those features need not be taught or fully implemented in Grade A. Each executable release only needs to support the operators and world interpretations it actually teaches.

### Scope of checking

Do not confuse `evaluate(expr, W)` (answer for one fully specified teaching world) with `satisfiable(P)` (some possible world), `entailed(P)` (every permitted world), or `unique_solution(P)` (exactly one permitted solution). **Our immediate examinations require the first operation**, with a complete stipulated world and a stable answer function. The other operations can provide generation, diagnostics or future lessons when those tasks actually need them.

If the factory adopts a solver that claims entailment, equivalence, uniqueness or contradiction proof, validate that narrow claim with its own scope and counterexamples. Do not silently elevate mere possibility to certainty. Conversely, an upstream tool's weakness at proving universal entailment does not disqualify it from constructing a useful bounded teaching example.

## Behavioral clean-room route

1. **Read:** A source analyst inspects a pinned upstream revision and writes an implementation-neutral contract. For each extracted mechanism, record inputs, outputs, preconditions, invariants, defined failures, runtime bounds, external witnesses and exact citation. Do not reproduce source control flow or prose as a disguised transcription.
2. **Review:** A separate reviewer checks whether the described method behaves as claimed on representative fixtures, and whether its use fits Bilqis's chosen teaching worlds. Do not demand that the source method establish universal truths outside its intended scope.
3. **Build:** An implementer who has not read the upstream implementation receives only the approved spec and fixtures. Implement the smallest independent method/adapter, or select an already qualified licensed dependency where appropriate.
4. **Test:** Exercise positive/negative examples, model-defined boundaries, changed semantic identities, expected failures and intentionally bad answer functions. Formal proofs are optional for narrow methods that can be checked deterministically on our chosen instructional examples.
5. **Reconcile:** If behavior fails, preserve the counterexample and fix the contract or implementation. Never quietly amend tests simply to agree with a buggy result.

Public source code without an explicit license can still teach us an algorithmic or mathematical idea. The procedure avoids copying its protected expression. It does not claim an exemption from applicable law.

## Acceptance cases

| Mutation or fault | Required observable result |
| --- | --- |
| Admit a new type-compatible predicate | Current method repertoire generates legal compositions without editing a grade-specific branch. |
| Add a predicate with incompatible world dialect | Report undefined translation; continue compatible in-world lessons. |
| Add a capability in an unknown grade | Derived dependency closure and tests change from catalog semantics, not a grade switch. |
| Rename or move a Sheet entry | Original IDs, model ABI, source meaning and released scores stay unchanged. |
| Revise a law or output signature | Exactly affected construction plans invalidate; historical releases still load. |
| Apply a reversal in a world where it does not flip truth | The recorded lesson rule excludes or correctly scores that case. |
| Generate many equivalent renamings | Structural-orbit coverage reports missing distinct cases. |
| Poison the prescribed answer evaluator | Inconsistent exercise is detected and withheld; unrelated lessons continue. |
| Fail a newly sampled exam item | The teacher can later teach that witness; actual exposure and outcomes are recorded. |
| Ask teacher for a different old/new mix | The factory preserves the teacher's choice; no fixed quota silently overrides it. |
| Score challengers on different draws | No paired comparison; use one shared cohort for ranking. |
| Pass all construction tests but fail human B learning | System says construction-qualified, not mastered; five real warning detectors report evidence. |
| Evaluate a specified finite world in which `parent(a,b)` holds | `parent(a,b)` scores true and `parent(b,a)` scores according to our declared directionality, with no global theorem necessary. |
| Compose the same two typed predicates through currying or direct application | Under the same prescribed world and connective, expected answers match for each reachable input pattern. |
| Introduce an overcomplicated composite before its primitive constituents | The curriculum reports unmet prerequisite and supplies a simpler lawful introduction. |
| Encounter an upstream constraint solver's incorrect entailment claim | Only methods depending on that claim are quarantined; independent bounded lesson evaluators continue operating. |

A supposed general solution fails this review if these cases require changing hardcoded A/B slugs or copying expected results into tests.

## Delivery sequence

**G0: Source behavior catalog.** Preserve all ten user references plus supplementary libraries, versions, bounded behavior contracts, practical tests, reuse/independent-rebuild decisions and unresolved defects.

**G1: Canonical catalog.** Reconcile existing 222 token IDs and original lesson symbols in one code AST. Check historical model+AdamW release identity; no alternate runtime identity catalog.

**G2: Small executable composition.** Combine a prescribed Grade A finite-world operand pair with an existing Grade B Boolean connective using generic higher-order operations. Generate different legal examples and check expected answers against the *chosen* lesson semantics. Show that a deliberately bad answer is rejected. Repeat with a new compatible semantic definition without method-code changes.

**G3: Genericity demonstration.** Run the mutation/fault matrix above. Verify useful teaching variety, selective invalidation and no new capability-name dispatch. Source-specific novelty can require a new adapter, not a new branch in the generic factory.

**G4: Shadow trainer.** Feed disposable/frozen student states from generated A+B plans. Verify that lessons actually exercise the prescribed beginner concepts, then check teacher selection, scoring cohorts, five signals, queued mistakes and intact checkpoints. No actual student optimization.

**G5: Reviewed cutover.** Migrate callers and delete redundant named-grade dispatch. Verify event recovery, trained model custody, full same-checkpoint graduation, actual human learning and delayed retention before claiming success.

No real student/teacher/optimizer state is changed by this specification.
