# Bilqis repository architecture and migration to the semantic factory

**Status:** SUPERSEDED INITIAL SKETCH. Its broad package tree is not an accepted migration plan. Prefer the smaller compositional architecture in [04_COMPOSITION_AND_UPSTREAM_REUSE_DECISION.md](04_COMPOSITION_AND_UPSTREAM_REUSE_DECISION.md). Documentation only.
**Depends on:** 01_CODE_AUTHORITY_AND_SEMANTIC_AST.md and 02_GENERATIVE_CURRICULUM_FACTORY.md.

## 1. Why the current layout is costly

The present bilqis_mlx package holds 46 direct Python modules as peers, with 38 direct test modules. Names mix semantic definition, historical source adapters, neural state, scheduling, assessment generation, experimental grammar work, dashboards, disk management and one-off grade implementations. The grade_a_trainer module also spans source planning, feedback, checkpoint publication and runtime work.

Flat peers and named-grade modules do not reveal the rules that govern imports and decisions. A new agent cannot tell which module owns a semantic identity, which is an adapter, which is an executable release, and which is a research-only experiment without reading most of the repository.

The user-observed result is predictable: convenient small changes introduce independent slugs, copy data between files, and prove local tests against the same hard-coded assumptions. More modules of the same shape will not correct that architecture.

## 2. Recommended package tree

The tree below defines **ownership and dependency direction**. File names are design targets, not a command to move everything immediately.

~~~text
bilqis_mlx/
  semantics/
    catalog/                   # sole code-resident semantic ID authority
      identities.lock          # append-only identity map and original token ABI
      declarations/            # sharded typed declarations; no local ID minting
      release_manifest.json    # content-addressed admitted release
    model.py                   # typed immutable AST/value types
    identity.py                # ID allocation, alias resolution, lineage
    types.py                   # type expressions, unification, binding
    laws.py                    # LawDefinition, preconditions, applicability
    sources.py                 # SourceClaimId and ExternalReference
    admission.py               # proposal/source/proof/release state machine
    compile.py                 # canonical catalog compiler and graph checks

  sources/
    adapters/
      finite_micro.py          # pinned micro-world representation
      finite_development.py    # pinned development-world representation
      formal_boolean.py        # source-attested typed Boolean interpreter
      new_ithkuil.py           # approved NI grammar/lexicon adapters only
    oracle.py                  # shared checker interface and mismatch receipt
    attest.py                  # exact provider/source/grammar digests
    translate.py               # explicit cross-interpreter proof boundary

  factory/
    dependency.py              # graph closure and legal candidate relations
    obligations.py             # semantic coverage lattice and debt
    construction.py            # AST construction program and typed witnesses
    transforms.py              # registered law execution adapters
    generation.py              # deterministic lesson/exam instance generation
    verification.py            # source-oracle agreement and structural controls
    artifacts.py               # versioned plans, witness and release receipts

  curriculum/
    grades.py                  # grade memberships and canonical progression
    plans.py                   # intro/decomposition/practice/recovery plans
    examinations.py            # full-rubric and same-cohort exam contracts
    spiral.py                  # preserved A-to-current revalidation

  learning/
    options.py                 # teacher-readable legal teaching choices
    feedback.py                # unresolved mistakes, actual exposure, fairness
    diagnostics.py             # user's five executable signals
    outcomes.py                # delayed retention and paired comparisons
    teacher.py                 # inherited evolving teacher adapter

  runtime/
    student.py                 # complete model/optimizer boundary
    checkpoints.py             # full FP32+own AdamW, champions, custody
    events.py                  # immutable event outbox and crash recovery
    operator.py                # explicit human-only training gate
    resources.py               # disk and budget stops

  presentation/
    school50.py                # read-only projection of measured events
    cli.py                     # user commands, no semantic declarations

  compatibility/
    legacy_abi.py              # original 222 IDs, old aliases and import maps
    legacy_releases.py         # pinned historic A/B course and rubric readers
    legacy_receipts.py         # historical state/manifest compatibility

  research/
    ni_experiments/            # not an admission route
    numeric_prototypes/       # not an admission route

tests/
  semantics/                   # identity, type, schema/law/source invariants
  sources/                     # independent interpreter/translation controls
  factory/                     # generative properties and mutation campaigns
  curriculum/                  # full-grade, spiral and assessment integrity
  learning/                    # five signals, fairness, teacher noninterference
  runtime/                     # checkpoint/optimizer/readback/crash custody
  compatibility/               # frozen original ABI and historical snapshots
  integration/                 # assembled release and disposable trainer tests

docs/
  architecture/                # this proposal set, rationale and migration
  provenance/                  # stable source and review receipts
  operations/                  # supported operator commands and recovery
  historical/                  # archived v10-v16 and bounded research records
~~~

Do not create one Python wrapper per directory for its own sake. Each package earns its boundary by owning an invariant, data structure or evidence channel. Several existing files may merge; wrappers with one caller should disappear. The target tree may shrink when the actual migration proves simpler.

## 3. Dependency law

~~~text
semantics (immutable types and identity)
       ^
       |---------- sources (external adapters and oracles)
       |---------- factory (pure compilation/generation)
       |---------- curriculum (policies over typed refs)
       |---------- learning (measurements and teacher options)
       |
       +-------------- runtime (state, optimizer, custody)
                         |
                         v
                   presentation / cli
~~~

The arrows indicate modules that may import the lower-level shared semantic contract. The **core semantics must import none of runtime, teacher, dashboard or Google Sheets**.

Detailed boundaries:

| Package | Owns | Must not own |
| --- | --- | --- |
| semantics | Domain IDs, types, canonical declarations, law contracts, admission state, graph digest | Training decisions, Sheet fetches, neural rewards or question samples |
| sources | Source interpreters, independent oracles, exact attestations and verified translations | Semantic IDs, teacher scheduling, synthetic gold without source proof |
| factory | Legal constructions, witness generation, coverage debt, versioned artifacts | Grade promotion, training authority, mutable student state |
| curriculum | Grade membership, mastery prerequisites, examination roster and spiral state transitions | Semantic meaning definitions, arbitrary teacher rehearsal quotas |
| learning | Teacher options, actual exposure and mistakes, five-signal diagnostics, delayed outcomes | Semantic identity allocation, gold-answer generation |
| runtime | FP32 student+AdamW, protected champions, release binding, event durability, explicit operator gate | New semantic definitions or human-implicit model updates |
| presentation | Dashboard and CLI projection of real events | Source-of-truth ledger, admission or policy mutation |
| compatibility | Historical ABI and old receipt decoding | New feature semantics or permanent alternative execution path |

Source adapters may be plugged into the pure factory through typed protocols. A plugin that has no approved source proof remains available for research only.

## 4. Public interfaces remain few and meaningful

Caller-facing abstractions:

~~~python
catalog = SemanticCatalog.open_release(release_digest)
plan = CurriculumFactory.compile(catalog, source_adapters, scope)
options = plan.teaching_options(evidence)
examination = plan.generate_exam(seed, complete_roster=True)
receipt = EvidenceStore.record(observation)
result = GradeScheduler.advance(school_state, graded_assessment)
~~~

These hide the graph joins, source wiring, witness logic and checkpoint verification. Consumers cannot silently replace typed IDs with names.

The first-class outputs are **SemanticRelease**, **CoveragePlan**, **VerifiedConstruction**, **TeachingOption**, **ImmutableExamCohort**, **LearningEvidence**, **DiagnosticSignal** and **CheckpointReceipt**. They should be serializable with explicit schema and release versions.

### Import discipline

- Internal imports follow package boundaries; pure core cannot import adapters that execute source code.
- Naming and aliases resolve exactly once at API/CLI/Sheet boundaries.
- New plugin registration uses typed capabilities and source claims, not filename prefixes or local constant strings.
- No Grade B-specific switch is allowed in generic compiler, teacher, testing or dashboard code. A legacy adapter may be specifically B-compatible while it is being retired, but cannot become canonical design.
- Untracked research files remain isolated. They do not become fixtures or executable source by being moved into a package.

## 5. Migration map from the actual current repository

| Existing file family | Intended owner | Disposition |
| --- | --- | --- |
| curriculum.py, registry_ast.py, registry_versions.py, token_atlas.py | semantics + compatibility | Rebuild around one immutable AST, move Sheet parse to boundary adapter, retain historic ABI proof. |
| curriculum_compiler.py, semantic_coverage.py, generated_assessment.py, semantic_test_generation.py | factory | Compose behind one versioned compiler interface; delete old parallel dispatch only after behavior proof. |
| live_grade_a.py, live_grade_b.py, grade_a_probe.py, grade_a_oracle.py, grade_b_oracle.py | sources + factory + compatibility | Retain original source behavior as adapters. Generate future families from AST; no new grade-specific module wave. |
| semantic_transformations.py (untracked), tests/test_semantic_transformations.py (untracked) | research initially, then law compiler after independent proof | Preserve untouched; redesign its law IDs, predicates and holdout behavior before any admission. |
| grade_a_release.py, grade_a_manifest.py, grade_a_baseline.py, pedagogical_parity.py | compatibility + curriculum tests | Preserve readback and frozen historical evidence, move portable behavior into compiler contracts. |
| grade_a_trainer.py, school.py, champions.py, mlx_checkpoint.py, backup.py, disk.py | runtime + curriculum + learning | Split source construction and teacher policy away from checkpoint mutations, preserving AdamW custody. |
| capability_frontier.py, teacher_votes.py, soup.py, typed_answer_training.py | learning + runtime | Preserve learned-teacher state, grade vote multiplicity and typed answer contracts without reweighting. |
| school_telemetry.py, grade_a_dashboard.py, spiral_dashboard.py, cli.py | presentation + learning diagnostics | Keep grade-neutral six panels; separate actual diagnostic state from visual summaries. |
| ni_construction.py, ni_adjudication.py, ithkuil_alignment.py, integer_curriculum.py and related research | sources or research until admission | Keep staged status and independent NI/numeric qualification. |
| test_registry_ast.py and other current-count tests | semantics contract + compatibility | Keep fixed historical source cases only in compatibility tests; generate general tests from AST mutations. |

The map is a **migration disposition**, not permission to delete, rename or move any source yet. The exact moved-file inventory and public/private screening will be checked at implementation time.

## 6. Non-destructive, verifiable migration

This is a temporal plan, separate from the normative desired-state specification. Each phase must end with a runnable, inspectable, recoverable state.

### Phase 0: freeze and map

- Confirm private issue #336, root README/AGENTS/ADR and the feature branch's exact remote SHA.
- Inventory module imports, tests, model release seals and existing local uncommitted work.
- Preserve original 222 token ABI, historical source hashes, current student+AdamW, teacher history and champions.
- Record current tests and status without touching the actual student. No pruning, reset or broad staging.

### Phase 1: establish one identity authority

- Adopt existing historical token identities into the code-native AST catalog and lock the original indices.
- Allocate canonical IDs for admitted capabilities, grade identities, rule/law contracts and source bindings from one allocator.
- Import current aliases as versioned references without duplicating ID assignment.
- Validate round-trip resolution of old A/B model states, event receipts, questions and hashes under the new catalog.
- Compare code-first declarations against the Sheet research ledger; classify unbound rows as external proposals.

**Exit gate:** Rename, Sheet row reorder and added research text cannot change a released semantic ID or model ABI. No caller besides catalog migration tooling assigns IDs.

### Phase 2: prove semantic compilation on a small vertical slice

- Implement one typed semantic family and source adapter against the canonical AST.
- Register one metamorphic law with typed preconditions, source proof and independent oracle.
- Compile generated instruction/test witnesses from the same family and produce full lineage receipts.
- Mutate a synthetic identifier, alias, type and law definition in fixtures. Confirm exactly affected family regeneration.
- Keep live A/B trainer on its pinned release until independently qualified replacement is available.

**Exit gate:** General new/edit/rename tests pass without a capability-name branch or handwritten Sheet count assertion.

### Phase 3: migrate actual A+B constructors

- Express the six A source capabilities and six B Boolean compositions as admitted catalog definitions and legal constructor registrations.
- Reconcile the micro/development-world translation using formal source proof; classify unsupported cross-world compositions explicitly.
- Compare old and new generator behavior on identical source seeds and finite worlds. Preserve historic release decoding even if new coverage expands.
- Integrate complete test rosters and current-source independently scored golds. Retire duplicate source-of-truth paths in the same phase as callers migrate.

**Exit gate:** One factory drives admitted lesson/exam construction; no second B-only semantic registry remains authoritative. Previously trained checkpoint meanings and scores remain interpretable.

### Phase 4: general teacher and diagnostics integration

- Expose verified teaching options and unresolved source-verified misses to the inherited teacher; remove the unratified fixed B prerequisite sample allocation.
- Preserve all prior teacher state, optimizer custody and grade-vote behavior.
- Implement the five original automatic warning signals, negative controls, actual instructional-exposure receipts and delayed outcome checks.
- Validate whole-student temporary regression and A-to-current spiral gates with disposable state.

**Exit gate:** Diagnostics cause visible teacher-readable evidence, policy-respecting choices and delayed measurements; no effect is credited without a delivered visit.

### Phase 5: retire obsolete paths

- Remove dead Grade A/B-only dispatch paths, redundant adapters and duplicate semantic definitions after behavior parity.
- Move files into the accepted modular layout with mechanical import-boundary checks.
- Run full source-only, mutation, compatibility, disposable model, checkpoint recovery and resource/disk tests.
- Pin a new approved release; only the human may initiate any real-student validation.

**Exit gate:** One authoritative AST, one construction pipeline, one examination contract, one learned teacher interface and one preserved optimizer lineage. Issue #336 stays open until its separate empirical graduation/retention obligations are met.

## 7. Test organization and rules

**No general test asserts live Sheet sizes.** Sheet tests validate schema import, source provenance and externally changing data. A historical-compatibility test may assert the exact original 222 indices and historical snapshot digests; these are intentionally immutable witnesses of old releases.

Tests for new semantics use fixture ASTs generated through the same canonical identifier allocator. They check public behavior and literal expected results from an independent oracle. They do not duplicate implementation internals, hand-enumerate the current capability set, or infer semantic validity from a successful compile.

Install a static boundary check for:

- Domain ID creation outside the canonical catalog.
- String-based semantic slug dispatch in production compiler/scheduler code.
- Free-form source_axiom declarations without a registered SourceClaimId.
- Runtime imports from research or Sheet-ingestion implementation.
- Teacher rehearsal quantities forced by a per-grade branch.
- Tests that fetch live Sheet data or assert mutable Sheet inventory counts as general invariants.
- New grade-specific runtime modules where a registered adapter/AST rule would express the behavior.

Legacy compatibility modules receive explicit, narrowly scoped exceptions, with retirement ownership and historical release evidence.

## 8. Sequencing safeguards

The current feature branch has seven pre-existing modified tracked files from provisional Grade B repairs. The NI/semantic research and grade-report paths remain untracked. Migration planning must never stage, overwrite, delete or normalize those files by accident.

Do not run human optimizer commands, reset a model to the champion, reinterpret a saved checkpoint under the latest AST, alter AdamW or teacher policy, or silently change an admitted rubric. Keep the 100 GiB disk reserve and crash-safe immutable event receipts.

Source/adapter work may use disposable synthetic models and source-only interpreters. The compilation architecture's success is established by mutation-driven semantic coverage and verified generation. Neural learning remains a distinct human-owned acceptance gate.
