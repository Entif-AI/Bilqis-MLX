# SPEC-0001: Bilqis generative curriculum factory and mandatory runtime cutover

**Status:** Normative enforcement and runtime-cutover specification. Consolidates pre-existing Bilqis architecture authority; does not originate that architecture.
**Change posture:** NORMATIVE.
**Scope:** Bilqis curriculum semantics, grade construction, lesson generation, assessment, admission, promotion, generalization, teacher integration, runtime boundaries, repository structure, tests, and documentation organization.
**Authority:** Longstanding direct-user and project authority requires Bilqis to use a functional, compositional, composable, modular, flexible, reusable curriculum architecture instead of handwritten per-grade implementations. This specification does not create that requirement. It consolidates the already-existing contract into one local executable enforcement specification and makes the previously uncompleted runtime cutover mechanically mandatory.
**Related specifications:** `0002_CHAMPIONSHIP_LIFECYCLE_V1.md` and `0003_CANDIDATE_RETENTION_GRADE_NET_V1.md` remain normative for their domains. They must be implemented through the factory contracts defined here. Conflicts must be surfaced and resolved explicitly, not silently reconciled.

## 0. Pre-existing authority and historical correction

SPEC-0001 is **not** the origin of the Bilqis curriculum-factory architecture. The architecture, its semantic substrate, its prerequisite-aware curriculum, its generated/source-grounded teaching and assessment boundaries, and its reuse expectations were already present across the project's governing issue graph, roadmaps, execution checkpoints, registries, ledgers, and successor contracts before this file was written.

At minimum, implementation and review must treat the following as pre-existing authority/evidence to reconcile rather than material invented by SPEC-0001:

- `Entif-AI/Bilqis` coordination issue #5, which defines the explicit developmental program and names the semantic ABI, deterministic compiler/codecs, generators/oracle, truth-bounded teacher, prerequisite graph/stage contracts, learner path, and curriculum gates as first-class program components;
- `Entif-AI/Bilqis` issue #7, which defines the shared typed semantic ABI/AST consumed by generators, codecs, teachers, oracles, and students;
- `Entif-AI/Bilqis` issue #17, which requires a machine-readable prerequisite graph and explicit developmental stage contracts rather than opaque curriculum order;
- `Entif-AI/Bilqis` issue #82, which freezes the cognition-before-language developmental curriculum and deterministic promotion gates;
- `Bilqis Roadmap - 20261006`, including its explicit, versioned, testable curriculum-order contract and issue hand-off/gate model;
- `Bilqis ALPHA-01 to ALPHA-02 | Codex Execution Checkpoint - 20261011`, which explicitly states that the roadmap and pre-existing issues already specify the typed semantic ABI, T0-T4 logic kernel, semantic geometry, deterministic initialization, learner training, and M3 qualification and that the checkpoint does not invent those obligations;
- `Bilqis Roadmap Supplement | Alpha Exit, Evidence Transfer, and Mainline Acceleration - 20261011`, which preserves the full #7/#79-#86/#17 foundation contracts outside the bounded alpha exception;
- `Bilqis-MLX Specs and Failures Ledger - 20261011-20261017` and the Bilqis Curriculum Registry, which carry requirement, failure, lesson, prerequisite, version, and champion-state continuity;
- protected Bilqis authority including IPR-0220 / `socr8s/private-ip#335`, plus successor `Entif-AI/bilqis-mlx` issue #1, which already requires source/prerequisite validation, taught-root-only evaluation, no premature composition, grade-linked voting, and continuation of the same student/optimizer lineage;
- `Bilqis MLX | Champions, Soups, Golden Ancestors & Grade Advancement | Governing Specification v1.0 | 2026-10-18`, which continues source admission, prerequisite semantics, independent lesson/exam generation, grade advancement, and human-only optimizer authority;
- `Bilqis New Ithkuil Semantic Bridge - Chapter 3 and Mathematical Root Seed v0.1`, which again describes deterministic source-semantic AST construction, prerequisite-bound lessons, held-out composition, counterbalanced generation, and reuse of the same continuing learner.

The historical failure addressed here is therefore **not absence of specification**. It is repeated execution drift away from already-specified architecture, combined with insufficient structural enforcement to prevent bespoke grade-specific runtime work from bypassing those contracts.

## 1. Purpose

Bilqis must have one curriculum system. New grades and capabilities must be data- and contract-driven instances of that system, not new runtime architectures.

The repository currently contains a partially generic semantic/compiler path beside a handwritten live-school path. Grade A accumulated dedicated probe, manifest, oracle, baseline, evaluator, release, live-constructor, compatibility, and trainer machinery. Grade B and Grade C then entered through narrower grade-specific paths. This split allowed different grades to receive different evidence, assessment, release, and generalization safeguards.

That outcome violates the already-existing design requirement. The end state consolidated here removes the split and turns prior architectural authority into a runtime-enforced invariant.

The governing rule is:

> **No factory release, no grade.**

A grade that cannot be compiled, verified, released, admitted, taught, assessed, generalized, and retired through the common factory contracts is not an executable Bilqis grade.

## 2. Required end state

One authoritative pipeline owns every admitted grade:

```text
source evidence + semantic catalog
              |
              v
      canonical typed AST
              |
              v
     curriculum factory
              |
      +-------+--------+-------------------+
      |                |                   |
      v                v                   v
construction      teaching plans      assessment plans
      |                |                   |
      +-------+--------+-------------------+
              |
              v
       verified release
              |
              v
      generic school runtime
              |
              v
        human-owned trainer
```

The factory compiles reusable programs and release artifacts. It does not own mutable neural state or teacher policy. The runtime executes only released artifacts. The trainer never decides what Grade B, Grade C, or any future grade means.

## 3. Non-negotiable invariants

### 3.1 One execution path

Every admitted grade uses the same construction, lesson, routine-assessment, promotion, generalization, admission, telemetry, and release interfaces.

Production runtime code MUST NOT select behavior by letter-grade identity. Code such as `if grade == "B"` or imports such as `live_grade_b` are allowed only inside explicit compatibility adapters while those adapters are being retired. Compatibility code MUST NOT be the canonical path for a new grade.

### 3.2 Grade identity is declarative

A grade is a versioned declaration over typed capability references. A grade declaration does not contain trainer code, scheduler code, dashboard code, or local semantic truth implementations.

Adding a grade MAY require registering a genuinely new source-domain adapter or answer modality. It MUST NOT require edits to the generic trainer, scheduler, evaluator, promotion logic, dashboard, checkpoint code, or teacher runtime.

### 3.3 Semantic identity has one authority

The code-resident semantic catalog and immutable ABI manifest own admitted semantic identities, token identities, types, prerequisites, source bindings, and release lineage.

Sheets, prose documents, experiments, and historical snapshots may supply evidence or proposals. They cannot mint runtime semantic identities.

### 3.4 Source truth is independent of training

Every construction family binds to source evidence and an independently callable oracle/checker contract. The factory verifies source agreement before a construction becomes eligible for training or assessment.

The trainer does not generate gold answers.

### 3.5 Teaching and assessment share meaning, not specimens

Teaching and assessment are compiled from the same verified semantic and construction contracts. They use independent specimen identities and explicit lifecycle rules.

A successful compile does not prove student mastery. A successful source-oracle check does not authorize neural training. A successful training visit does not authorize promotion.

### 3.6 Generalization is part of graduation

A grade cannot graduate solely by passing a familiar cohort.

Promotion requires independent fresh source-valid evidence generated from the same released semantic contract. The factory must make the lifetime and contamination status of every assessment cohort explicit.

### 3.7 Progression may carry explicit mastery debt without fabricating graduation

Graduation and access to new learning territory are separate authorities. The ordinary path remains cumulative same-checkpoint mastery before clean next-grade admission. However, after substantial stagnation rehabilitation, an explicit human-authorized admission MAY open the next source-valid released grade while preserving every currently imperfect prior capability as durable `carried_mastery_debt`.

Debt admission MUST NOT fabricate a champion, graduation receipt, perfect score, or historical reclassification for an unresolved grade. The complete current-checkpoint prior-course assessment is the authority for the exact carried capability set. While any carried debt remains, cumulative assessment keeps every admitted grade in scope and ordinary grade-neutral spiral scheduling continues across imperfect grades. A later grade may itself earn a champion without erasing earlier debt. The debt epoch ends only when one intact student checkpoint with its own optimizer satisfies the complete active-school mastery contract; only then may the runtime reach the ordinary clean next-grade boundary.

Debt admission is an explicit human progression decision, not a fixed timeout, two-recovery-round shortcut, or autonomous scheduler guess. The factory/runtime must preserve the release, ABI, vocabulary-growth, source-admission, checkpoint-custody, championship, and human-optimizer gates that would apply to an ordinary admission.

### 3.8 Human neural authority remains unchanged

Only the human may start or resume actual optimizer updates. Factory compilation, source verification, disposable model tests, static conformance checks, and read-only checkpoint evaluation do not authorize a live neural run.

### 3.9 Historical evidence is immutable

Existing checkpoints, AdamW state, cohorts, event ledgers, source manifests, rubrics, champions, soups, receipts, and historical documents remain interpretable. Migration must preserve their hashes and decoding paths.

Compatibility is a reader of history, not a second production architecture.

## 4. Canonical domain model

The factory must operate on typed objects. Names below define responsibilities, not mandatory Python class names.

### 4.1 `SemanticRelease`

A content-addressed release of the admitted semantic catalog.

It contains:

- immutable semantic and token IDs;
- typed signatures and answer modalities;
- prerequisite and composition edges;
- source claim bindings;
- admitted vocabulary geometry;
- release digest and predecessor lineage.

### 4.2 `CapabilityDefinition`

A declarative capability contract.

It identifies:

- capability ID;
- semantic operation or relation;
- typed operands and result;
- prerequisite capabilities;
- legal construction families;
- source adapters and oracle contracts;
- coverage obligations;
- answer modality;
- admissible transformations and contrasts.

It does not contain scheduler or optimizer behavior.

### 4.3 `GradeDefinition`

A versioned ordered set of capability references plus grade-level release requirements.

It identifies:

- grade ID;
- capability roster;
- prerequisite closure;
- intra-grade stage dependencies when needed;
- assessment scope;
- graduation/generalization requirements;
- semantic release compatibility.

It MUST NOT contain grade-specific trainer callbacks.

### 4.4 `SourceAdapter`

A typed adapter to an independently governed source domain.

It owns:

- source representation;
- deterministic source construction primitives;
- source encoding;
- independent oracle/checker access;
- source provenance digest;
- lawful translation boundaries to other adapters.

A source adapter may be domain-specific. The factory and runtime remain grade-neutral.

### 4.5 `ConstructionProgram`

A reusable program compiled from capability definitions and source adapters.

It defines legal variation axes, positive/negative cases, structural contrasts, metamorphic relations, prerequisite compositions, source constraints, and answer modalities. It produces specimens from seeds. It does not store a permanent question inventory.

### 4.6 `CoveragePlan`

A machine-readable set of obligations that a release must satisfy.

Examples include:

- truth/polarity coverage;
- operand-pattern coverage;
- source-world diversity;
- prerequisite coverage;
- legal and illegal construction coverage;
- alternative construction coverage;
- answer-space coverage;
- complexity/depth bands;
- generalization strata.

Coverage debt is explicit. Missing required coverage blocks release.

### 4.7 `TeachingOption`

A verified instruction option offered to the learned teacher.

It contains semantic purpose, construction family, source proof, eligible variation axes, prerequisite relation, and evidence context. The teacher chooses among legal options through its learned policy. The factory does not impose arbitrary per-grade rehearsal quotas.

### 4.8 `AssessmentPlan`

A released plan for generating source-valid assessment cohorts. It declares the assessment class and specimen lifecycle.

Assessment classes are defined in section 7.

### 4.9 `FactoryRelease`

The only artifact that makes a grade executable.

It binds:

- semantic release;
- grade definition;
- capability definitions;
- source adapters and source digests;
- construction programs;
- coverage plan and satisfied obligations;
- teaching-option schema;
- assessment plans;
- evaluator/oracle contracts;
- release tests and verification receipts;
- runtime compatibility constraints;
- content digest and predecessor release.

The runtime accepts a `FactoryRelease` or refuses the grade.

### 4.10 `LearningEvidence`

A typed observation of actual student behavior. It distinguishes source facts from model measurements.

It can represent:

- routine assessment;
- promotion attempt;
- fresh generalization;
- target lesson probe;
- retention comparison;
- diagnostic warning;
- delivered teaching exposure;
- delayed outcome.

### 4.11 `AdmissionReceipt`

An immutable runtime receipt proving that a specific factory release was admitted against a specific student geometry and semantic ABI.

No grade is active without this receipt.

## 5. Factory pipeline

The canonical pipeline is deterministic and fail-closed.

### 5.1 Resolve semantic scope

Load one admitted `SemanticRelease`. Resolve all capability and prerequisite IDs through typed references.

Unknown, proposed, research-only, or source-unqualified semantics remain unavailable to executable grades.

### 5.2 Close prerequisites

Compile the complete prerequisite graph for the requested grade. Support same-grade staged dependencies through explicit stage ordering rather than grade-name exceptions.

Reject cycles, future-stage dependencies, unqualified edges, and missing source bindings.

### 5.3 Compile constructions

For every capability, compile source-backed `ConstructionProgram` objects from registered typed constructors and adapters.

The compiler must support composition, partial application, lifting, lawful transformations, contrasts, and other higher-order construction techniques without encoding capability slugs in generic control flow.

### 5.4 Compile coverage obligations

Derive the required coverage lattice from capability type, source domain, construction program, prerequisites, and assessment contract.

No handwritten list of current capability names may define general coverage behavior.

### 5.5 Verify source behavior

Generate bounded proof specimens and verify them through independent source/oracle paths. Verify positive and falsifying controls.

A shared implementation cannot serve as both constructor and independent oracle unless a separate source-grounded equivalence proof exists.

### 5.6 Compile teaching options

Produce teacher-readable legal options from verified constructions and current learning evidence.

The factory may expose prerequisite reinforcement, contrast, depth, composition, rehearsal, and source-family alternatives. The teacher remains responsible for policy choice.

### 5.7 Compile assessments

Generate assessment plans from the same verified semantic contracts while preserving specimen independence and lifecycle boundaries from section 7.

### 5.8 Produce factory release

A release is content-addressed and complete. Partial source-only candidate packages do not become runnable grades.

The release must fail closed if any required factory artifact is missing.

### 5.9 Admit atomically

The generic runtime validates the factory release against the active model ABI, semantic ABI, source receipts, student checkpoint, native AdamW custody, and current school state.

Admission changes school curriculum state only. It never performs an optimizer update.

## 6. Required runtime architecture

The runtime consumes factory artifacts. It does not recreate them.

The desired package ownership is:

```text
bilqis_mlx/
  semantics/
    catalog/          canonical IDs and immutable ABI release data
    model.py          typed semantic AST/value definitions
    identity.py       IDs, aliases, lineage
    types.py          typed signatures and binding
    admission.py      semantic proposal/proof/release states
    compile.py        catalog compilation and graph checks
    tests/

  sources/
    adapters/         finite-world, Boolean, numeric, NI, and future adapters
    oracle.py         independent checking protocol
    attest.py         source/provider digests
    translate.py      explicit cross-domain proof boundary
    tests/

  factory/
    dependency.py     prerequisite and stage closure
    construction.py   typed construction programs
    coverage.py       coverage obligations and debt
    generation.py     deterministic specimen generation
    teaching.py       verified teacher-option construction
    assessment.py     routine/promotion/generalization plan generation
    verification.py   independent source and structural checks
    release.py        FactoryRelease assembly and validation
    artifacts.py      serializable receipts and schemas
    tests/

  curriculum/
    grades.py         grade declarations and progression
    scheduler.py      grade-neutral progression over released grades
    spiral.py         cumulative revalidation policy
    tests/

  learning/
    teacher.py        learned teacher adapter
    feedback.py       misses, exposure, delayed outcomes
    retention.py      candidate-retention contract
    championships.py  championship and mentor contract
    diagnostics/      measured warning signals and controls
    tests/

  runtime/
    student.py        whole student + native AdamW boundary
    training.py       generic visit execution
    evaluation.py     generic assessment execution
    admission.py      atomic FactoryRelease admission
    checkpoints.py    checkpoint custody and recovery
    events.py         durable event/outbox handling
    operator.py       explicit human-run gate
    resources.py      disk and resource protections
    tests/

  presentation/
    cli.py
    dashboard.py
    tests/

  compatibility/
    historical_abi.py
    historical_releases.py
    historical_receipts.py
    tests/

  research/
    ...               non-admission experiments only

tests/
  integration/        cross-package behavior only
  system/             disposable end-to-end runtime proofs only
```

The exact file split may change if a smaller structure preserves the same ownership. One-caller wrappers and decorative package layers are forbidden.

## 7. Assessment lifecycle

Assessment lifetime must be explicit and generic. The runtime must never infer it from grade identity.

### 7.1 Routine assessment

Routine MAIN/RECOVERY evaluation uses fresh source-valid specimens on each scheduled cycle. Its purpose is learning-state measurement and scheduler/teacher evidence.

Routine assessment may feed exact source-verified misses back into teaching because those specimens are not promotion authority.

### 7.2 Promotion attempt

Promotion uses a fixed cohort only within one explicit qualification attempt so parent/candidate and retry comparisons remain interpretable.

Failed promotion questions and their gold answers remain valid supervised teaching material after scoring, as the user has explicitly required. Promotion scoring inference never receives gold, but the teacher may train on failed promotion specimens and retry the same fixed attempt.

Passing the fixed promotion cohort is therefore evidence of satisfying that explicit classroom criterion, not proof of out-of-sample generalization. The independent fresh generalization gate in section 7.3 is mandatory before graduation and is what prevents a familiar qualification cohort from masquerading as broad mastery.

### 7.3 Fresh generalization gate

After a promotion cohort is passed, the same checkpoint must pass a newly generated fresh generalization cohort from the same released construction contract.

The generalization cohort:

- is generated after the candidate checkpoint is fixed;
- shares semantic obligations, not specimen identities, with teaching/promotion data;
- is source-oracled independently;
- is scored once for that qualification decision;
- does not become a passable retry cohort after exposure;
- may yield concept-family evidence for future teaching;
- is burned after the decision.

After a failed generalization decision, its exact source-valid questions and gold may become teaching material. A later qualification must use a newly generated generalization cohort. There is no permanent question embargo.

Failure blocks graduation. It does not roll back evidence or rewrite gold.

### 7.4 Cumulative school graduation

Whole-school graduation still requires one intact causal student with its own native AdamW to satisfy the governing cumulative championship/graduation contract. Factory release and per-grade generalization are additional structural requirements, not substitutes.

### 7.5 Cohort provenance

Every assessment receipt includes:

- factory release digest;
- semantic release digest;
- grade/capability scope;
- assessment class;
- seed and generator release;
- source/oracle digests;
- specimen identities;
- student checkpoint SHA;
- optimizer step;
- contamination state;
- prior attempt lineage when applicable.

## 8. Teaching and failure feedback

The factory must teach concepts, not accidentally teach a qualification test.

When an assessment identifies a failure, the teacher may receive:

- failed capability;
- failed construction family;
- operand/truth/answer pattern;
- source-world shape;
- prerequisite relation;
- depth/complexity class;
- exact specimen only when its assessment lifecycle permits teaching.

The factory then generates fresh source-valid teaching specimens for the deficient semantic family.

No policy may silently convert an immutable qualification cohort into a reusable classroom simply because exact misses are convenient.

## 9. Generalization and leakage controls

The factory must test whether an apparent skill survives changes that should preserve meaning.

Each capability release declares applicable variation axes. Examples include world identity, entity names, operand order, source-world cardinality, structural depth, equivalent construction, answer balance, and prerequisite composition.

The generalization gate must draw across those axes. A capability cannot satisfy the gate solely through a surface feature that deterministically reveals the answer unless that feature is part of the intended semantics.

The factory must support cheap leakage baselines. Examples include answer prediction from sequence length, token counts, fixed positions, or other surface statistics. If a cheap baseline explains a capability at near-mastery accuracy, the release must either justify that signal as semantically intended or redesign the construction before claiming abstract acquisition.

## 10. Reuse contract

The factory is successful only if later work reuses it without editing generic runtime code.

### 10.1 Add a capability to an existing source domain

Required work:

- add or update the semantic declaration;
- bind existing source adapter operations;
- register legal construction/coverage rules when not derivable from existing type traits;
- compile and verify a new factory release.

Generic trainer, scheduler, evaluator, dashboard, checkpoint, and promotion code remain unchanged.

### 10.2 Add a new grade

Required work:

- declare ordered capability membership and prerequisites;
- compile a new factory release;
- pass factory verification and admission tests.

No `live_grade_x.py`, `grade_x_trainer.py`, `grade_x_evaluator.py`, or equivalent runtime module is created.

### 10.3 Add a new source domain

Implement one typed `SourceAdapter` plus independent oracle/source evidence. Existing factory and runtime interfaces remain unchanged.

### 10.4 Add a new answer modality

Implement a typed answer contract and its generic training/evaluation adapter. Capability definitions reference the modality. Grade identity does not control the answer path.

### 10.5 Add a new model precision/backend

Model precision is a runtime/student concern. The same factory releases, source semantics, teaching programs, and assessment contracts must be usable by FP32, ternary, or later compatible students unless the model ABI explicitly lacks a required answer/input modality.

## 11. Required conformance tests

The implementation is not complete until the following tests exist and pass.

### 11.1 Synthetic Grade Z test

A synthetic grade with dummy source-backed capabilities is added only through declarative semantic/grade registrations and a test source adapter.

The test MUST prove that adding Grade Z requires zero changes to:

- generic trainer;
- scheduler;
- evaluation runtime;
- promotion/generalization code;
- dashboard;
- checkpoint handling;
- teacher runtime.

A new grade-specific production runtime branch fails this test.

### 11.2 A migration parity

Grade A must compile and execute through the factory while preserving its admitted meaning, source correctness, ABI, historical release decoding, and strong fresh-source behavior.

Factory migration must not weaken A to make B look comparable.

### 11.3 Historical B false-mastery regression

The historical pre-C checkpoint that scored 72/72 on its familiar B qualification cohort but about 62% over fresh B cohorts must fail the factory's fresh-generalization graduation gate.

This is a permanent regression test for the failure that motivated this specification.

### 11.4 B and C factory migration

B and C must use the same factory interfaces as A. Grade-specific source adapters may remain only where they express real source-domain differences. They may not own training, release, assessment-lifetime, or promotion policy.

### 11.5 Assessment contamination tests

Tests must prove:

- routine cohorts redraw as specified;
- promotion cohorts remain fixed within an attempt even when failed promotion items become teaching material;
- promotion success alone never satisfies the independent fresh-generalization gate;
- fresh generalization cohorts are independent and burned after use;
- after a failed generalization cohort becomes teaching material, a later qualification uses a different fresh generalization cohort.

### 11.6 Mutation tests

Mutating a synthetic semantic type, prerequisite, source binding, or construction rule regenerates exactly the affected factory artifacts and blocks stale releases.

Renaming an editorial label must not change stable semantic IDs.

### 11.7 Import and architecture tests

Static checks must reject:

- grade-name dispatch in generic production runtime;
- semantic ID minting outside the catalog;
- runtime imports from research packages;
- new canonical `live_grade_*` or `grade_*_trainer` modules;
- source gold generation in training code;
- teacher policy ratios hard-coded by grade;
- production runtime paths that bypass `FactoryRelease` validation.

Narrow historical compatibility exceptions must be explicit and test-covered.

## 12. Test organization

Tests are part of the architecture and must follow the same ownership boundaries as production code.

Unit and contract tests MUST be colocated with the package they test, under that package's `tests/` directory. Fixtures and helpers stay with the narrowest package that owns them.

A test module should cover one coherent behavior or contract. If a file needs unrelated fixture families or tests multiple subsystems, split it.

The top-level `tests/` directory is reserved for true cross-package integration and disposable system proofs. It MUST NOT remain a flat dumping ground for every module in the repository.

Tests call code through the same public boundary used by the consumer. They assert observable behavior and literal independently derived expectations. They do not pass merely because two implementations share the same helper.

Historical compatibility tests may retain fixed hashes and exact legacy values because those are evidence. New general behavior tests use generated typed fixtures and mutation/property checks.

## 13. Documentation organization

The documentation tree must express authority and purpose. The repository root of `docs/` must not remain a chronological pile of unrelated reports.

The target taxonomy is:

```text
docs/
  README.md             index, authority legend, and navigation
  specifications/       numbered normative desired-state specifications
  tasks/                numbered execution prompts and work packets
  architecture/         current design rationale and technical decisions
  operations/           supported operator commands, recovery, runbooks
  evidence/
    grades/             grade reports and learning evidence
    experiments/        disposable experiment receipts and results
    diagnostics/        forensic and diagnostic reports
    development/        code-quality and engineering measurements
  provenance/           source audits, registries, manifests, adjudication records
  history/              superseded architecture/docs and preserved old snapshots
```

Rules:

- `docs/README.md` is the only general file at the root of `docs/`.
- Normative desired-state contracts live only in `docs/specifications/` and use four-digit stable numbers.
- Executable work prompts live only in `docs/tasks/` and use four-digit stable numbers.
- A document has one canonical home. Do not duplicate it into multiple categories.
- Move files with history-preserving renames and update internal links.
- Do not delete forensic, provenance, or superseded evidence merely to make the tree tidy. Move it to the correct evidence/history location.
- Date suffixes may remain on evidence artifacts where the date is part of identity. Current normative specs and tasks use stable numbered names instead.
- Generated machine-readable evidence belongs beside the human-readable evidence it supports, not at the root of `docs/`.

## 14. Migration requirements

The existing system must be migrated, not rewritten blindly.

### 14.1 Preserve before replacing

Inventory and preserve:

- current semantic/ABI authorities;
- A/B/C source constructors and oracles;
- current factory/compiler work;
- teacher state contracts;
- scheduler and spiral behavior;
- candidate-retention and championship contracts;
- historical checkpoint/readback support;
- event/recovery behavior;
- diagnostics and telemetry;
- operator safety rules.

### 14.2 Reuse proven work

Use existing semantic AST, construction contracts, source adapters, verification tools, curriculum compiler work, and historical compatibility logic where they satisfy this specification.

Do not build a second new factory beside the first one.

### 14.3 Migrate callers, then delete the bypass

Once A/B/C behavior is available through the factory and verified, migrate all production callers in the same implementation wave and remove the grade-specific canonical runtime paths.

Compatibility readers may remain for old receipts. They cannot remain callable as an alternative current training architecture.

### 14.4 Atomic runtime cutover

The generic runtime cutover is part of this specification's completion. A source-only factory beside a handwritten trainer is not conformance.

The runtime must refuse an executable grade without a valid `FactoryRelease` and `AdmissionReceipt`.

## 15. Code quality and module discipline

The deliverable must reduce reader load rather than rearrange the same complexity into more folders.

Requirements:

- each module owns one coherent concept;
- public interfaces are few and typed;
- dependency direction is enforced mechanically;
- no speculative abstraction with one trivial caller;
- no mega-module equivalent to the current trainer after migration;
- no grade-specific policy embedded in generic functions;
- no duplicate semantic registries;
- no free-form string protocols when a typed enum/value exists;
- no compatibility layer without an explicit historical purpose and retirement boundary;
- no new root-level code or test dumping grounds.

A directory boundary must correspond to an ownership boundary, not an aesthetic preference.

## 16. Required operator behavior

The human retains control of actual neural optimization.

Before any live run the operator preflight must verify:

- factory release digest;
- semantic release and ABI compatibility;
- source/oracle digests;
- assessment contracts;
- current student and AdamW custody;
- no active conflicting writer/trainer;
- human-run authorization.

Factory migration must not reset or silently reinterpret an existing student.

## 17. Acceptance criteria

SPEC-0001 is implemented only when all of the following are true:

1. One factory release path drives A, B, C, and a synthetic Grade Z.
2. New grades can be added without editing generic runtime code.
3. No canonical grade-specific trainer/evaluator/admission path remains.
4. A/B/C semantics and historical receipts remain readable and source-verifiable.
5. The historical false-positive B graduate fails the new fresh-generalization gate.
6. Routine, promotion, and generalization assessment lifecycles are distinct and mechanically enforced.
7. Candidate retention and championship logic consume generic learning/evaluation artifacts rather than grade-specific data shapes.
8. Teacher options are generated through generic verified construction contracts without hidden grade-specific quotas.
9. Unit/contract tests are organized beside their code packages. Top-level tests contain only integration/system proofs.
10. Static architecture checks reject new grade-specific runtime branches and factory bypasses.
11. `docs/` conforms to the taxonomy in section 13, with internal links repaired and historical evidence preserved.
12. The full repository test/conformance suite passes on the final code state.
13. Disposable end-to-end tests prove factory admission, training orchestration, dynamic routine assessment, promotion attempt, generalization gate, crash/recovery, and historical compatibility without launching the human's real neural optimizer.
14. The runtime cannot start training an admitted grade without a validated factory release and admission receipt.

## 18. Explicit non-goals

This specification does not require a new neural architecture, ternary weights, a new teacher algorithm, new curriculum semantics, or a reset of the current student.

It does not claim that the factory will make every capability easy to learn. It makes every capability pass through the same evidence, construction, evaluation, and release machinery so failures can be attributed to learning rather than inconsistent grade engineering.

It does not require preserving current file names. It requires preserving meaning, evidence, ABI, and behavior where still authoritative.

## 19. Governing failure test

The factory has failed if a future engineer can add Grade D by creating a handful of Grade-D-specific source/trainer/evaluator files and wiring them into the live runtime without touching the factory.

The factory has succeeded when that path is mechanically impossible.
