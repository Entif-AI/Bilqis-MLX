# Bilqis generative curriculum factory: compiler, evidence and adaptive teaching

**Status:** SUPERSEDED INITIAL SKETCH. Retained for provenance. [04_COMPOSITION_AND_UPSTREAM_REUSE_DECISION.md](04_COMPOSITION_AND_UPSTREAM_REUSE_DECISION.md) is the active comparison and architectural recommendation. Behavioral implementation is paused.
**Previous context:** 01_CODE_AUTHORITY_AND_SEMANTIC_AST.md and protected issue #336. ADR-028 now records the newer, composition-first direction; this draft has no governing authority.

## 1. Product contract

An approved change to one semantic definition must propagate through every relevant curriculum obligation, lesson generator, assessment constructor, source oracle, teacher option and diagnostic probe **without new code branches for that semantic slug or its grade**.

The resulting instruction must be lawful, generated afresh across visits and optimizer steps, progressively comprehensible, and governed by the learned teacher. Assessments derive from the same approved semantic rules as instruction, remain independently scored, and require complete 100% same-checkpoint graduation. Failed examinations inform later teaching. Temporary forgetting in earlier grades is allowed during acquisition, then repaired during cumulative A-through-current revalidation.

The machine must distinguish what it constructed, what it actually taught, what was learned, what persisted, and what remains unsupported.

## 2. System dataflow and authority

~~~text
Repository semantic catalog (canonical IDs, typed AST, source claims, revisions)
              |
              v
    Immutable admitted semantic release
              |
      +-------+------------+------------------+
      |                    |                  |
      v                    v                  v
Typed rule compiler    Dependency graph   Source adapter registry
      |                    |                  |
      +----------+---------+------------------+
                 |
                 v
     Legal construction obligation planner
                 |
                 v
    Source-bound construction and witness engine
        |                         |
        v                         v
 Verified teaching menu      Generated exam plan
        |                         |
        v                         v
 Learned teacher decision     Independent scoring
        |                         |
        v                         |
 Human-owned optimizer loop   |
        |                         |
        +-----------+-------------+
                    v
        Learner evidence and exposure receipts
                    |
                    v
       Five-signal diagnosis and delayed outcome
                    |
                    v
     Teacher-readable observations and options
                    |
                    +----> next teacher policy decision
~~~

Every arrow has a typed artifact and a versioned receipt. No generator module owns a second semantic registry. The compiler owns construction *eligibility*; the teacher owns pedagogical *selection* within eligible choices; the human owns actual student optimization.

## 3. Caller's view first

This example is **design pseudocode**, not a shipped API:

~~~python
# Resolve the semantic world the intact student was trained against.
release = catalog.open_by_digest(student.semantic_release_digest)

# Work with canonical typed refs. A trainer never creates A.* or B.* names.
scope = release.admitted_scope(school.current_grade, school.mastery_history)
plan = factory.plan(scope, source_adapters, obligation_policy=release.coverage_policy)
evidence = learner_evidence.read_current(student, school.teacher_state)

# Candidates are generated from admissible AST rules and source witnesses.
options = factory.teaching_options(plan, evidence, seed=next_seed)
selection = teacher.choose(options, evidence)      # inherited strategy decides
batch = factory.materialize(selection, plan, seed=next_seed)
assert batch.source_verified and batch.release_digest == release.digest

# Human-authorized trainer alone applies the optimizer step.
# All selected, attempted, excluded and served obligations receive receipts.

exam = factory.examination(plan, seed=fresh_seed, complete_grade_roster=True)
scores = evaluator.score_same_cohort(student, protected_champions, exam)
diagnosis = monitors.update(scores, served_batch_receipts, prior_observations)
teacher.observe(diagnosis)                           # no imposed fixed mix
~~~

Only a configured, explicitly approved grade release can reach the last two calls for a new grade. A source candidate or research hypothesis is not independently admitted by the existence of a generator.

## 4. Compiler stages

### Stage 1: normalize and type-check the semantic AST

Resolve opaque IDs, aliases and revisions; check every declared type, operand/result slot, lexical/grammar restriction and source claim. Close direct and transitive prerequisites. Reject cycles and undefined refs. Keep supported finite mathematical adapters separate from unverified New Ithkuil morphological equivalences.

### Stage 2: discover potential compositions

Use **type unification and admitted semantic traits**, not cartesian product over fixed grade lists. Candidate producers satisfy operand type constraints. Apply scope, binding, source-world, grammar, modality, and relevance predicates to determine if each candidate is:

- REQUIRED: mandated by the admitted semantic/coverage contract.
- PERMITTED: lawful, useful variety supported by that contract.
- INAPPLICABLE: the construction rules explicitly exclude it.
- UNRESOLVED: legality, source interpreter compatibility or relevance has not been established.

Record the rule ID and proof or counterexample for each verdict. A type match is not enough to call something a required learning obligation. A large candidate pool is not proof of completeness. Inapplicability must be justified and source-traceable.

**Coverage debt** includes required/permitted structures that lack proofs or witnesses, unresolved applicable candidates, and source-defined factors not yet taught or assessed. Unsupported new constructions block their own admission and affected releases only; previously approved independent learning may continue.

### Stage 3: build a declarative coverage lattice

Coverage dimensions come from AST declarations and sources. Examples include:

| Dimension | Evidence |
| --- | --- |
| Semantic types and legal argument roles | Type derivation, binding and domain/scope constraints |
| Source relevance and composition legality | Exact source claim and approved construction-rule proof |
| Positive/negative/contrastive forms | Lawful witness records and independent gold agreement |
| Boundaries and invalid constructions | Source-defined invalidity classifications and negative controls |
| Metamorphic relations | Registered LawId, preconditions, transformation and oracle relation |
| Structural variation | Isomorphism/orbit diversity where semantics allow renaming |
| Prerequisite integration | Closure, constituent mastery and construction-role witnesses |
| Introductory complexity | AST complexity measure and permitted first-lesson progression |
| Actual exposure | Selected option, materialized sample, delivered optimizer visit/step receipt |
| Observed learning and retention | Same-cohort scoring, longitudinal changes and delayed probes |

These are separate statuses. Source construction correctness alone cannot set **TAUGHT**, **LEARNED**, **MASTERED**, or **RETAINED**.

### Stage 4: materialize witnesses with pluggable source interpreters

Construction plugins are source-attested, typed and version-pinned. They implement small interfaces and do not allocate IDs or decide curriculum policy:

~~~python
class SourceAdapter:
    def supports(self, expression_type, source_scope) -> SupportVerdict: ...
    def construct(self, expression_ast, context, seed) -> SourceExpression: ...
    def encode(self, expression, token_abi) -> EncodedExpression: ...

class IndependentOracle:
    def evaluate(self, expression, semantics_revision) -> TypedAnswer: ...

class TransformationOperator:
    def apply(self, expression, law_preconditions, seed) -> SourceExpression: ...
~~~

The witness engine requires agreement among independent implementations appropriate to the source. It detects disagreement rather than voting away the conflict. It records exact source/file/section digests, typed AST, token binding, adapter version, oracle results, seed and produced canonical identity.

The current micro/development split becomes **explicit capability support metadata**, not inferred by parsing file paths. To construct across both, an adapter must prove a common world representation and a lossless typed translation, or provide a source-approved combined interpreter. A bridge that changes truth conditions, token ABI or binding semantics is rejected. No translated form is admitted merely because its final type is Boolean.

### Stage 5: compile reusable lesson and examination plans

The factory generates **construction programs**, not fixed question/answer inventories. A plan constrains permitted rule families, source world shapes, answer modalities, semantic targets, prerequisite depth and coverage deficits; each draw supplies reproducible varied examples.

Instruction and assessment use the same semantic rules and independent gold oracles. They can use different seeds and sampling objectives, but no permanent semantic holdout embargo. Previously failed/examined constructions are eligible for later instruction. Gold is never supplied to scoring inference.

The examination plan yields a complete roster covering all admitted capabilities and legitimate answer types. A single intact FP32 student and its matching AdamW must reach 100% on the complete active grade. Subsequent Billy Madison revalidation runs A through the latest mastered grade, culminating in complete same-checkpoint prefix mastery before advancing.

## 5. Law-driven generation and semantic transformations

A law is a universally or conditionally quantified semantic relation with typed preconditions and source authority. It selects legal transformations for **any compatible AST**, rather than enumerating six Grade A names.

Example: finite-world entity renaming. The law requires a bijection between entity sets and a transformation that changes every entity reference consistently. Its proof obligation is that interpreting the transformed query in the transformed world yields the same typed truth as the original. That is an isomorphism/invariance property, not an arbitrary new vocabulary token.

Contrast: reversing a directed relation is generally **not** a truth-flipping law without controlled world/query preconditions. The generator must construct a witness satisfying those preconditions and test the result with independent evaluators. Law effects include equivalent, negated, order-related, implication, approximate-with-bound, invalid, and other typed relations where sources warrant them. Binary preserve/flip is one case.

A registered law yields a **candidate transformation witness** with parent construction, AST law identity, adapter identity, applicability proof, result relation, oracle agreement and token receipts. Only source-admitted instances enter teaching or assessment. A test must not declare truth because its own hard-coded string says preserve or flip.

## 6. Actual learner and teacher interface

### 6.1 Teacher options, not injected ratios

The factory provides option sets indexed by requirement IDs and evidence:

~~~text
TeacherOption {
  objective_ref, semantic_release, candidate_family, sources,
  valid_answer_modes, complexity, prerequisites, coverage_debt,
  recent_student_errors, exposure_history, delayed_retention,
  optional_champion_teacher_evidence, resource_estimate
}
TeacherDecision {
  observed_options_digest, learned_policy_version, chosen_option_refs,
  selection_reason_receipt, scheduled_quantity, requested_followup
}
~~~

The adaptive teacher applies its inherited policy to options. The factory must not carve out 25% for Grade A because a particular Grade B generator exists. Any policy change is separate versioned, tested, approved work, with comparisons against inherited teacher behavior.

Existing grade champions contribute one teacher vote **per represented graduated grade**. A weighted soup remains a frozen teacher. The trainable student and its native AdamW are never reconstructed from champion scores or frozen teachers.

### 6.2 Evidence ledger for teaching exposure and mistakes

Use an append-only evidence log keyed to the semantic-release identity, obligation, generated witness, student checkpoint, teacher decision and optimizer visit/step:

~~~text
Constructed -> Offered -> Selected -> Delivered -> Reassessed -> Retained/Regressed
~~~

Only **Delivered** proves instructional exposure. A recorded examination error does not count as repaired because a newer cohort rotated. Store unresolved errors with identity, capability, severity, observed incorrect prediction, next eligibility, subsequent corrections and eviction/starvation receipts. Bound storage with a separately justified policy that preserves fairness and allows observable recovery; there is no universal 24-item capacity derived from the current Grade B patch.

If the teacher selects other work, the ledger records that choice and leaves the missed obligation observable. Fairness rules may require teacher visibility, debt escalation or explicit policy evaluation, but may not masquerade as choices made by the learned teacher.

### 6.3 Spiral learning is modeled as state, not a global blocker

Acquisition of a new grade can reduce earlier proficiency. That loss becomes diagnostic evidence and a future revalidation obligation. The scheduler enforces:

1. Full active-grade capability pass.
2. Two independently re-ranked weakest-three rounds using all currently eligible grades, with repeated selection allowed.
3. Repeat until the active grade first achieves 100% on one intact checkpoint.
4. Ordered earlier-to-current grade replay and final 100% cumulative same-checkpoint qualification.

Teacher selection may vary the instructional response, but it cannot waive the grade-order or graduation proof. A current score below an old champion is visible; it is not silently hidden behind a saved-champion banner.

## 7. Five executable learning diagnostics

The user supplied five original warning signals. The new monitoring layer must consume actual predictions, training exposure, generated-cohort provenance and the AST coverage ledger.

| Signal | Input | Diagnostic evidence | Teacher-facing response | Delayed measurement |
| --- | --- | --- | --- | --- |
| 1. Repeated identical answers | Predicted label distribution per typed task versus independently computed gold distribution | Entropy/collapse, lexical confounds, class imbalance, sampled controls | Offer contrastive source-valid witnesses; show predictions and coverage classes | Fresh comparable cohorts and prediction distribution |
| 2. Chance-level or lagging capabilities | Full-capability scores, proper class baseline and task difficulty | Capability-specific lag with uncertainty; same-cohort champion comparison | Offer weakest capability and prerequisite construction options | Subsequent paired assessment |
| 3. No persistent learning gains | Reward/lesson result alongside multiple later exams | Short-lived gain, interference, retained versus regressed families | Offer spaced revision, structural variety and dependency recovery options | Delayed source-valid re-probes |
| 4. New semantics lack links to old | AST prerequisite/compatibility closure plus delivered construction receipts | Missing required edge, unverified source bridge, no actual constituent exposure | Offer earlier-skill bridge and decomposition options | Verified exposure and cross-grade retention |
| 5. Introductions are too complex | AST depth, new token count, constituent prerequisite coverage and observed early failures | Complexity exceeds admitted introductory scope or outpaces mastered constituents | Offer minimal lawful exemplars and staged complexity options | Intro-stage gain and later transfer |

Each detector needs positive and negative-control fixtures, an attributable grade/capability scope, evidence timestamps, missing-data state and follow-up linkage. Thresholds/baselines are **versioned diagnostic policy** established from valid data and controls. Do not scatter numerical alarm thresholds into specialized Grade B functions. Signals are hypotheses and options for the teacher, not new model-weight updates or automatic bans on allowed temporary forgetting.

Report NOT MEASURED when evidence is absent. A green source-construction suite cannot produce a fictional learning-improvement metric.

## 8. Tests generated from the AST rather than copied from it

The verification engine derives legal cases and mutation scenarios from the typed AST, then compares outcomes with independently implemented source/oracle rules. No general-purpose test pins a currently convenient list of A/B slugs or the live Sheet's row counts.

**Required contracts and test families:**

- Unique domain IDs, append-only token ABI, stable aliases and release/version lineage.
- Adding a synthetic primitive via the canonical catalog produces all affected type/legal/prerequisite coverage and compiler artifacts without editing named-grade code.
- Editing a primitive's type or law revision invalidates exactly its dependent families while preserving old student release receipts.
- Renaming a display symbol or moving a human lesson/Sheet row changes neither semantic identity nor compiled behavior.
- Deleting a required source claim, breaking an oracle, or leaving an ambiguous bridge fails new admission visibly.
- Metamorphic witnesses validate both their preconditions and source truth relation, including deliberately false-law controls.
- A new grade is admitted only with complete provenance, typed construction coverage, baseline source proof, appropriate answer castes and teacher options.
- Model-response collapse, chance plateau, transient gains, missed prerequisites and overly complex introductions trigger the correct diagnostic with independent negative controls.
- Previously examined questions may return as teaching examples; immutable exams cannot be overwritten or score from gold hints.
- Missed-example memory cannot silently erase unresolved failures, hide starvation, or make the learner seem trained when an option was only offered.
- Temporary old-grade regression is allowed; ordered spiral and one-whole-checkpoint 100% prefix graduation remain mandatory.
- Same-cohort champions, full FP32+own AdamW, trained teacher policy, event outbox and crash recovery remain intact across release changes.

**Historical ABI fixtures are exceptions:** A migration-specific test may pin the original 222 token indices, hashes and archived source cohorts to prove no historical drift. That is an intentionally fixed compatibility receipt, not a definition of how many tokens, lessons, grades or bridges the *current* source of truth must have.

## 9. Bounded generation without hiding debt

The combinatorial search space can grow rapidly. The planner uses typed pruning, semantic equivalence classes, prioritized coverage and configurable generation budgets. Budgets affect how many witnesses are built in an audit, **not whether an obligation exists**. Unsampled required cases remain explicit coverage debt, tied to the exact AST/source revision and reason.

Mutation, concurrent catalog edits and interrupted audits must be reproducible: canonical input digests, deterministic seeds, dependency-indexed caches, pure construction functions, atomic artifact publication, and immutable readback. Caches are derived data, never authority.

## 10. Existing evidence versus target acceptance

The most recent pinned A/B audit identified 66 **type-compatible operand-position candidates**. It independently verified source contrast witnesses for 33 historical micro-world positions. The remaining 33 cross micro/development interpreter boundaries and remain unverified. These are construction-level observations; the numbers cannot be generalized as permanent curriculum requirements.

The current A/B trainer does not yet consume the new planner as its primary semantic source. The five full detection/diagnosis/teacher-response/delayed-outcome loops and a teacher-controlled general rehearsal policy remain unimplemented. The untracked SemanticLaw research prototype must not be elevated as an AST-approved law registry.

The next **architecturally valid** implementation unit is a code-native semantic catalog with identity/types/law contracts plus one source adapter proof, followed by a self-generated artifact showing renamed/added/revised semantics and zero handwritten grade branches. Human neural training remains a separately authorized last acceptance stage.
