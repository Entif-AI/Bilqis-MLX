# TASK-0001: Implement SPEC-0001 and complete the Bilqis curriculum-factory cutover

## Mission

Transform the current Bilqis MLX repository so it conforms to `docs/specifications/0001_GENERATIVE_CURRICULUM_FACTORY.md`.

This is an implementation task. Do not stop at another proposal, RFC, source-only prototype, partial factory increment, or future migration plan. The prior failure was precisely that the generic factory existed beside a handwritten live runtime. Complete the cutover.

The intended outcome is one functional, compositional, modular, reusable curriculum factory through which every executable grade is constructed, verified, released, admitted, taught, assessed, generalized, and reported.

**Historical correction:** SPEC-0001 is not a newly invented architecture. It is a local enforcement/cutover consolidation of requirements that already existed across the Bilqis issue graph, roadmaps, execution checkpoints, registries, ledgers, protected authority, and governing specs. Do not describe this work as introducing the factory requirement. Describe it as finally making the existing requirement unavoidable in production code.

## User authority and non-negotiable intent

The user has repeatedly required that new grades NOT be implemented by hand one at a time. Treat this as the controlling product/architecture requirement.

The implementation must make the requirement structural. Do not rely on comments that tell future agents to remember it.

The runtime invariant is:

> No factory release, no grade.

A future grade must be impossible to add by writing `live_grade_d.py`, `grade_d_trainer.py`, grade-specific scheduler branches, or similar bespoke runtime paths.

## Mandatory reads before mutation

Read, in this order:

1. `README.md`
2. `AGENTS.md`
3. `ADR.md`
4. `docs/specifications/0001_GENERATIVE_CURRICULUM_FACTORY.md`
5. `docs/specifications/0002_CHAMPIONSHIP_LIFECYCLE_V1.md`
6. `docs/specifications/0003_CANDIDATE_RETENTION_GRADE_NET_V1.md`
7. the current factory/compiler and semantic architecture code
8. the existing architecture/factory documents under `docs/architecture/`
9. the current A/B/C source constructors, oracles, admission code, scheduler, teacher, evaluation, checkpoint, telemetry, and CLI paths
10. relevant historical receipts before changing compatibility behavior

Then close the historical authority loop before implementing. At minimum, inspect the live/current forms of:

- `Entif-AI/Bilqis#5` program roadmap / coordination spine;
- `Entif-AI/Bilqis#7` semantic ABI and canonical AST;
- `Entif-AI/Bilqis#17` prerequisite graph and developmental stage contracts;
- `Entif-AI/Bilqis#82` developmental curriculum gate;
- `socr8s/private-ip#335` / IPR-0220 and `Entif-AI/bilqis-mlx#1` where access permits;
- [https://github.com/Entif-AI/Bilqis/issues](https://github.com/Entif-AI/Bilqis/issues)
- [https://github.com/socr8s/private-ip/issues?q=is%3Aissue+state%3Aopen+%22bilqis%22+in%3Atitle](https://github.com/socr8s/private-ip/issues?q=is%3Aissue+state%3Aopen+%22bilqis%22+in%3Atitle)
- [Bilqis-MLX Specs and Failures Ledger - 20261011-20261017](https://docs.google.com/spreadsheets/d/1KhKLENPnP0f3db7g8_gOBzeOTFJkzeX0LsnHsCazQxQ/edit)
- [https://github.com/Entif-AI/bilqis-mlx/issues/1](https://github.com/Entif-AI/bilqis-mlx/issues/1)
- [Bilqis Roadmap - 20261006](https://docs.google.com/document/d/19mUp81fRDxBVwc6gX7xNRo6rIeIgMJqyVYo_UQPM5xw/edit)
- [Bilqis ALPHA-01 to ALPHA-02 | Codex Execution Checkpoint - 20261011](https://docs.google.com/document/d/1JIiyP2-4bJVWWHqYYt3TJmmY5FYwc2h-8n41TzIgydY/edit)
- [Bilqis Roadmap Supplement | Alpha Exit, Evidence Transfer, and Mainline Acceleration - 20261011](https://docs.google.com/document/d/1x1jtvd1KCfcu7nkz3sLgbaPCBBTEd8NvDeZFaBR-67I/edit)
- [Bilqis MLX | Champions, Soups, Golden Ancestors & Grade Advancement | Governing Specification v1.0 | 2026-10-18](https://docs.google.com/document/d/1UURzJNes-tB7AZU2pSjB9-q-aWholnjtGbbUJcLTgXI/edit)
- [Bilqis Curriculum Registry - Version, Lessons, Prerequisites and Champion States](https://docs.google.com/spreadsheets/d/1xtOjO0jGCxjU2bgcg0TKpVruJ4Z5O3vW9ixu6oMQ-so/edit)
- [Bilqis New Ithkuil Semantic Bridge - Chapter 3 and Mathematical Root Seed v0.1](https://docs.google.com/document/d/1Ti7gSwSWQdHB7W2Qpxtm_I6zylXBcrmFAjhEsTrDJv4/edit)

The point of this read is not to reopen design. It is to preserve the full pre-existing contract and identify where implementation deviated from it. Record any genuine conflict instead of using later implementation as evidence that earlier requirements never existed.

Where older architecture prose conflicts with SPEC-0001, SPEC-0001 is the desired-state authority. Preserve conflicting historical prose as evidence rather than rewriting history.

## Safety and execution rules

- Never start or resume the human's real neural optimizer.
- Before every repository mutation, check for an active `bilqis_mlx.cli train --human-run` process and the authoritative operator lock. Do not mutate the active source tree while a human trainer owns it.
- Preserve the current student, native AdamW, checkpoints, champions, soups, cohorts, run ledgers, source receipts, and original ABI.
- Do not manually edit run `state.json` or `events.jsonl`.
- Use a dedicated governed branch/worktree according to current repository writer-coordination rules. Never force-push.
- Build in small verifiable units. Keep the repository runnable at each meaningful checkpoint.
- Use disposable models, synthetic fixtures, and read-only historical checkpoints for execution proof. Human neural validation is a later gate.

## Required work

### 1. Inventory the real architecture

Map the current production path from semantic definition to actual optimizer batch and from source construction to graduation.

Identify:

- every grade-name branch;
- every canonical `live_grade_*`, `grade_*_trainer`, `grade_*_evaluator`, or equivalent per-grade path;
- duplicate semantic registries;
- source/oracle implementations;
- factory/compiler code that is already reusable;
- assessment lifecycle implementations;
- teacher-policy integration;
- checkpoint and recovery boundaries;
- documentation and test references that will move.

Use this inventory to avoid building a second replacement beside the first replacement.

Also produce a concise authority-to-implementation divergence map. For each material pre-existing curriculum/factory requirement, identify whether the current code: conforms, partially conforms, bypasses it, or has no enforcement. This is a failure-forensics aid, not permission to renegotiate the requirement.

### 2. Establish the canonical typed factory contracts

Implement the SPEC-0001 domain contracts using the smallest coherent set of types and modules.

At minimum, establish executable equivalents of:

- `SemanticRelease`
- `CapabilityDefinition`
- `GradeDefinition`
- `SourceAdapter`
- `ConstructionProgram`
- `CoveragePlan`
- `TeachingOption`
- `AssessmentPlan`
- `FactoryRelease`
- `LearningEvidence`
- `AdmissionReceipt`

Reuse existing types where they already satisfy these responsibilities. Delete or migrate duplicate definitions instead of wrapping them indefinitely.

### 3. Make the factory the only production construction path

Migrate current A, B, and C construction into the common factory.

The factory must own generic:

- prerequisite closure;
- construction compilation;
- coverage obligations;
- source verification;
- lesson specimen generation;
- assessment specimen generation;
- release assembly;
- admission validation.

The trainer consumes verified factory artifacts. It does not import grade-specific constructors directly.

### 4. Separate genuine source-domain adapters from grade policy

Preserve domain-specific source code only when it represents a real source system or oracle boundary.

A finite micro-world adapter, formal Boolean adapter, numeric adapter, or New Ithkuil adapter can be domain-specific. It cannot decide:

- scheduler behavior;
- trainer policy;
- assessment lifetime;
- promotion rules;
- championship behavior;
- dashboard behavior.

Those are generic consumers of typed factory artifacts.

### 5. Repair assessment and graduation semantics generically

Implement the assessment classes from SPEC-0001:

- fresh routine MAIN/RECOVERY assessment;
- fixed promotion attempt whose failed questions and gold remain teachable after scoring;
- cumulative whole-school graduation under existing governing championship rules.

Do not reintroduce the unauthorized frozen-routine-exam behavior.

Preserve the user's explicit no-holdout rule for promotion: failed promotion questions and gold may be used as supervised lessons, and the same fixed promotion attempt may be retried. Do not pass gold into scoring inference.

Treat promotion as the current developmental qualification proof. Do not describe it as proof of broad generalization. Fresh GENERALIZATION is dormant until a future explicit human maturity decision re-admits it.

### 6. Preserve dormant generalization compatibility without activating it

Historical generalization artifacts belong to compatibility/research surfaces, not the current live developmental graduation path.

Implement:

- declared variation axes;
- fresh source-valid specimen generation;
- contamination state;
- cheap surface-leakage baselines where applicable;
- source/oracle provenance;
- fail-closed parsing and provenance for historical generalization evidence;
- no automatic live scheduling or graduation dependency on that evidence.

Use the known historical B false-mastery case as a permanent diagnostic fixture showing that familiar-cohort mastery and fresh-cohort performance are distinct measurements. It must not reintroduce a current graduation gate.

### 7. Preserve existing candidate-retention and championship contracts

Migrate the logic governed by specs 0002 and 0003 onto generic learning/evaluation artifacts.

Do not silently change their user-directed semantics while reorganizing code.

If implementation reveals an actual conflict between SPEC-0001 and those contracts, record the conflict explicitly and complete all independent work before escalating it. Do not invent a reconciliation.

### 8. Split the current mega-runtime by ownership

Refactor `grade_a_trainer.py` and other oversized mixed-responsibility modules so source construction, curriculum planning, learning policy, runtime mutation, checkpoint custody, evaluation, and presentation have distinct owners.

Use the package shape in SPEC-0001 as a target, not a requirement to create empty wrapper packages. Each directory and module must own a real invariant.

Delete one-caller wrappers and duplicate paths when callers have migrated.

Do not preserve legacy APIs merely to avoid migrating internal callers. Migrate callers and remove the obsolete API in the same verified wave when safe.

### 9. Reorganize tests with the code

The existing flat top-level test directory is not the desired end state.

Move unit and contract tests beside the package they test, for example:

```text
bilqis_mlx/factory/
  construction.py
  release.py
  tests/
    test_construction.py
    test_release.py
```

Use the same pattern for semantics, sources, curriculum, learning, runtime, presentation, and compatibility.

Keep only genuine cross-package integration and disposable end-to-end proofs under top-level `tests/integration/` and `tests/system/`.

Test modules must be focused. Split files that test unrelated contracts or require unrelated fixture families. Keep fixtures local to the narrowest owner. Avoid giant shared fixture modules that recreate global coupling.

Tests must assert public behavior and independently derived expected values. Avoid assertions that can pass because the test and implementation share the same helper.

### 10. Add structural anti-regression checks

The repository must mechanically reject future factory bypasses.

Add static or executable checks that fail on:

- new grade-name dispatch in generic runtime;
- new canonical `live_grade_*` or `grade_*_trainer` production modules;
- semantic ID creation outside the canonical catalog;
- runtime imports from research modules;
- training code generating source gold;
- grade-specific teacher quotas in generic code;
- training/admission paths that bypass `FactoryRelease` validation.

Keep explicit compatibility exceptions narrow and documented.

### 11. Prove the factory with synthetic Grade Z

Create a synthetic test-only Grade Z through declarative semantic/grade registration plus a test source adapter.

The proof must add Grade Z without modifying generic:

- trainer code;
- scheduler code;
- evaluator code;
- promotion logic;
- dashboard code;
- checkpoint code;
- teacher runtime.

If the proof requires any of those changes, the factory is incomplete. Fix the factory rather than adding the exception.

### 12. Migrate A/B/C through the same release path

A, B, and C must all produce and consume `FactoryRelease` artifacts through one API.

Preserve historical release readers, but remove current production authority from bespoke A/B/C paths.

Prove:

- A source/evaluation parity and historical ABI compatibility;
- B source/oracle correctness and compatibility readback of the known fresh-cohort diagnostic;
- C source/typed-answer behavior without granting C a special runtime path.

### 13. Unfuck `docs/`

The documentation tree is already an unstructured accumulation of reports, experiments, snapshots, proposals, and current contracts. Clean it as part of this task.

Conform to the taxonomy in SPEC-0001:

```text
docs/
  README.md
  specifications/
  tasks/
  architecture/
  operations/
  evidence/
    grades/
    experiments/
    diagnostics/
    development/
  provenance/
  history/
```

Requirements:

- Inventory every current document before moving it.
- Classify it as normative spec, execution task, current architecture, operation/runbook, evidence, provenance, or history.
- Use `git mv` so repository history remains legible.
- Preserve forensic/historical evidence. Do not delete it merely because it is ugly or superseded.
- Move superseded proposals and archived design drafts to history rather than leaving them beside current architecture.
- Move date-stamped experiments and forensic reports under evidence.
- Move source audits, manifests, registry snapshots, adjudication records, and immutable source ledgers under provenance.
- Add `docs/README.md` with a concise authority legend and navigation index.
- Leave no general documents loose at the root of `docs/` other than `README.md`.
- Repair every internal repository link and code comment that refers to moved paths.
- Do not copy documents to new locations and leave duplicate authoritative versions behind.
- Do not rewrite old evidence to make it appear current.

### 14. Keep code organization deliberate

Do not solve the current mess by creating a deeper mess with prettier folder names.

Before adding a module, state the invariant it owns. Prefer cohesive data structures and pure functions over forwarding wrappers.

Keep semantic identity, source truth, factory compilation, curriculum policy, learning policy, runtime state mutation, and presentation separated by import boundaries.

Use typed values for lifecycle and result states instead of free-form strings where practical.

### 15. Preserve performance and concurrency semantics

The existing source-prefetch worker feature is throughput-only. Preserve deterministic packet identity and sole MLX/AdamW writer custody while moving code into the new structure.

Do not turn factory generation into concurrent neural training.

### 16. Verify real historical behavior

Use existing read-only checkpoints/cohorts and disposable clones where available to prove migration behavior.

At minimum preserve the evidence that:

- historical A fresh-cohort evidence remains readable;
- the pre-C B "graduate" passes its familiar cohort but scores materially lower on historical fresh B cohorts;
- C vocabulary admission alone does not perturb old A/B outputs;
- current developmental graduation does not depend on a generalization gate.

Do not reinterpret historical event records under new semantics without an explicit compatibility adapter.

## Required test and proof set

The final implementation must include and pass:

1. focused colocated unit/contract tests for every new package;
2. synthetic Grade Z factory-extension proof;
3. A/B/C factory-release integration tests;
4. semantic/ABI mutation tests;
5. assessment-lifecycle contamination tests;
6. candidate-retention conformance tests;
7. championship/graduation conformance tests;
8. historical checkpoint/readback compatibility tests;
9. crash/recovery and admission idempotency tests;
10. static architecture/import-boundary tests;
11. docs-link validation after reorganization;
12. full repository test suite;
13. disposable end-to-end school test with no real human neural run.

Do not count mocked perfect predictions as proof of neural acquisition or generalization.

## Definition of done

Do not close this task while any of the following are true:

- the live trainer still imports canonical grade-specific constructors;
- a new grade can bypass the factory;
- A/B/C use materially different admission/evaluation lifecycles because of grade identity;
- ordinary scheduler movement can open promotion without an authoritative grade-exam epoch advance;
- the live developmental path can automatically schedule GENERALIZATION;
- the runtime can train a grade without a validated factory release and admission receipt;
- unit tests remain primarily dumped into one flat top-level directory;
- `docs/` remains a root-level pile of dated reports and current contracts;
- old grade-specific paths remain as current alternative production routes;
- the synthetic Grade Z proof requires generic runtime edits;
- full verification is not green.

The final report must identify:

- final package tree;
- final docs tree;
- deleted/retired production bypasses;
- preserved compatibility surfaces;
- A/B/C migration evidence;
- Grade Z proof;
- proof that historical generalization evidence remains readable but dormant;
- complete test results;
- any remaining blocker that requires the human.

Do not launch the human optimizer as part of this task. End at a verified, committed, pushed, reviewable source state with an exact continuation command for the human's later validation run.
