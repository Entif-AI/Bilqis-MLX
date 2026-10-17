# Evergreen grade factory: desired state and admission contract

**Status:** PROPOSED FOR HUMAN REVIEW. This is not an admitted Grade D release, an optimizer-policy change, or permission to train the student. The current source and operating rules remain authoritative until a proposal is accepted and proved in code.

**Authority:** The user's 2026-10-17 ten-question request, the current private Bilqis repo instructions, ADR-028 through ADR-035, and protected IPR-0220 issue #336. Keep protected operational details in private surfaces.

## Immediate evidence and scope

At generation 6824, optimizer step 204072, one saved complete student held both A and B grade championships. The run ended at `GRADE_B_AWAITING_NEXT_GRADE`. The existing C transition checks this cumulative result before append-only vocabulary and own-AdamW growth.

The real C preflight cannot currently qualify its release: `semantics/numeric_registry_v1.json` is absent from the feature branch. `tests/test_grade_c_sources.py` and `tests/test_grade_c_trainer.py` construct a **proposed** graph for their fixtures. Their success does not prove that the separately required native Registry readback has been approved and packaged. The connected Token Atlas observed on 2026-10-17 still contained the historical 222-token inventory. No source-reconstruction shortcut or fabricated approval is allowed.

The code already has a grade-neutral scheduler, typed immutable expression nodes, curried operations, source adapters, some independent verification, a read-only Registry projection and a candidate-only A probe planner. Grade authoring, probe generation and native admission still contain A/B/C-specific paths. This proposal closes that gap. It does not replace the existing semantic AST or implement a second solver.

## One default workflow, eleven states

Every next-grade candidate must have exactly one versioned release manifest, built from approved semantic and capability declarations, with a machine-readable proof index. Its status transitions are:

`IDEA -> SOURCED -> SEMANTIC_CANDIDATE -> SEMANTICS_QUALIFIED -> DEPENDENCIES_QUALIFIED -> GENERATED -> TESTED -> REVIEWED -> ADMITTED -> HUMAN_TRAINED -> CUMULATIVE_MASTERED`

`REVIEWED` never implies `ADMITTED`. `TESTED` never implies neural competence. Any `UNKNOWN`, conflicting source claim or missing receipt blocks only the affected release or semantic edge. Earlier saved model releases remain readable under their own pinned contract. Each state change must be explicit and backed by immutable evidence.

The manifest identifies its parent release; original token, lesson and capability IDs; typed semantic bindings; permitted worlds and source authorities; dependency and teaching-stage DAG; independent oracle and adapters; generated instruction/probe/assessment plans; coverage obligations; admitted tokens; model/optimizer migration; provenance and method versions; acceptance tests; and review receipts. Hash the canonical content, keep the old release intact, and regenerate only the transitive dependent subtree when a semantic changes. Do not use Sheet row order or Python callable identity as a semantic identifier.

### Semantic admission: three separate pure operations

All three operations are required and have different contracts. They execute on immutable typed values and carry source/world provenance:

1. `associate(observations, context) -> CandidateAssociations`: enumerate plausible typed relationships, with evidence and unresolved alternatives. Do not assign a final semantic identity.
2. `disambiguate(candidates, evidence) -> ResolvedInterpretation | Unknown`: test competing interpretations under source-backed constraints. An ambiguous result remains typed `Unknown`, never a guessed gold label.
3. `identify(resolved, catalog) -> ExistingSemanticRef | ProposedSemanticRef | Unknown`: bind an interpretation to one approved identity or place an unapproved distinct proposal in review. A proposal cannot allocate a model token or approve itself.

Pure functions can be nested, partially applied, curried, lifted and composed into inspectable AST nodes. Every node retains typed input/output constraints, valid-world assumptions, semantic identity/version, method ID and source evidence. A callable closure alone is insufficient persistent proof. Each admitted semantic receives a companion qualification suite for all three operations, independent source-oracle agreement, negative controls, identity/ambiguity boundaries and lawful compositional transformations. Runtime learning is separately measured on generated **capability probes** rather than inferred from source-function tests.

### Planning and generative construction

The next curriculum is selected from a typed proposal pool, not copied automatically from the historical `Grade Tranches` worksheet. The sheet supplies identities, source evidence and research candidates. Versioned code owns admitted machine semantics. The selection process ranks prerequisite readiness, coverage debt, future dependency leverage, independently validated transfer opportunities, source reliability, donor suitability and observed prior learning/retention cost. It must record why alternatives were deferred. No scoring weights or automatic promotion policy are approved by this draft.

The compiler builds a DAG across **grades and teaching stages within a grade**. Foundational capabilities receive instruction and qualification before composition or dependent examinations. It may also stage foundational semantics needed by upcoming grades, but cannot examine them before mastery. It generates direct, inverse, contrastive, composition/decomposition, illegal-structure and metamorphic probes where laws and sources support them. Every source claim is checked by independently implemented oracles. A held-out composition family must test transfer beyond recalled sample identities. No permanent embargo bars failed exam examples from later supervised teaching.

External libraries and donors are evaluated before creating a parallel implementation. A donor record must bind repository/commit/version, license status, exact function or algorithm, type/world bridge, source ownership, edge-case tests, compatibility, resource limits and replacement proof. Unsupported donors remain proposals, not oracles. The method registry chooses verified operations by type and declared applicability rather than grade names.

## Admission proof, not a test-count target

Before a candidate grade reaches `ADMITTED`, a deterministic, **offline** gate must prove:

- The complete native and code-owned Registry release artifacts exist, are pinned, and agree on approved identities. Old ABI indexes and prior course/exam identities remain unchanged.
- Source claims, pure functions, method versions and independent oracle results are linked to the exact semantic definition. Negative and counterexample probes fail as expected.
- The dependency DAG is acyclic and every teaching prerequisite is from an earlier grade or **earlier qualified stage**. All planned compositions name their mastered constituents.
- Construction and probe factories generate varied source-valid examples for every relevant type, truth condition, boundary, exception and lawful transformation. Missing coverage is explicit debt.
- Semantic edits invalidate only impacted dependent plans. A new unfamiliar synthetic primitive and its dependent grade compile and qualify without a new grade-specific branch.
- Both teacher and student are excluded from the independent oracle role. Candidate-versus-incumbent scoring uses one paired fresh cohort; fixed graduation evidence lasts through its enrollment.
- A disposable, complete model-plus-own-AdamW transition preserves old embedding rows, moments, teacher state and source/custody receipts. Crash, retry and cross-machine readback are tested.
- Every source artifact needed by the **actual** operator path is present in the release package. No test may substitute a `proposed_graph`, mock oracle or synthetic checkpoint for this completeness requirement.
- Static quality gates and focused contract tests pass. No new severity-critical lint, source-boundary, forbidden dependency, broken ABI, secret, unreviewed license or data-loss warning is waived by merely increasing the test count.
- Source and policy review records identify accepted changes, rejected alternatives, open risks, owner, exact release hash and the earliest human-only training action.

`GRADE_READY` requires all mandatory evidence above. Any absent obligation yields machine-readable `BLOCKED` with the exact missing proof. `UNKNOWN` is an outcome, not a reason to forge a receipt. Drafts and earlier saved students remain usable while a future release is blocked.

## Training failure isolation and teacher accountability (separate policy proposal)

Do not install the following mechanisms as hidden changes to the inherited teacher. First compare them against the human-run failure history, agree on thresholds, and qualify them with disposable models and replayed actual receipts.

Each capability gets a per-session health state: `ACTIVE`, `WATCH`, `QUARANTINED`, `REHAB_ELIGIBLE`, or `REINSTATED`. Detection should compare **paired measurements on the same cohort**, trends and capability-relative distributions, not a widening global median polluted by already-stuck capabilities. Use robust historical baselines, variability estimates, minimum evidence, hysteresis and repeated confirmations. Avoid treating a single noisy sample as a causal failure.

When a capability is quarantined, withhold it from the teacher's further adaptation and ordinary evaluation queue for the current run. Preserve its student/checkpoint state and the exact triggering receipts. Remove it from ordinary progress statistics, but show quarantined coverage separately. Buffer the diagnosis and suggested repair for human review at the end of the run. Keep unrelated healthy capabilities progressing. Do **not** declare full grade qualification while required capabilities remain quarantined. A new recovery attempt must be an explicit, measured re-entry decision.

The next teacher-policy proposal must separate *attempted* and *accepted* optimizer updates, preserve exact candidate parent weights and own AdamW, compare paired source-oracled retention evidence, and penalize an accountable rejected teaching strategy. Training a weak new grade may temporarily reduce earlier scores. Thus the mature-consolidation activation phase, acceptance tolerance, penalty amount and retry budget require human approval. Existing source-only warnings are diagnostic, not causal authority for new penalties.

One meta-optimization lane may analyze failed curriculum decisions, propose new detection features, compiler simplifications or teaching strategies, and qualify them against frozen replay and negative controls. **The optimizer cannot change its own admission thresholds, authority, test oracles or mandatory gates.** Promote improvements through the same separate review process as other semantic releases. Measure whether each change improves independent learning/retention per compute and human attention spent.

## Code hygiene and continuity as executable boundaries

The release factory owns one machine-readable manifest and one generated evidence report per grade. Reuse existing `README.md`, `AGENTS.md`, append-only `ADR.md`, `HANDOFF.md`, protected issues and incident ledger; do not create parallel narrative authorities. Each development start reconciles branch/HEAD, source release, open work, active writers/locks, immutable student state and known relevant postmortem controls. It reports conflicts before mutations. Each verified unit ends with tests, ordinary non-force push, remote SHA readback and compact protected issue receipt. Move the same work across workstations or agents using Git/source IDs and opaque issue pointers, not fragile chat memory.

Quality checks execute in two tiers. Fast, affected-module checks run at each change/PR; release promotion runs integration, mutation/negative-control, ABI/source, checkpoint/restart and live-artifact inventory checks. Slower full or randomized sweeps run at release boundaries or on a schedule. Checks must assert observable behavior, not implementation detail. A previous violation becomes a specific compiler rule or test when mechanically decidable. Apply refactors on real dependency boundaries and remove redundant compatibility layers once callers migrate.

Use one bounded human-attention queue with evidence-linked dispositions: `STOP_NOW` (model/custody/security corruption), `DECISION_REQUIRED` (missing approval or policy choice), `END_OF_RUN_REVIEW` (quarantined or stagnant capability), and `AUTOMATIC` (reversible, verified maintenance). Deduplicate repeats and expose changed information, risk, recommended decision and downstream effects. Review the queue's precision, missed incidents, response time and user attention cost. Never hide a mandatory human decision behind an automatic answer.

## Ten-question recurrence contract

For **every** proposed grade, the generated release-review record must answer all ten questions with an evidence pointer or explicit missing-proof status. A grade cannot promote on a checked box alone.

| User question | Machine-verifiable obligation before admission |
| --- | --- |
| Q1 Admission | Actual next-grade source/registry, environment, cumulative mastery and atomic model+AdamW transition preflight |
| Q2 Next grade | A versioned release proposal from qualified semantic/prerequisite data, not a new bespoke trainer module |
| Q3 AST/generation | Pure association, disambiguation and identification bindings; compositional probes; prerequisite-stage ordering; affected-family regeneration |
| Q4 Reuse/future work | Stable contracts, donor/adapter review, synthetic unfamiliar-semantic exercise and documented migration/rollback |
| Q5 Code quality | Static hygiene, behavior tests, module boundaries, independent oracles, negative controls, source/ABI compliance and exception receipts |
| Q6 Continuity | Canonical Git/release/issue identity, serialized writer proof, portable setup, state recovery and SHA readback |
| Q7 Failure containment | Capability health/quarantine proposal, unambiguous denominators, teacher credit and noninterference proof; policy approved before activation |
| Q8 Human attention | Priority-classified, deduplicated, evidence-backed decision queue with false-alert/missed-event review |
| Q9 Curriculum optimization | Ranked source/donor/semantic candidates, alternatives, independent expected benefits and observed outcomes across previous grades |
| Q10 Recursion | Fresh, generated Q1-Q10 review attached to every release with updated rules from verified incidents and prior outcomes |

## Order of work and first proof

1. Reconcile the actual C Registry approval and restore an authentic pinned artifact. Re-run the real C preflight, not only the proposed-graph fixtures. The human alone starts neural Grade C training after source and custody gates pass.
2. Promote the source-only composition contracts already drafted under `docs/architecture/04_*` and `05_*` only after their independent reviewer/verification gates. Keep the code-resident catalog and source adapter boundary singular.
3. Prototype one unfamiliar **disposable Grade D-like semantic** through a declared triad, prerequisite DAG, generated construction/test suite, held-out composition probes, mutation-sensitive proof report and offline restart rehearsal. No new trained vocabulary or actual Grade D admission.
4. Use this proof to define and ratify the default manifest schema, readiness CLI and required CI gate. Delete temporary bespoke scaffolding as the generic route absorbs its callers.
5. Run the curriculum/teacher health-policy proposals as separate, controlled experiments. Accept new run behavior only after measured benefit, clear human approval and an executable rollback.

The first falsifiable milestone is simple: **the next unfamiliar semantic and dependent capability must reach a complete source-only readiness report without editing a letter-specific trainer file.** The second milestone is that a future release with a missing Registry artifact must fail promotion despite a fully green synthetic test suite.
